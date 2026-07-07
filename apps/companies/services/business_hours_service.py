from datetime import datetime, time

from django.core.exceptions import ValidationError

from apps.companies.models import BusinessHours, Company


class BusinessHoursService:
    @staticmethod
    def create_defaults(company: Company) -> list[BusinessHours]:
        existing_days = set(
            BusinessHours.all_objects.filter(tenant=company).values_list("day_of_week", flat=True)
        )
        rows: list[BusinessHours] = []

        for day in range(7):
            if day in existing_days:
                continue

            is_sunday = day == 6
            rows.append(
                BusinessHours(
                    tenant=company,
                    day_of_week=day,
                    opens_at=time(11, 0),
                    closes_at=time(22, 0),
                    is_closed=is_sunday,
                )
            )

        if not rows:
            return []

        return BusinessHours.objects.bulk_create(rows)

    @staticmethod
    def _parse_time(value: str) -> time:
        try:
            return datetime.strptime(value, "%H:%M").time()
        except ValueError as exc:
            raise ValidationError(f"Horário inválido: {value}") from exc

    @staticmethod
    def update_for_tenant(company: Company, hours_data: list[dict]) -> list[BusinessHours]:
        for item in hours_data:
            day = item.get("day_of_week")
            if day is None or not 0 <= day <= 6:
                raise ValidationError("day_of_week deve ser entre 0 e 6")

            BusinessHours.all_objects.update_or_create(
                tenant=company,
                day_of_week=day,
                defaults={
                    "opens_at": BusinessHoursService._parse_time(item["opens_at"]),
                    "closes_at": BusinessHoursService._parse_time(item["closes_at"]),
                    "is_closed": bool(item.get("is_closed", False)),
                },
            )

        return list(BusinessHours.all_objects.filter(tenant=company).order_by("day_of_week"))
