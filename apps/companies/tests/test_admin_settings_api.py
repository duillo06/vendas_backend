import pytest
from django.test import override_settings

from apps.catalog.services.seed_catalog import seed_demo_catalog
from apps.companies.services.onboarding_service import OnboardingService
from apps.companies.services.settings_service import SettingsService
from apps.orders.models import Order


@pytest.fixture
def demo_admin(db):
    company = OnboardingService.create_company(
        trade_name="Lanchonete Demo",
        subdomain="demo",
        email="contato@demo.com",
        owner_email="admin@demo.com",
        owner_password="demo1234",
    )
    seed_demo_catalog(company)
    SettingsService.update(company, auto_close_outside_hours=False, is_open=True)
    return company


def _login(api_client):
    return api_client.post(
        "/api/v1/auth/login/",
        {"email": "admin@demo.com", "password": "demo1234", "subdomain": "demo"},
        format="json",
    ).json()


@pytest.mark.django_db
def test_admin_settings_requires_auth(api_client):
    response = api_client.get("/api/v1/admin/settings/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_admin_settings_get(api_client, demo_admin):
    login = _login(api_client)

    response = api_client.get(
        "/api/v1/admin/settings/",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["company"]["trade_name"] == "Lanchonete Demo"
    assert "delivery_fee" in body["settings"]
    assert len(body["business_hours"]) == 7


@pytest.mark.django_db
def test_admin_settings_patch(api_client, demo_admin):
    login = _login(api_client)

    response = api_client.patch(
        "/api/v1/admin/settings/",
        {
            "settings": {
                "delivery_fee": 7.5,
                "is_open": False,
                "theme": {
                    "primary": "160 84% 39%",
                    "primary_foreground": "0 0% 100%",
                },
            },
            "company": {"phone": "(11) 99999-0000"},
        },
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["settings"]["delivery_fee"] == 7.5
    assert body["settings"]["is_open"] is False
    assert body["settings"]["theme"]["primary"] == "160 84% 39%"
    assert body["company"]["phone"] == "(11) 99999-0000"


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_public_company_exposes_theme_after_patch(api_client, demo_admin):
    login = _login(api_client)
    api_client.patch(
        "/api/v1/admin/settings/",
        {"settings": {"theme": {"primary": "200 80% 40%"}}},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
    )

    response = api_client.get(
        "/api/v1/public/company/",
        HTTP_HOST="demo.localhost:8001",
    )

    assert response.status_code == 200
    assert response.json()["theme"]["primary"] == "200 80% 40%"


@pytest.mark.django_db
def test_admin_dashboard_requires_auth(api_client):
    response = api_client.get("/api/v1/admin/dashboard/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_admin_dashboard_with_orders(api_client, demo_admin):
    from apps.customers.models import Customer

    login = _login(api_client)
    customer = Customer.all_objects.create(
        tenant=demo_admin,
        first_name="Maria",
        phone="11999990000",
    )
    Order.all_objects.create(
        tenant=demo_admin,
        customer=customer,
        order_number="#0001",
        status="completed",
        delivery_type="pickup",
        subtotal=50,
        total=50,
        customer_name="Maria",
        customer_phone="11999990000",
    )
    Order.all_objects.create(
        tenant=demo_admin,
        customer=customer,
        order_number="#0002",
        status="pending",
        delivery_type="pickup",
        subtotal=30,
        total=30,
        customer_name="João",
        customer_phone="11988880000",
    )

    response = api_client.get(
        "/api/v1/admin/dashboard/",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["today"]["total_orders"] == 2
    assert body["today"]["pending_orders"] == 1
    assert body["today"]["completed_orders"] == 1
    assert body["today"]["revenue"] == 50.0
    assert "yesterday" in body
    assert "total_orders" in body["yesterday"]
    assert "revenue" in body["yesterday"]
    assert len(body["recent_orders"]) == 2
