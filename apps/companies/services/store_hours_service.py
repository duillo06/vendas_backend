from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from apps.companies.models import BusinessHours, Company
from apps.companies.services.settings_service import SettingsService


class StoreHoursService:
    @staticmethod
    def is_store_open(company: Company, now: datetime | None = None) -> bool:
        settings = SettingsService.get_for_tenant(company)

        if not settings.is_open:
            return False

        if not settings.auto_close_outside_hours:
            return True

        tz = ZoneInfo(company.timezone)
        current = (now or datetime.now(tz=tz)).astimezone(tz)

        today_hours = StoreHoursService._get_day_hours(company, current.weekday())
        if StoreHoursService._is_open_for_day(current.time(), today_hours):
            return True

        # madrugada pode ser continuação do horário de ontem
        yesterday = current - timedelta(days=1)
        yesterday_hours = StoreHoursService._get_day_hours(company, yesterday.weekday())
        if (
            yesterday_hours
            and not yesterday_hours.is_closed
            and yesterday_hours.closes_at < yesterday_hours.opens_at
            and current.time() <= yesterday_hours.closes_at
        ):
            return True

        return False

    @staticmethod
    def _get_day_hours(company: Company, day_of_week: int) -> BusinessHours | None:
        return BusinessHours.all_objects.filter(
            tenant=company,
            day_of_week=day_of_week,
        ).first()

    @staticmethod
    def _is_open_for_day(current: time, day_hours: BusinessHours | None) -> bool:
        if day_hours is None or day_hours.is_closed:
            return False

        return StoreHoursService._is_time_within_hours(
            current,
            day_hours.opens_at,
            day_hours.closes_at,
        )

    @staticmethod
    def _is_time_within_hours(current: time, opens_at: time, closes_at: time) -> bool:
        if closes_at > opens_at:
            return opens_at <= current <= closes_at

        if closes_at < opens_at:
            # cruza meia-noite (ex: 18h às 2h)
            return current >= opens_at or current <= closes_at

        return current == opens_at
