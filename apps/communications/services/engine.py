from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.communications.domain.catalog import PREVIEW_SAMPLES, SITUATION_CATALOG
from apps.communications.domain.enums import (
    Channel,
    ConnectionStatus,
    DispatchStatus,
    ORDER_STATUS_TO_EVENT,
)
from apps.communications.models import (
    CommunicationConnection,
    MessageDispatch,
    MessageTemplate,
    SituationSetting,
)
from apps.communications.services.connection_service import ConnectionService
from apps.communications.services.renderer import render
from apps.companies.models import Company

logger = logging.getLogger(__name__)


@dataclass
class CommunicationEvent:
    tenant_id: str
    event_key: str
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""
    aggregate_type: str = ""
    aggregate_id: str = ""


@dataclass
class DispatchAck:
    accepted: bool
    dispatch_id: str | None = None
    reason: str = ""


class CommunicationEngine:
    @staticmethod
    def handle(event: CommunicationEvent) -> DispatchAck:
        tenant = Company.objects.filter(id=event.tenant_id).first()
        if not tenant:
            return DispatchAck(accepted=False, reason="tenant_missing")

        setting = SituationSetting.all_objects.filter(
            tenant=tenant,
            channel=Channel.WHATSAPP,
            event_key=event.event_key,
        ).first()
        if setting and not setting.is_enabled:
            return DispatchAck(accepted=False, reason="situation_disabled")

        # se ainda não seedou, não dispara
        if setting is None and event.event_key not in SITUATION_CATALOG:
            return DispatchAck(accepted=False, reason="unknown_event")

        connection = ConnectionService.get_whatsapp(tenant=tenant)
        if not connection or connection.status != ConnectionStatus.CONNECTED:
            return DispatchAck(accepted=False, reason="not_connected")

        if event.idempotency_key:
            existing = MessageDispatch.all_objects.filter(
                tenant=tenant,
                idempotency_key=event.idempotency_key,
            ).first()
            if existing:
                return DispatchAck(accepted=True, dispatch_id=str(existing.id), reason="idempotent")

        template = MessageTemplate.all_objects.filter(
            tenant=tenant,
            channel=Channel.WHATSAPP,
            event_key=event.event_key,
        ).first()
        if not template:
            meta = SITUATION_CATALOG.get(event.event_key)
            if not meta:
                return DispatchAck(accepted=False, reason="no_template")
            template = MessageTemplate.all_objects.create(
                tenant=tenant,
                channel=Channel.WHATSAPP,
                event_key=event.event_key,
                body=meta["seed"],
                is_system_seed=True,
            )

        body = render(template.body, event.payload)
        recipient = str(event.payload.get("customer_phone") or "").strip()
        if not recipient:
            return DispatchAck(accepted=False, reason="no_recipient")

        dispatch = MessageDispatch.all_objects.create(
            tenant=tenant,
            connection=connection,
            channel=Channel.WHATSAPP,
            event_key=event.event_key,
            template=template,
            status=DispatchStatus.QUEUED,
            recipient=recipient,
            body_snapshot=body,
            idempotency_key=event.idempotency_key or "",
            payload_snapshot=event.payload,
            is_test=False,
        )

        transaction.on_commit(
            lambda: _enqueue_send(str(dispatch.id)),
        )
        return DispatchAck(accepted=True, dispatch_id=str(dispatch.id))

    @staticmethod
    def send_test(
        *,
        connection: CommunicationConnection,
        body: str,
        to_e164: str | None = None,
    ) -> MessageDispatch:
        from apps.communications.infrastructure.providers.registry import get_provider
        from apps.communications.domain.catalog import human_error
        from apps.communications.infrastructure.providers.evolution.client import EvolutionHttpError

        recipient = (to_e164 or connection.phone_e164 or "").strip()
        # se conectou mas o número ainda não gravou, busca na Evolution
        if not recipient and connection.status == ConnectionStatus.CONNECTED:
            ConnectionService.refresh_session(connection=connection)
            connection.refresh_from_db()
            recipient = (connection.phone_e164 or "").strip()
        if not recipient:
            raise ValueError(
                "Ainda não identificamos o número do WhatsApp. "
                "Aguarde alguns segundos e tente de novo.",
            )

        provider = get_provider(connection.provider_key)
        ctx = ConnectionService.build_ctx(connection)
        dispatch = MessageDispatch.all_objects.create(
            tenant=connection.tenant,
            connection=connection,
            channel=Channel.WHATSAPP,
            event_key="connection.test",
            status=DispatchStatus.PENDING,
            recipient=recipient,
            body_snapshot=body,
            is_test=True,
        )
        started = timezone.now()
        try:
            result = provider.send_text(ctx, to_e164=recipient, body=body)
            dispatch.status = DispatchStatus.SENT
            dispatch.provider_message_id = result.provider_message_id or ""
            dispatch.sent_at = timezone.now()
            dispatch.latency_ms = int((dispatch.sent_at - started).total_seconds() * 1000)
            dispatch.save()
        except EvolutionHttpError as exc:
            dispatch.status = DispatchStatus.FAILED
            dispatch.error_code = exc.error_code
            dispatch.error_message = human_error(exc.error_code)
            dispatch.save()
            raise ValueError(human_error(exc.error_code)) from exc
        except Exception as exc:
            dispatch.status = DispatchStatus.FAILED
            dispatch.error_code = "send_failed"
            dispatch.error_message = human_error("send_failed")
            dispatch.save()
            raise ValueError(human_error("send_failed")) from exc
        return dispatch

    @staticmethod
    def preview(*, body: str, company_name: str = "") -> str:
        payload = dict(PREVIEW_SAMPLES)
        if company_name:
            payload["company_name"] = company_name
        return render(body, payload)


def _enqueue_send(dispatch_id: str) -> None:
    from apps.communications.tasks import send_dispatch

    send_dispatch.delay(dispatch_id)


def emit_order_status_event(*, order) -> None:
    """chamado pelo OrderService — fail soft"""
    try:
        event_key = ORDER_STATUS_TO_EVENT.get(order.status)
        if not event_key:
            return

        customer = order.customer
        phone = ""
        customer_name = "Cliente"
        if customer is not None:
            phone = _to_e164_br(getattr(customer, "phone", "") or "")
            customer_name = (
                f"{getattr(customer, 'first_name', '')} {getattr(customer, 'last_name', '')}".strip()
                or "Cliente"
            )

        total = getattr(order, "total", None) or getattr(order, "grand_total", None) or 0
        payload = {
            "customer_name": customer_name,
            "customer_phone": phone,
            "order_number": order.order_number,
            "total_formatted": f"R$ {total:.2f}".replace(".", ","),
            "eta_text": "em breve",
            "company_name": order.tenant.trade_name,
            "delivery_address": "",
            "payment_method_label": "",
        }
        if hasattr(order, "delivery_address") and order.delivery_address:
            payload["delivery_address"] = str(order.delivery_address)

        CommunicationEngine.handle(
            CommunicationEvent(
                tenant_id=str(order.tenant_id),
                event_key=event_key,
                payload=payload,
                idempotency_key=f"order:{order.id}:{order.status}",
                aggregate_type="order",
                aggregate_id=str(order.id),
            ),
        )
    except Exception:
        logger.exception("falha ao emitir comunicação do pedido %s", getattr(order, "id", "?"))


def _to_e164_br(phone: str) -> str:
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if not digits:
        return ""
    if digits.startswith("55"):
        return digits
    if len(digits) in (10, 11):
        return f"55{digits}"
    return digits
