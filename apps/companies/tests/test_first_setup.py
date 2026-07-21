"""Fase 4 — assistente de 1ª configuração."""

import pytest

from apps.catalog.models import Category, CategoryCapability, OptionGroup
from apps.companies.services.first_setup_service import FirstSetupService
from apps.companies.services.onboarding_service import OnboardingService


@pytest.fixture
def setup_company(db):
    return OnboardingService.create_company(
        trade_name="Setup Demo",
        subdomain="setup-fase4",
        email="contato@setup.com",
        owner_email="admin@setup.com",
        owner_password="demo1234",
    )


@pytest.mark.django_db
def test_onboarding_starts_setup_pending(setup_company):
    setup = FirstSetupService.get(setup_company)
    assert setup["status"] == "pending"


@pytest.mark.django_db
def test_apply_pizza_segment(setup_company):
    result = FirstSetupService.apply_segment(setup_company, "pizza")
    assert result["setup"]["status"] == "completed"
    assert result["setup"]["segment"] == "pizza"
    assert len(result["categories"]) >= 1

    pizzas = Category.all_objects.get(tenant=setup_company, name="Pizzas")
    assert CategoryCapability.all_objects.filter(category=pizzas, kind="size").exists()
    assert OptionGroup.all_objects.filter(tenant=setup_company, name="Tamanho").exists()


@pytest.mark.django_db
def test_admin_setup_apply(api_client, setup_company):
    login = api_client.post(
        "/api/v1/auth/login/",
        {
            "email": "admin@setup.com",
            "password": "demo1234",
            "subdomain": "setup-fase4",
        },
        format="json",
    ).json()
    headers = {"HTTP_AUTHORIZATION": f"Bearer {login['access']}"}

    status_resp = api_client.get("/api/v1/admin/setup/", **headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["setup"]["status"] == "pending"
    assert len(status_resp.json()["segments"]) >= 3

    apply = api_client.post(
        "/api/v1/admin/setup/apply/",
        {"segment": "burger"},
        format="json",
        **headers,
    )
    assert apply.status_code == 200
    body = apply.json()
    assert body["setup"]["segment"] == "burger"
    assert Category.all_objects.filter(tenant=setup_company, name="Lanches").exists()

    stub = api_client.get("/api/v1/admin/ai/suggestions/", **headers)
    assert stub.status_code == 200
    assert stub.json()["available"] is False
