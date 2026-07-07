import pytest
from django.test import override_settings

from apps.catalog.services.seed_catalog import seed_demo_catalog
from apps.companies.services.onboarding_service import OnboardingService
from apps.companies.services.settings_service import SettingsService


@pytest.fixture
def demo_orders_store(db):
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


def _checkout(api_client, product_id, options):
    return api_client.post(
        "/api/v1/public/orders/checkout/",
        {
            "customer_name": "Maria Santos",
            "customer_phone": "(11) 98765-4321",
            "delivery_type": "pickup",
            "payment_method": "pix",
            "items": [{"product_id": product_id, "quantity": 1, "options": options}],
        },
        format="json",
        HTTP_HOST="demo.localhost:8001",
    )


@pytest.fixture
def pending_order(api_client, demo_orders_store):
    from apps.catalog.models import Option, Product, ProductOptionGroup

    product = Product.all_objects.get(tenant=demo_orders_store, slug="x-burger")
    link = ProductOptionGroup.all_objects.filter(product=product).select_related("option_group").first()
    option = Option.all_objects.filter(option_group=link.option_group).first()
    options = [{"option_id": str(option.id)}]

    response = _checkout(api_client, str(product.id), options)
    assert response.status_code == 201
    return response.json()


@pytest.mark.django_db
def test_admin_orders_requires_auth(api_client):
    response = api_client.get("/api/v1/admin/orders/")
    assert response.status_code == 401


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_admin_orders_list_and_detail(api_client, demo_orders_store, pending_order):
    login = _login(api_client)

    list_response = api_client.get(
        "/api/v1/admin/orders/",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
    )
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["count"] >= 1
    assert body["results"][0]["order_number"]

    detail_response = api_client.get(
        f"/api/v1/admin/orders/{pending_order['id']}/",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "pending"
    assert len(detail["items"]) == 1


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_admin_order_status_transition(api_client, demo_orders_store, pending_order):
    login = _login(api_client)
    headers = {"HTTP_AUTHORIZATION": f"Bearer {login['access']}"}

    confirmed = api_client.patch(
        f"/api/v1/admin/orders/{pending_order['id']}/status/",
        {"status": "confirmed", "notes": "Ok"},
        format="json",
        **headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"

    invalid = api_client.patch(
        f"/api/v1/admin/orders/{pending_order['id']}/status/",
        {"status": "pending"},
        format="json",
        **headers,
    )
    assert invalid.status_code == 422


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_admin_order_payment(api_client, demo_orders_store, pending_order):
    login = _login(api_client)

    response = api_client.patch(
        f"/api/v1/admin/orders/{pending_order['id']}/payment/",
        {"status": "paid"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
    )

    assert response.status_code == 200
    assert response.json()["payment"]["status"] == "paid"
    assert response.json()["payment"]["paid_at"] is not None
