from __future__ import annotations

from django.db import transaction

from apps.communications.domain.catalog import SITUATION_CATALOG
from apps.communications.domain.enums import Channel, PHASE1_EVENT_KEYS
from apps.communications.domain.exceptions import TemplateValidationError
from apps.communications.models import MessageTemplate, SituationSetting
from apps.communications.services.helpers import ensure_templates_and_situations
from apps.communications.services.renderer import validate_body
from apps.companies.models import Company


class TemplateService:
    @staticmethod
    def list_situations(*, tenant: Company) -> list[dict]:
        ensure_templates_and_situations(tenant=tenant)
        settings = {
            s.event_key: s
            for s in SituationSetting.all_objects.filter(tenant=tenant, channel=Channel.WHATSAPP)
        }
        templates = {
            t.event_key: t
            for t in MessageTemplate.all_objects.filter(tenant=tenant, channel=Channel.WHATSAPP)
        }
        rows = []
        for event_key in PHASE1_EVENT_KEYS:
            meta = SITUATION_CATALOG[event_key]
            st = settings.get(event_key)
            tpl = templates.get(event_key)
            rows.append(
                {
                    "event_key": event_key,
                    "title": meta["title"],
                    "description": meta["description"],
                    "is_enabled": st.is_enabled if st else True,
                    "variables": meta["variables"],
                    "body_preview": (tpl.body[:120] if tpl else meta["seed"][:120]),
                },
            )
        return rows

    @staticmethod
    def get_template(*, tenant: Company, event_key: str) -> MessageTemplate:
        ensure_templates_and_situations(tenant=tenant)
        if event_key not in SITUATION_CATALOG:
            raise TemplateValidationError("Situação desconhecida.")
        return MessageTemplate.all_objects.get(
            tenant=tenant,
            channel=Channel.WHATSAPP,
            event_key=event_key,
        )

    @staticmethod
    @transaction.atomic
    def save_template(*, tenant: Company, event_key: str, body: str) -> MessageTemplate:
        meta = SITUATION_CATALOG.get(event_key)
        if not meta:
            raise TemplateValidationError("Situação desconhecida.")
        validate_body(body, meta["variables"])
        tpl, _ = MessageTemplate.all_objects.update_or_create(
            tenant=tenant,
            channel=Channel.WHATSAPP,
            event_key=event_key,
            defaults={"body": body.strip(), "is_system_seed": False},
        )
        return tpl

    @staticmethod
    @transaction.atomic
    def bulk_set_enabled(*, tenant: Company, enabled_map: dict[str, bool]) -> None:
        ensure_templates_and_situations(tenant=tenant)
        for event_key, enabled in enabled_map.items():
            if event_key not in SITUATION_CATALOG:
                continue
            SituationSetting.all_objects.filter(
                tenant=tenant,
                channel=Channel.WHATSAPP,
                event_key=event_key,
            ).update(is_enabled=bool(enabled))
