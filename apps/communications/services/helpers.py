from __future__ import annotations

from django.utils import timezone

from apps.communications.domain.catalog import SITUATION_CATALOG, human_error
from apps.communications.domain.enums import (
    AlertSeverity,
    Channel,
    ConnectionRole,
    ConnectionStatus,
    PHASE1_EVENT_KEYS,
)
from apps.communications.models import (
    CommunicationConnection,
    MerchantAlert,
    MessageTemplate,
    SituationSetting,
)
from apps.companies.models import Company


def ensure_templates_and_situations(*, tenant: Company, channel: str = Channel.WHATSAPP) -> None:
    for event_key, meta in SITUATION_CATALOG.items():
        MessageTemplate.all_objects.get_or_create(
            tenant=tenant,
            channel=channel,
            event_key=event_key,
            defaults={"body": meta["seed"], "is_system_seed": True},
        )
        SituationSetting.all_objects.get_or_create(
            tenant=tenant,
            channel=channel,
            event_key=event_key,
            defaults={"is_enabled": True},
        )


def upsert_alert(
    *,
    tenant: Company,
    connection: CommunicationConnection | None,
    kind: str,
    title: str,
    body: str = "",
    action_hint: str = "",
    severity: str = AlertSeverity.WARNING,
) -> MerchantAlert:
    # evita spam do mesmo problema aberto
    existing = (
        MerchantAlert.all_objects.filter(
            tenant=tenant,
            connection=connection,
            kind=kind,
            resolved_at__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )
    if existing:
        existing.title = title
        existing.body = body
        existing.action_hint = action_hint
        existing.severity = severity
        existing.save(
            update_fields=["title", "body", "action_hint", "severity", "updated_at"],
        )
        return existing

    return MerchantAlert.all_objects.create(
        tenant=tenant,
        connection=connection,
        kind=kind,
        title=title,
        body=body,
        action_hint=action_hint,
        severity=severity,
    )


def resolve_alert(*, tenant: Company, connection: CommunicationConnection, kind: str) -> None:
    MerchantAlert.all_objects.filter(
        tenant=tenant,
        connection=connection,
        kind=kind,
        resolved_at__isnull=True,
    ).update(resolved_at=timezone.now(), is_read=True)


def format_phone_display(e164: str) -> str:
    digits = "".join(c for c in (e164 or "") if c.isdigit())
    if len(digits) >= 11 and digits.startswith("55"):
        local = digits[2:]
        if len(local) == 11:
            return f"({local[:2]}) {local[2:7]}-{local[7:]}"
        if len(local) == 10:
            return f"({local[:2]}) {local[2:6]}-{local[6:]}"
    return e164 or ""


def instance_name_for(connection: CommunicationConnection) -> str:
    short_tenant = str(connection.tenant_id).replace("-", "")[:8]
    short_conn = str(connection.id).replace("-", "")[:8]
    return f"fs_{short_tenant}_{short_conn}"


__all__ = [
    "ensure_templates_and_situations",
    "upsert_alert",
    "resolve_alert",
    "format_phone_display",
    "instance_name_for",
    "PHASE1_EVENT_KEYS",
    "ConnectionStatus",
    "ConnectionRole",
    "Channel",
    "human_error",
]
