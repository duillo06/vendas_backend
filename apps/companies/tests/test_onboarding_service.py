import pytest
from django.core.exceptions import ValidationError

from apps.companies.domain.validators import validate_subdomain
from apps.companies.models import BusinessHours, CompanySettings
from apps.companies.services.onboarding_service import OnboardingService


@pytest.mark.django_db
def test_onboarding_creates_settings_and_seven_business_hours():
    company = OnboardingService.create_company(
        trade_name="Teste",
        subdomain="teste-loja",
        email="teste@teste.com",
        owner_email="dono@teste.com",
        owner_password="senha1234",
    )

    settings = CompanySettings.all_objects.get(tenant=company)
    assert settings.is_open is True
    assert "cash" in settings.payment_methods

    hours = BusinessHours.all_objects.filter(tenant=company)
    assert hours.count() == 7

    from apps.accounts.models import Employee, Role

    assert Employee.all_objects.filter(tenant=company, is_owner=True).exists()
    assert Role.all_objects.filter(tenant=company, is_system=True).count() == 4


@pytest.mark.django_db
def test_subdomain_rejects_reserved_name():
    with pytest.raises(ValidationError):
        validate_subdomain("api")


@pytest.mark.django_db
def test_subdomain_rejects_invalid_chars():
    with pytest.raises(ValidationError):
        validate_subdomain("Loja_Test")
