import pytest
from django.test import override_settings

from apps.catalog.services.seed_catalog import seed_demo_catalog
from apps.companies.services.onboarding_service import OnboardingService
from apps.companies.services.settings_service import SettingsService


@pytest.fixture
def demo_store(db):
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


@pytest.fixture
def x_burger_option_ids(demo_store):
    from apps.catalog.models import Option, Product, ProductOptionGroup

    product = Product.all_objects.get(tenant=demo_store, slug="x-burger")
    link = ProductOptionGroup.all_objects.filter(product=product).select_related("option_group").first()
    assert link is not None
    option = Option.all_objects.filter(option_group=link.option_group).first()
    return str(product.id), [{"option_id": str(option.id)}]


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_checkout_happy_path(api_client, demo_store, x_burger_option_ids):
    product_id, options = x_burger_option_ids

    payload = {
        "customer_name": "Maria Santos",
        "customer_phone": "(11) 98765-4321",
        "delivery_type": "pickup",
        "payment_method": "pix",
        "items": [{"product_id": product_id, "quantity": 1, "options": options}],
    }

    response = api_client.post(
        "/api/v1/public/orders/checkout/",
        payload,
        format="json",
        HTTP_HOST="demo.localhost:8001",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["order_number"] == "#0001"
    assert body["total"] >= 22


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_checkout_authenticated_customer_links_order(api_client, demo_store, x_burger_option_ids):
    from apps.accounts.services.customer_auth_service import CustomerAuthService
    from apps.customers.models import Customer, CustomerAddress
    from apps.orders.models import Order

    product_id, options = x_burger_option_ids

    auth = CustomerAuthService.register(
        tenant=demo_store,
        phone="(11) 98888-7777",
        password="senha1234",
        first_name="Maria",
        last_name="Santos",
        email="maria@example.com",
    )
    customer_id = auth["customer"]["id"]

    customer = Customer.objects.get(id=customer_id)

    CustomerAddress.objects.create(
        tenant=demo_store,
        customer=customer,
        label="Casa",
        street="Rua das Flores",
        number="100",
        neighborhood="Centro",
        city="São Paulo",
        state="SP",
        zip_code="01310-100",
        is_default=True,
    )

    payload = {
        "customer_id": customer_id,
        "customer_name": "Maria Santos",
        "customer_phone": "(11) 98888-7777",
        "customer_email": "maria@example.com",
        "delivery_type": "delivery",
        "payment_method": "pix",
        "address": {
            "street": "Rua das Flores",
            "number": "100",
            "complement": "",
            "neighborhood": "Centro",
            "city": "São Paulo",
            "state": "SP",
            "zip_code": "01310-100",
            "reference": "",
        },
        "items": [{"product_id": product_id, "quantity": 1, "options": options}],
    }

    response = api_client.post(
        "/api/v1/public/orders/checkout/",
        payload,
        format="json",
        HTTP_HOST="demo.localhost:8001",
        HTTP_AUTHORIZATION=f"Bearer {auth['access']}",
    )

    assert response.status_code == 201
    order = Order.objects.get(id=response.json()["id"])
    assert str(order.customer_id) == customer_id


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_checkout_guest_rejects_customer_id(api_client, demo_store, x_burger_option_ids):
    from apps.accounts.services.customer_auth_service import CustomerAuthService

    product_id, options = x_burger_option_ids
    auth = CustomerAuthService.register(
        tenant=demo_store,
        phone="(11) 97777-6666",
        password="senha1234",
        first_name="João",
    )

    response = api_client.post(
        "/api/v1/public/orders/checkout/",
        {
            "customer_id": auth["customer"]["id"],
            "customer_name": "João",
            "customer_phone": "(11) 97777-6666",
            "delivery_type": "pickup",
            "payment_method": "pix",
            "items": [{"product_id": product_id, "quantity": 1, "options": options}],
        },
        format="json",
        HTTP_HOST="demo.localhost:8001",
    )

    assert response.status_code == 400
    assert "customer_id" in response.json()


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_checkout_store_closed(api_client, demo_store, x_burger_option_ids):
    SettingsService.update(demo_store, is_open=False)
    product_id, options = x_burger_option_ids

    response = api_client.post(
        "/api/v1/public/orders/checkout/",
        {
            "customer_name": "João",
            "customer_phone": "(11) 98888-7777",
            "delivery_type": "pickup",
            "payment_method": "pix",
            "items": [{"product_id": product_id, "quantity": 1, "options": options}],
        },
        format="json",
        HTTP_HOST="demo.localhost:8001",
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "STORE_CLOSED"


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_public_order_tracking(api_client, demo_store, x_burger_option_ids):
    product_id, options = x_burger_option_ids

    created = api_client.post(
        "/api/v1/public/orders/checkout/",
        {
            "customer_name": "Ana",
            "customer_phone": "(11) 97777-6666",
            "delivery_type": "pickup",
            "payment_method": "pix",
            "items": [{"product_id": product_id, "quantity": 1, "options": options}],
        },
        format="json",
        HTTP_HOST="demo.localhost:8001",
    ).json()

    response = api_client.get(
        f"/api/v1/public/orders/{created['id']}/",
        HTTP_HOST="demo.localhost:8001",
    )

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert len(response.json()["status_history"]) >= 1
