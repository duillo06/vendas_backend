from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.companies.models import BusinessHours, Company, CompanySettings
from apps.companies.services.business_hours_service import BusinessHoursService
from apps.companies.services.first_setup_service import FirstSetupService
from apps.companies.services.settings_service import SettingsService
from core.utils.media import absolutize_media_url

COMPANY_FIELDS = {"legal_name", "trade_name", "document", "email", "phone", "description"}


class CompanyAdminService:
    @staticmethod
    def _serialize_settings(settings: CompanySettings) -> dict:
        return {
            "min_order_value": float(settings.min_order_value),
            "delivery_fee": float(settings.delivery_fee),
            "free_delivery_above": (
                float(settings.free_delivery_above)
                if settings.free_delivery_above is not None
                else None
            ),
            "estimated_prep_time": settings.estimated_prep_time,
            "estimated_delivery_time": settings.estimated_delivery_time,
            "accepts_delivery": settings.accepts_delivery,
            "accepts_pickup": settings.accepts_pickup,
            "is_open": settings.is_open,
            "auto_close_outside_hours": settings.auto_close_outside_hours,
            "payment_methods": settings.payment_methods,
            "theme": settings.theme,
            "setup": FirstSetupService.normalize(settings.setup),
        }

    @staticmethod
    def _serialize_company(company: Company) -> dict:
        return {
            "legal_name": company.legal_name,
            "trade_name": company.trade_name,
            "document": company.document,
            "email": company.email,
            "phone": company.phone,
            "description": company.description,
            "logo_url": absolutize_media_url(company.logo_url),
            "cover_url": absolutize_media_url(company.cover_url),
        }

    @staticmethod
    def _serialize_hours(hours: list[BusinessHours]) -> list[dict]:
        return [
            {
                "day_of_week": row.day_of_week,
                "opens_at": row.opens_at.strftime("%H:%M"),
                "closes_at": row.closes_at.strftime("%H:%M"),
                "is_closed": row.is_closed,
            }
            for row in hours
        ]

    @staticmethod
    def get_settings_payload(company: Company) -> dict:
        settings = SettingsService.get_for_tenant(company)
        hours = list(BusinessHours.all_objects.filter(tenant=company).order_by("day_of_week"))

        return {
            "company": CompanyAdminService._serialize_company(company),
            "settings": CompanyAdminService._serialize_settings(settings),
            "business_hours": CompanyAdminService._serialize_hours(hours),
        }

    @staticmethod
    @transaction.atomic
    def update_settings(company: Company, data: dict[str, Any]) -> dict:
        company_data = data.get("company")
        if company_data:
            if not isinstance(company_data, dict):
                raise ValidationError("company deve ser um objeto")

            for key, value in company_data.items():
                if key not in COMPANY_FIELDS:
                    raise ValidationError(f"Campo de empresa inválido: {key}")
                setattr(company, key, value)
            company.save()

        settings_data = data.get("settings")
        if settings_data:
            if not isinstance(settings_data, dict):
                raise ValidationError("settings deve ser um objeto")
            SettingsService.update(company, **settings_data)

        hours_data = data.get("business_hours")
        if hours_data:
            if not isinstance(hours_data, list):
                raise ValidationError("business_hours deve ser uma lista")
            BusinessHoursService.update_for_tenant(company, hours_data)

        return CompanyAdminService.get_settings_payload(company)
