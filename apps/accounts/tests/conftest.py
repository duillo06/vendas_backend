import pytest

from apps.companies.services.onboarding_service import OnboardingService


@pytest.fixture
def demo_with_owner(db):
    return OnboardingService.create_company(
        trade_name="Lanchonete Demo",
        subdomain="demo",
        email="contato@demo.com",
        owner_email="admin@demo.com",
        owner_password="demo1234",
    )
