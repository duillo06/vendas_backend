import pytest

from apps.companies.services.onboarding_service import OnboardingService


@pytest.fixture
def demo_company(db):
    return OnboardingService.create_company(
        trade_name="Comms Demo",
        subdomain="demo-comms",
        email="comms@demo.com",
    )
