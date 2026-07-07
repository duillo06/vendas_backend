from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from apps.companies.models import BusinessHours
from apps.companies.services.settings_service import SettingsService
from apps.companies.services.store_hours_service import StoreHoursService


@pytest.mark.django_db
def test_store_closed_when_manually_closed(demo_company):
    SettingsService.update(demo_company, is_open=False)

    assert StoreHoursService.is_store_open(demo_company) is False


@pytest.mark.django_db
def test_store_open_when_auto_close_disabled(demo_company):
    SettingsService.update(demo_company, auto_close_outside_hours=False)

    assert StoreHoursService.is_store_open(demo_company) is True


@pytest.mark.django_db
def test_store_closed_on_sunday(demo_company):
    tz = ZoneInfo(demo_company.timezone)
    sunday_noon = datetime(2026, 7, 12, 12, 0, tzinfo=tz)

    assert StoreHoursService.is_store_open(demo_company, now=sunday_noon) is False


@pytest.mark.django_db
def test_store_open_on_weekday_inside_hours(demo_company):
    tz = ZoneInfo(demo_company.timezone)
    monday_noon = datetime(2026, 7, 6, 12, 0, tzinfo=tz)

    assert StoreHoursService.is_store_open(demo_company, now=monday_noon) is True


@pytest.mark.django_db
def test_store_closed_outside_hours(demo_company):
    tz = ZoneInfo(demo_company.timezone)
    monday_early = datetime(2026, 7, 6, 8, 0, tzinfo=tz)

    assert StoreHoursService.is_store_open(demo_company, now=monday_early) is False


@pytest.mark.django_db
def test_overnight_hours(demo_company):
    # muda segunda pra horário que cruza meia-noite
    monday = BusinessHours.all_objects.get(tenant=demo_company, day_of_week=0)
    monday.opens_at = time(18, 0)
    monday.closes_at = time(2, 0)
    monday.is_closed = False
    monday.save()

    tz = ZoneInfo(demo_company.timezone)
    monday_late = datetime(2026, 7, 6, 23, 0, tzinfo=tz)
    monday_after_midnight = datetime(2026, 7, 7, 1, 0, tzinfo=tz)
    monday_afternoon = datetime(2026, 7, 6, 15, 0, tzinfo=tz)

    assert StoreHoursService.is_store_open(demo_company, now=monday_late) is True
    assert StoreHoursService.is_store_open(demo_company, now=monday_after_midnight) is True
    assert StoreHoursService.is_store_open(demo_company, now=monday_afternoon) is False
