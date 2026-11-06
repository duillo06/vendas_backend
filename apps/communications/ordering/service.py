from __future__ import annotations

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.communications.models import CommunicationConnection, WhatsAppOrderSession
from apps.communications.ordering.machine import (
    choice_from_reply,
    consume,
    fresh_draft,
    place_order,
    prompt,
    render,
    touch_expiry,
)
from apps.companies.services.store_hours_service import StoreHoursService
from apps.orders.domain.exceptions import DomainException
from core.tenancy.context import TenantContext

logger = logging.getLogger(__name__)

CANCEL_WORDS = {"cancelar", "cancela", "sair", "parar"}


def national_phone(digits: str) -> str:
    # WhatsApp manda com 55; o cadastro do cliente usa DDD + número
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]
    # celular antigo vem sem o 9 (DDD + 8). O cadastro exige o 9.
    if len(digits) == 10 and digits[2] in "6789":
        digits = digits[:2] + "9" + digits[2:]
    return digits


class OrderingService:
    @staticmethod
    def handle_inbound(
        *,
        connection: CommunicationConnection,
        phone: str,
        message_id: str = "",
        text: str = "",
        selected_id: str = "",
        push_name: str = "",
    ) -> list:
        if not connection.ordering_enabled:
            return []
        phone = "".join(ch for ch in (phone or "") if ch.isdigit())
        if len(phone) < 10:
            return []

        tenant = connection.tenant
        TenantContext.set(tenant)
        try:
            return OrderingService._handle(
                connection=connection,
                tenant=tenant,
                phone=phone,
                message_id=message_id,
                text=text or "",
                selected_id=selected_id or "",
                push_name=push_name or "",
            )
        finally:
            TenantContext.clear()

    @staticmethod
    @transaction.atomic
    def _handle(*, connection, tenant, phone, message_id, text, selected_id, push_name) -> list:
        if not StoreHoursService.is_store_open(tenant):
            return [_closed_reply()]

        session = (
            WhatsAppOrderSession.all_objects.select_for_update()
            .filter(tenant=tenant, phone=phone, closed_at__isnull=True)
            .first()
        )
        now = timezone.now()
        if session and session.expires_at <= now:
            session.closed_at = now
            session.save(update_fields=["closed_at", "updated_at"])
            session = None
            expired = True
        else:
            expired = False

        opened_now = session is None
        if session is None:
            session = WhatsAppOrderSession.all_objects.create(
                tenant=tenant,
                connection=connection,
                phone=phone,
                step="menu",
                draft=fresh_draft(push_name),
                seen_message_ids=[],
                expires_at=now + timezone.timedelta(minutes=30),
            )
        elif push_name and not session.draft.get("push_name"):
            session.draft["push_name"] = push_name.strip()

        if message_id:
            seen = list(session.seen_message_ids or [])
            if message_id in seen:
                return []
            seen.append(message_id)
            session.seen_message_ids = seen[-30:]

        folded = text.strip().casefold()
        if folded in CANCEL_WORDS:
            session.closed_at = now
            session.save()
            return [_text("Pedido cancelado. Quando quiser, é só chamar de novo.")]

        if expired:
            session.draft["hint"] = "Vamos recomeçar."

        current = prompt(session, tenant)
        choice = selected_id or choice_from_reply(current, text)
        # oi só abre o cardápio — não é resposta errada
        if not (opened_now and not choice):
            consume(session, tenant, choice=choice, text=text)

        if session.draft.get("confirm"):
            reply = _confirm(session, phone)
            session.draft.pop("confirm", None)
            if session.closed_at:
                session.save()
                return [reply]
            touch_expiry(session)
            session.save()
            return [reply, render(session, tenant)]

        touch_expiry(session)
        session.save()
        return [render(session, tenant)]

    @staticmethod
    def set_enabled(*, connection: CommunicationConnection, enabled: bool) -> CommunicationConnection:
        connection.ordering_enabled = enabled
        connection.save(update_fields=["ordering_enabled", "updated_at"])
        return connection


def _confirm(session, phone: str):
    try:
        order = place_order(session, national_phone(phone))
    except DomainException as exc:
        return _text(exc.message)
    except (ValidationError, DjangoValidationError) as exc:
        return _text(_validation_message(exc))
    except Exception:
        logger.exception("falha ao gravar pedido do WhatsApp")
        return _text("Não consegui registrar o pedido. Tenta confirmar de novo.")

    session.closed_at = timezone.now()
    session.step = "done"
    return _text(
        f"Pedido {order.order_number} recebido! "
        "Avisamos por aqui quando o status mudar."
    )


def _validation_message(exc) -> str:
    messages = getattr(exc, "messages", None)
    if messages and not getattr(exc, "detail", None):
        return " ".join(str(item) for item in messages)
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        parts = []
        for value in detail.values():
            if isinstance(value, list) and value:
                parts.append(str(value[0]))
            else:
                parts.append(str(value))
        return " ".join(parts) or "Confere os dados e tenta de novo."
    if isinstance(detail, list) and detail:
        return str(detail[0])
    return str(detail)


def _closed_reply():
    return _text("A loja está fechada agora. Quando abrir, é só chamar de novo.")


def _text(body: str):
    from apps.communications.ordering.replies import Reply

    return Reply(body=body)

