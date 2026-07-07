import pytest

from apps.companies.services.onboarding_service import OnboardingService


@pytest.fixture
def demo_company(db):
    return OnboardingService.create_company(
        trade_name="Lanchonete Demo",
        subdomain="demo",
        email="demo@demo.com",
    )


@pytest.fixture
def other_company(db):
    return OnboardingService.create_company(
        trade_name="Outra Loja",
        subdomain="outra-loja",
        email="outra@demo.com",
    )
