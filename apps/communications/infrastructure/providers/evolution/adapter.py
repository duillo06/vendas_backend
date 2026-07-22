from __future__ import annotations

import json
import logging
import re
from typing import Any

from apps.communications.domain.ports import (
    ConnectionContext,
    ProviderEvent,
    ProvisionResult,
    QrPayload,
    SendResult,
    SessionStatus,
    ValidationResult,
)
from apps.communications.infrastructure.providers.evolution.client import (
    EvolutionHttpClient,
    EvolutionHttpError,
)

logger = logging.getLogger(__name__)


def _digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


class EvolutionWhatsAppAdapter:
    provider_key = "evolution"

    def _client(self, base_url: str, api_key: str) -> EvolutionHttpClient:
        return EvolutionHttpClient(base_url, api_key)

    def validate_credentials(self, *, base_url: str, api_key: str) -> ValidationResult:
        try:
            client = self._client(base_url, api_key)
            # fetchInstances é leve e valida a chave na maioria das versões
            status, _ = client.request("GET", "/instance/fetchInstances")
            if status in (200, 201):
                return ValidationResult(ok=True)
            if status in (401, 403):
                return ValidationResult(ok=False, error_code="credentials_invalid")
            return ValidationResult(ok=False, error_code="unknown")
        except EvolutionHttpError as exc:
            return ValidationResult(ok=False, error_code=exc.error_code)

    def provision(self, ctx: ConnectionContext) -> ProvisionResult:
        client = self._client(ctx.base_url, ctx.api_key)
        instance = ctx.instance_name
        body: dict[str, Any] = {
            "instanceName": instance,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS",
        }
        if ctx.webhook_url:
            body["webhook"] = {
                "enabled": True,
                "url": ctx.webhook_url,
                "byEvents": False,
                "base64": True,
                "events": [
                    "QRCODE_UPDATED",
                    "CONNECTION_UPDATE",
                    "MESSAGES_UPDATE",
                    "SEND_MESSAGE",
                ],
            }

        try:
            status, data = client.request("POST", "/instance/create", body=body)
        except EvolutionHttpError as exc:
            raise EvolutionHttpError(exc.error_code) from exc

        # já existe → segue (idempotente o bastante pro fluxo)
        if status in (400, 403, 409) and "already" in json.dumps(data).lower():
            return ProvisionResult(provider_metadata={"instance_name": instance, "existed": True})

        if status not in (200, 201):
            code = "credentials_invalid" if status in (401, 403) else "unknown"
            raise EvolutionHttpError(code, status=status, detail=data)

        meta = {"instance_name": instance}
        if isinstance(data, dict):
            # algumas versões devolvem hash/token da instância
            hash_val = data.get("hash") or (data.get("instance") or {}).get("instanceId")
            if hash_val:
                meta["instance_token"] = str(hash_val)
            qr = data.get("qrcode") or {}
            if isinstance(qr, dict) and qr.get("base64"):
                meta["last_qr_base64"] = qr["base64"]
        return ProvisionResult(provider_metadata=meta)

    def get_qr(self, ctx: ConnectionContext) -> QrPayload | None:
        client = self._client(ctx.base_url, ctx.api_key)
        instance = ctx.instance_name
        cached = (ctx.provider_metadata or {}).get("last_qr_base64")
        try:
            status, data = client.request("GET", f"/instance/connect/{instance}")
        except EvolutionHttpError as exc:
            raise EvolutionHttpError(exc.error_code) from exc

        if status not in (200, 201):
            if cached:
                return QrPayload(image_base64=cached)
            raise EvolutionHttpError("unknown", status=status, detail=data)

        base64 = None
        code = None
        if isinstance(data, dict):
            base64 = data.get("base64") or (data.get("qrcode") or {}).get("base64")
            code = data.get("code") or (data.get("qrcode") or {}).get("code")
            if not base64 and data.get("pairingCode"):
                code = str(data["pairingCode"])
        if not base64 and cached:
            base64 = cached
        if not base64 and not code:
            return None
        return QrPayload(image_base64=base64, code=code)

    def get_session_status(self, ctx: ConnectionContext) -> SessionStatus:
        client = self._client(ctx.base_url, ctx.api_key)
        instance = ctx.instance_name
        try:
            status, data = client.request("GET", f"/instance/connectionState/{instance}")
        except EvolutionHttpError as exc:
            return SessionStatus(state="error", raw_state=exc.error_code)

        raw = ""
        phone = None
        if isinstance(data, dict):
            instance_data = data.get("instance") if isinstance(data.get("instance"), dict) else data
            raw = str(
                instance_data.get("state")
                or instance_data.get("connectionStatus")
                or data.get("state")
                or ""
            )
            phone = instance_data.get("owner") or instance_data.get("wuid") or data.get("phone")
            if phone:
                phone = _digits(str(phone).split("@")[0])

        raw_l = raw.lower()
        if raw_l in ("open", "connected", "online"):
            state = "connected"
        elif raw_l in ("close", "closed", "disconnected"):
            state = "disconnected"
        elif raw_l in ("connecting", "qr", "refused"):
            state = "pending_qr"
        else:
            state = "pending_qr" if status == 200 else "error"

        # connectionState muitas vezes não traz o número — busca no fetchInstances
        if state == "connected" and not phone:
            phone = self._resolve_phone(client, instance)

        return SessionStatus(state=state, phone_e164=phone, raw_state=raw or None)

    def _resolve_phone(self, client: EvolutionHttpClient, instance: str) -> str | None:
        try:
            status, data = client.request("GET", "/instance/fetchInstances")
        except EvolutionHttpError:
            return None
        if status not in (200, 201):
            return None
        rows = [r for r in (data if isinstance(data, list) else [data]) if isinstance(r, dict)]
        matched = None
        for row in rows:
            name = row.get("name") or row.get("instanceName")
            nested = row.get("instance") if isinstance(row.get("instance"), dict) else {}
            name = name or nested.get("instanceName")
            if name == instance:
                matched = row
                break
        if matched is None and len(rows) == 1:
            matched = rows[0]
        if not matched:
            return None
        nested = matched.get("instance") if isinstance(matched.get("instance"), dict) else {}
        jid = matched.get("ownerJid") or matched.get("owner") or matched.get("number") or nested.get(
            "ownerJid",
        )
        return _digits(str(jid).split("@")[0]) if jid else None

    def send_text(self, ctx: ConnectionContext, *, to_e164: str, body: str) -> SendResult:
        client = self._client(ctx.base_url, ctx.api_key)
        instance = ctx.instance_name
        number = _digits(to_e164)
        payload = {
            "number": number,
            "text": body,
        }
        try:
            status, data = client.request(
                "POST",
                f"/message/sendText/{instance}",
                body=payload,
            )
        except EvolutionHttpError as exc:
            raise EvolutionHttpError(exc.error_code) from exc

        if status not in (200, 201):
            raise EvolutionHttpError("send_failed", status=status, detail=data)

        msg_id = None
        if isinstance(data, dict):
            key = data.get("key") or {}
            msg_id = key.get("id") if isinstance(key, dict) else data.get("messageId")
        return SendResult(provider_message_id=str(msg_id) if msg_id else None, accepted=True)

    def disconnect(self, ctx: ConnectionContext) -> None:
        client = self._client(ctx.base_url, ctx.api_key)
        instance = ctx.instance_name
        try:
            client.request("DELETE", f"/instance/logout/{instance}")
        except EvolutionHttpError:
            logger.info("logout Evolution falhou — segue desconectando local")

    def parse_webhook(self, headers: dict, raw_body: bytes) -> list[ProviderEvent]:
        try:
            data = json.loads(raw_body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return []

        event_name = str(data.get("event") or data.get("type") or "").upper()
        payload = data.get("data") if isinstance(data.get("data"), dict) else data
        events: list[ProviderEvent] = []

        if "QRCODE" in event_name:
            qr = payload.get("qrcode") if isinstance(payload, dict) else None
            base64 = None
            if isinstance(qr, dict):
                base64 = qr.get("base64")
            elif isinstance(payload, dict):
                base64 = payload.get("base64")
            events.append(ProviderEvent(kind="qr_updated", payload={"base64": base64}))

        if "CONNECTION" in event_name:
            state = ""
            phone = None
            if isinstance(payload, dict):
                state = str(payload.get("state") or payload.get("status") or "")
                phone = payload.get("owner") or payload.get("wuid")
            events.append(
                ProviderEvent(
                    kind="connection_update",
                    payload={"state": state, "phone": phone, "raw": payload},
                )
            )

        if "MESSAGES_UPDATE" in event_name or "SEND_MESSAGE" in event_name:
            events.append(ProviderEvent(kind="message_ack", payload=payload if isinstance(payload, dict) else {}))

        return events
