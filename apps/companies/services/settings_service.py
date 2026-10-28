from typing import Any

from django.core.exceptions import ValidationError

from apps.companies.domain.print_settings import normalize_print_settings
from apps.companies.models import Company, CompanySettings
from apps.locations.services import LocationCatalogService


def _delivery_window(raw_min, raw_max) -> tuple[int | None, int | None]:
    empty = (None, "")
    if raw_min in empty and raw_max in empty:
        return None, None
    if raw_min in empty or raw_max in empty:
        raise ValidationError("Informe o tempo mínimo e o máximo da entrega")
    try:
        low = int(raw_min)
        high = int(raw_max)
    except (TypeError, ValueError):
        raise ValidationError("Informe o tempo de entrega em minutos") from None
    if low < 5 or high > 240 or high < low:
        raise ValidationError(
            "O tempo de entrega vai de 5 a 240 minutos, e o máximo precisa ser maior ou igual ao mínimo"
        )
    return low, high


class SettingsService:
    @staticmethod
    def get_for_tenant(company: Company) -> CompanySettings:
        return CompanySettings.all_objects.select_related(
            "delivery_city_ref__state",
        ).get(tenant=company)

    @staticmethod
    def update(company: Company, **fields: Any) -> CompanySettings:
        settings = SettingsService.get_for_tenant(company)
        missing = object()
        city_id = fields.pop("delivery_city_id", missing)
        state_id = fields.pop("delivery_state_id", None)
        has_city_id = city_id is not missing

        # o id da cidade define nome e estado, sem deixar combinações inválidas
        if has_city_id and city_id not in (None, ""):
            try:
                city = LocationCatalogService.get_city(
                    city_id=int(city_id),
                    state_id=int(state_id) if state_id not in (None, "") else None,
                )
            except (TypeError, ValueError):
                raise ValidationError("Escolha uma cidade válida") from None
            settings.delivery_city_ref = city
            settings.delivery_city = city.name
            settings.delivery_state = city.state.acronym
            fields.pop("delivery_city", None)
            fields.pop("delivery_state", None)
        elif has_city_id:
            settings.delivery_city_ref = None
            settings.delivery_city = ""
            settings.delivery_state = ""

        if "delivery_time_min" in fields or "delivery_time_max" in fields:
            low, high = _delivery_window(
                fields.get("delivery_time_min"),
                fields.get("delivery_time_max"),
            )
            fields["delivery_time_min"] = low
            fields["delivery_time_max"] = high

        allowed = {
            "min_order_value",
            "delivery_fee",
            "free_delivery_above",
            "estimated_prep_time",
            "estimated_delivery_time",
            "delivery_time_min",
            "delivery_time_max",
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
            "print_settings",
            "setup",
        }

        for key, value in fields.items():
            if key not in allowed:
                continue
            if key == "print_settings":
                value = normalize_print_settings(value)
            setattr(settings, key, value)

        if not has_city_id and {"delivery_city", "delivery_state"} <= fields.keys():
            city = LocationCatalogService.find_city(
                city_name=str(fields["delivery_city"]),
                state_acronym=str(fields["delivery_state"]),
            )
            settings.delivery_city_ref = city

        settings.save()
        return settings
