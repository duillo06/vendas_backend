from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.communications.domain.catalog import human_error
from apps.communications.domain.enums import Channel, ConnectionRole, ConnectionStatus, ProviderKey
from apps.communications.domain.exceptions import ConnectionError as CommConnectionError
from apps.communications.domain.ports import ConnectionContext
from apps.communications.infrastructure.providers.evolution.client import EvolutionHttpError
from apps.communications.infrastructure.providers.registry import get_provider
from apps.communications.models import CommunicationConnection
from apps.communications.services.credentials import open_credentials, seal_credentials
from apps.communications.services.helpers import (
    ensure_templates_and_situations,
    format_phone_display,
    instance_name_for,
    resolve_alert,
    upsert_alert,
)
from apps.companies.models import Company

logger = logging.getLogger(__name__)


@dataclass
class HealthSnapshot:
    steps: list[dict]
    ok: bool
    checked_at: str


class ConnectionService:
    MODE_HOSTED = "hosted"
    MODE_BYO = "byo"

    @staticmethod
    def hosted_available() -> bool:
        return bool(settings.EVOLUTION_HOSTED_BASE_URL and settings.EVOLUTION_HOSTED_API_KEY)

    @staticmethod
    def connection_options() -> dict:
        return {
            "hosted_available": ConnectionService.hosted_available(),
            "modes": [
                {
                    "id": ConnectionService.MODE_HOSTED,
                    "title": "Conectar de forma simples",
                    "description": "Recomendado se você não tem servidor próprio. Só escaneie o QR Code.",
                    "available": ConnectionService.hosted_available(),
                },
                {
                    "id": ConnectionService.MODE_BYO,
                    "title": "Já tenho Evolution",
                    "description": "Use o servidor que você já instalou. Vamos pedir o endereço e a chave.",
                    "available": True,
                },
            ],
        }

    @staticmethod
    def get_whatsapp(*, tenant: Company) -> CommunicationConnection | None:
        return (
            CommunicationConnection.all_objects.filter(
                tenant=tenant,
                channel=Channel.WHATSAPP,
                role=ConnectionRole.DEFAULT,
            )
            .order_by("-created_at")
            .first()
        )

    @staticmethod
    def _webhook_url(provider_key: str) -> str | None:
        base = getattr(settings, "PUBLIC_API_BASE_URL", None) or getattr(
            settings, "API_PUBLIC_BASE_URL", None
        )
        if not base:
            # local: o comerciante precisa de URL pública pra webhook — ainda provisiona sem
            return None
        return f"{base.rstrip('/')}/api/v1/webhooks/communications/{provider_key}/"

    @staticmethod
    def build_ctx(connection: CommunicationConnection) -> ConnectionContext:
        creds = open_credentials(connection.credentials_signed)
        meta = dict(connection.provider_metadata or {})
        instance = meta.get("instance_name") or instance_name_for(connection)
        meta.setdefault("instance_name", instance)
        return ConnectionContext(
            connection_id=str(connection.id),
            tenant_id=str(connection.tenant_id),
            base_url=creds.get("base_url", ""),
            api_key=creds.get("api_key", ""),
            instance_name=instance,
            provider_metadata=meta,
            webhook_url=ConnectionService._webhook_url(connection.provider_key),
        )

    @staticmethod
    @transaction.atomic
    def start_whatsapp_connection(
        *,
        tenant: Company,
        mode: str = MODE_BYO,
        base_url: str = "",
        api_key: str = "",
        provider_key: str = ProviderKey.EVOLUTION,
    ) -> CommunicationConnection:
        mode = (mode or ConnectionService.MODE_BYO).strip().lower()
        if mode == ConnectionService.MODE_HOSTED:
            if not ConnectionService.hosted_available():
                raise CommConnectionError(
                    "A conexão simples ainda não está disponível. "
                    "Use a opção com Evolution própria ou fale com o suporte.",
                )
            base_url = settings.EVOLUTION_HOSTED_BASE_URL
            api_key = settings.EVOLUTION_HOSTED_API_KEY
        else:
            mode = ConnectionService.MODE_BYO
            base_url = (base_url or "").strip().rstrip("/")
            api_key = (api_key or "").strip()
            if not base_url or not api_key:
                raise CommConnectionError("Informe o endereço e a chave de acesso.")

        provider = get_provider(provider_key)
        validation = provider.validate_credentials(base_url=base_url, api_key=api_key)
        if not validation.ok:
            raise CommConnectionError(human_error(validation.error_code))

        connection = ConnectionService.get_whatsapp(tenant=tenant)
        if connection is None:
            connection = CommunicationConnection.all_objects.create(
                tenant=tenant,
                channel=Channel.WHATSAPP,
                provider_key=provider_key,
                role=ConnectionRole.DEFAULT,
                status=ConnectionStatus.PENDING,
            )
        else:
            connection.provider_key = provider_key
            connection.status = ConnectionStatus.PENDING
            connection.last_error_code = ""

        connection.credentials_signed = seal_credentials(
            {"base_url": base_url, "api_key": api_key},
        )
        # instance nova se mudou de modo/servidor — evita órfão
        connection.provider_metadata = {
            **(connection.provider_metadata or {}),
            "instance_name": instance_name_for(connection),
            "connection_mode": mode,
        }
        connection.save()

        ensure_templates_and_situations(tenant=tenant)

        ctx = ConnectionService.build_ctx(connection)
        try:
            result = provider.provision(ctx)
        except EvolutionHttpError as exc:
            connection.status = ConnectionStatus.ERROR
            connection.last_error_code = exc.error_code
            connection.save(update_fields=["status", "last_error_code", "updated_at"])
            raise CommConnectionError(human_error(exc.error_code)) from exc

        meta = {**(connection.provider_metadata or {}), **(result.provider_metadata or {})}
        meta["connection_mode"] = mode
        connection.provider_metadata = meta
        connection.status = ConnectionStatus.AWAITING_QR
        connection.save(update_fields=["provider_metadata", "status", "updated_at"])
        return connection

    @staticmethod
    def get_qr(*, connection: CommunicationConnection) -> dict:
        provider = get_provider(connection.provider_key)
        ctx = ConnectionService.build_ctx(connection)
        try:
            qr = provider.get_qr(ctx)
        except EvolutionHttpError as exc:
            raise CommConnectionError(human_error(exc.error_code)) from exc

        # também confere se já conectou
        session = provider.get_session_status(ctx)
        if session.state == "connected":
            ConnectionService._mark_connected(connection, session.phone_e164)
            return {"status": "connected", "phone_display": connection.phone_display}

        if not qr:
            return {"status": connection.status, "qr_base64": None}

        if qr.image_base64:
            meta = dict(connection.provider_metadata or {})
            meta["last_qr_base64"] = qr.image_base64
            connection.provider_metadata = meta
            connection.save(update_fields=["provider_metadata", "updated_at"])

        return {
            "status": ConnectionStatus.AWAITING_QR,
            "qr_base64": qr.image_base64,
            "pairing_code": qr.code,
        }

    @staticmethod
    def refresh_session(*, connection: CommunicationConnection) -> CommunicationConnection:
        provider = get_provider(connection.provider_key)
        ctx = ConnectionService.build_ctx(connection)
        session = provider.get_session_status(ctx)
        if session.state == "connected":
            ConnectionService._mark_connected(connection, session.phone_e164)
        elif session.state == "disconnected":
            connection.status = ConnectionStatus.DISCONNECTED
            connection.save(update_fields=["status", "updated_at"])
            upsert_alert(
                tenant=connection.tenant,
                connection=connection,
                kind="whatsapp_disconnected",
                title="Seu WhatsApp foi desconectado.",
                action_hint="Reconectar WhatsApp",
            )
        return connection

    @staticmethod
    def _mark_connected(connection: CommunicationConnection, phone: str | None) -> None:
        connection.status = ConnectionStatus.CONNECTED
        if phone:
            connection.phone_e164 = phone
            connection.phone_display = format_phone_display(phone)
        connection.last_error_code = ""
        connection.save(
            update_fields=[
                "status",
                "phone_e164",
                "phone_display",
                "last_error_code",
                "updated_at",
            ],
        )
        resolve_alert(
            tenant=connection.tenant,
            connection=connection,
            kind="whatsapp_disconnected",
        )

    @staticmethod
    def run_health_check(*, connection: CommunicationConnection) -> HealthSnapshot:
        steps: list[dict] = []
        creds = open_credentials(connection.credentials_signed)
        base_url = creds.get("base_url", "")
        api_key = creds.get("api_key", "")

        # 1 servidor
        server_ok = bool(base_url)
        steps.append(
            {
                "key": "server",
                "label": "Servidor conectado" if server_ok else "Servidor",
                "ok": server_ok,
                "message": "" if server_ok else "Não encontramos o servidor nesse endereço.",
            },
        )

        provider = get_provider(connection.provider_key)
        # 2 credenciais
        cred_ok = False
        cred_msg = ""
        if server_ok:
            validation = provider.validate_credentials(base_url=base_url, api_key=api_key)
            cred_ok = validation.ok
            cred_msg = "" if cred_ok else human_error(validation.error_code)
        steps.append(
            {
                "key": "credentials",
                "label": (
                    "Servidor do sistema respondendo"
                    if (connection.provider_metadata or {}).get("connection_mode")
                    == ConnectionService.MODE_HOSTED
                    else (
                        "Evolution respondendo"
                        if connection.provider_key == "evolution"
                        else "Acesso validado"
                    )
                ),
                "ok": cred_ok,
                "message": cred_msg,
            },
        )

        # 3+4 sessão
        session_ok = False
        session_msg = ""
        messaging_ok = False
        if cred_ok:
            ctx = ConnectionService.build_ctx(connection)
            session = provider.get_session_status(ctx)
            session_ok = session.state == "connected"
            if session_ok and session.phone_e164 and not connection.phone_e164:
                ConnectionService._mark_connected(connection, session.phone_e164)
            elif session.state == "disconnected":
                connection.status = ConnectionStatus.DISCONNECTED
                connection.save(update_fields=["status", "updated_at"])
                session_msg = human_error("session_disconnected")
            elif not session_ok:
                session_msg = "WhatsApp ainda não está conectado."
            messaging_ok = session_ok
        steps.append(
            {
                "key": "session",
                "label": "WhatsApp conectado",
                "ok": session_ok,
                "message": session_msg,
            },
        )
        steps.append(
            {
                "key": "messaging",
                "label": "Comunicação funcionando",
                "ok": messaging_ok,
                "message": "" if messaging_ok else "Não conseguimos enviar mensagens ainda.",
            },
        )

        ok = all(s["ok"] for s in steps)
        snapshot = {
            "steps": steps,
            "ok": ok,
        }
        connection.last_health_at = timezone.now()
        connection.last_health_status = snapshot
        connection.save(update_fields=["last_health_at", "last_health_status", "updated_at"])

        if not session_ok and connection.status == ConnectionStatus.CONNECTED:
            upsert_alert(
                tenant=connection.tenant,
                connection=connection,
                kind="whatsapp_disconnected",
                title="Seu WhatsApp foi desconectado.",
                action_hint="Reconectar WhatsApp",
            )

        return HealthSnapshot(
            steps=steps,
            ok=ok,
            checked_at=connection.last_health_at.isoformat(),
        )

    @staticmethod
    @transaction.atomic
    def disconnect(*, connection: CommunicationConnection) -> CommunicationConnection:
        provider = get_provider(connection.provider_key)
        ctx = ConnectionService.build_ctx(connection)
        try:
            provider.disconnect(ctx)
        except Exception:
            logger.info("falha ao desconectar no provider — marca local mesmo")
        connection.status = ConnectionStatus.DISCONNECTED
        connection.save(update_fields=["status", "updated_at"])
        return connection

    @staticmethod
    def apply_webhook_events(*, connection: CommunicationConnection, events: list) -> None:
        for event in events:
            if event.kind == "qr_updated":
                base64 = (event.payload or {}).get("base64")
                if base64:
                    meta = dict(connection.provider_metadata or {})
                    meta["last_qr_base64"] = base64
                    connection.provider_metadata = meta
                    connection.status = ConnectionStatus.AWAITING_QR
                    connection.save(
                        update_fields=["provider_metadata", "status", "updated_at"],
                    )
            elif event.kind == "connection_update":
                state = str((event.payload or {}).get("state") or "").lower()
                phone = (event.payload or {}).get("phone")
                if state in ("open", "connected"):
                    phone_digits = None
                    if phone:
                        phone_digits = "".join(c for c in str(phone) if c.isdigit()).split("@")[0]
                    ConnectionService._mark_connected(connection, phone_digits)
                elif state in ("close", "closed", "disconnected"):
                    connection.status = ConnectionStatus.DISCONNECTED
                    connection.save(update_fields=["status", "updated_at"])
                    upsert_alert(
                        tenant=connection.tenant,
                        connection=connection,
                        kind="whatsapp_disconnected",
                        title="Seu WhatsApp foi desconectado.",
                        action_hint="Reconectar WhatsApp",
                    )
