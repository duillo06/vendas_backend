from datetime import time

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
