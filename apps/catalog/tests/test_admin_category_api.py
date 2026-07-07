import pytest

from apps.companies.services.onboarding_service import OnboardingService


@pytest.fixture
def demo_admin(db):
    return OnboardingService.create_company(
        trade_name="Lanchonete Demo",
        subdomain="demo",
        email="contato@demo.com",
        owner_email="admin@demo.com",
        owner_password="demo1234",
    )


def _login(api_client):
    return api_client.post(
        "/api/v1/auth/login/",
        {"email": "admin@demo.com", "password": "demo1234", "subdomain": "demo"},
        format="json",
    ).json()


@pytest.mark.django_db
def test_admin_create_category_without_slug(api_client, demo_admin):
    login = _login(api_client)

    response = api_client.post(
        "/api/v1/admin/categories/",
        {"name": "Bebidas", "is_active": True, "sort_order": 0},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Bebidas"
    assert body["slug"] == "bebidas"
