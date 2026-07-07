import pytest
from django.test import override_settings

from apps.catalog.services.seed_catalog import seed_demo_catalog
from apps.companies.services.onboarding_service import OnboardingService


@pytest.fixture
def demo_catalog(db):
    company = OnboardingService.create_company(
        trade_name="Lanchonete Demo",
        subdomain="demo",
        email="contato@demo.com",
        owner_email="admin@demo.com",
        owner_password="demo1234",
    )
    seed_demo_catalog(company)
    return company


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_public_categories(api_client, demo_catalog):
    response = api_client.get(
        "/api/v1/public/catalog/categories/",
        HTTP_HOST="demo.localhost:8001",
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    assert data[0]["slug"] == "lanches"


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_public_product_detail_with_options(api_client, demo_catalog):
    response = api_client.get(
        "/api/v1/public/catalog/products/x-burger/",
        HTTP_HOST="demo.localhost:8001",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "x-burger"
    assert len(body["option_groups"]) == 1
    assert body["option_groups"][0]["name"] == "Tamanho"


@pytest.mark.django_db
def test_admin_products_requires_auth(api_client):
    response = api_client.get("/api/v1/admin/products/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_admin_products_with_token(api_client, demo_catalog):
    login = api_client.post(
        "/api/v1/auth/login/",
        {"email": "admin@demo.com", "password": "demo1234", "subdomain": "demo"},
        format="json",
    ).json()

    response = api_client.get(
        "/api/v1/admin/products/",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
    )

    assert response.status_code == 200
    assert response.json()["count"] >= 2
