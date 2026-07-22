from typing import Any

from apps.companies.models import Company, CompanySettings


class SettingsService:
    @staticmethod
    def get_for_tenant(company: Company) -> CompanySettings:
        return CompanySettings.all_objects.get(tenant=company)

    @staticmethod
    def update(company: Company, **fields: Any) -> CompanySettings:
        settings = SettingsService.get_for_tenant(company)

        allowed = {
            "min_order_value",
            "delivery_fee",
            "free_delivery_above",
            "estimated_prep_time",
            "estimated_delivery_time",
            "accepts_delivery",
            "accepts_pickup",
            "accepts_dine_in",
            "is_open",
            "auto_close_outside_hours",
            "payment_methods",
            "delivery_areas",
            "delivery_city",
            "delivery_state",
            "theme",
            "notification_settings",
            "setup",
        }

        for key, value in fields.items():
            if key in allowed:
                setattr(settings, key, value)

        settings.save()
        return settings
