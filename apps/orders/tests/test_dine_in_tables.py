import pytest
from django.test import override_settings

from apps.catalog.services.seed_catalog import seed_demo_catalog
from apps.companies.services.onboarding_service import OnboardingService
from apps.companies.services.settings_service import SettingsService
from apps.orders.domain.enums import OrderStatus
from apps.orders.models import Order
from apps.orders.services.order_service import OrderService
from apps.orders.services.table_service import TableService


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
    SettingsService.update(
        company,
        auto_close_outside_hours=False,
        is_open=True,
        accepts_dine_in=True,
    )
    return company


@pytest.fixture
def admin_token(api_client, demo_store):
    response = api_client.post(
        "/api/v1/auth/login/",
        {"email": "admin@demo.com", "password": "demo1234", "subdomain": "demo"},
        format="json",
    )
    assert response.status_code == 200
    return response.json()["access"]


@pytest.fixture
def table(demo_store):
    return TableService.create(tenant=demo_store, number="12", label="Varanda")


@pytest.fixture
def x_burger_option_ids(demo_store):
    from apps.catalog.models import Option, Product, ProductOptionGroup

    product = Product.all_objects.get(tenant=demo_store, slug="x-burger")
    link = ProductOptionGroup.all_objects.filter(product=product).select_related("option_group").first()
    option = Option.all_objects.filter(option_group=link.option_group).first()
    return str(product.id), [{"option_id": str(option.id)}]


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_admin_create_and_list_tables(api_client, demo_store, admin_token):
    response = api_client.post(
        "/api/v1/admin/tables/",
        {"number": "1", "label": "Salão"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {admin_token}",
        HTTP_HOST="demo.localhost:8001",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["number"] == "1"
    assert body["qr_token"]
    assert "/mesa/" in body["qr_url"]

    listed = api_client.get(
        "/api/v1/admin/tables/",
        HTTP_AUTHORIZATION=f"Bearer {admin_token}",
        HTTP_HOST="demo.localhost:8001",
    )
    assert listed.status_code == 200
    assert len(listed.json()) >= 1


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_public_table_by_token(api_client, demo_store, table):
    response = api_client.get(
        f"/api/v1/public/tables/{table.qr_token}/",
        HTTP_HOST="demo.localhost:8001",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["table_number"] == "12"
    assert body["table_id"] == str(table.id)


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_public_table_inactive(api_client, demo_store, table):
    TableService.update(table=table, is_active=False)
    response = api_client.get(
        f"/api/v1/public/tables/{table.qr_token}/",
        HTTP_HOST="demo.localhost:8001",
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TABLE_INACTIVE"


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_checkout_dine_in_via_qr(api_client, demo_store, table, x_burger_option_ids):
    product_id, options = x_burger_option_ids
    # checkout express: sem nome/fone/pagamento
    payload = {
        "delivery_type": "dine_in",
        "qr_token": table.qr_token,
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
    assert body["delivery_type"] == "dine_in"
    assert body["table_number"] == "12"
    assert body["delivery_fee"] == 0
    assert body["customer_name"] == "Mesa 12"
    assert body["payment"]["method"] == "pay_at_venue"

    order = Order.all_objects.get(id=body["id"])
    assert order.table_id == table.id
    assert order.table_number == "12"
    assert order.customer_phone == ""


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_checkout_dine_in_blocked_when_disabled(api_client, demo_store, table, x_burger_option_ids):
    SettingsService.update(demo_store, accepts_dine_in=False)
    product_id, options = x_burger_option_ids
    response = api_client.post(
        "/api/v1/public/orders/checkout/",
        {
            "delivery_type": "dine_in",
            "qr_token": table.qr_token,
            "items": [{"product_id": product_id, "quantity": 1, "options": options}],
        },
        format="json",
        HTTP_HOST="demo.localhost:8001",
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "DINE_IN_NOT_ACCEPTED"


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_dine_in_cannot_go_out_for_delivery(demo_store, table, x_burger_option_ids):
    product_id, options = x_burger_option_ids
    order = OrderService.create_from_checkout(
        tenant=demo_store,
        data={
            "delivery_type": "dine_in",
            "qr_token": table.qr_token,
            "items": [{"product_id": product_id, "quantity": 1, "options": options}],
        },
    )
    for status in (OrderStatus.CONFIRMED, OrderStatus.PREPARING, OrderStatus.READY):
        order = OrderService.update_status(order=order, new_status=status)

    from apps.orders.domain.exceptions import InvalidOrderTransition

    with pytest.raises(InvalidOrderTransition):
        OrderService.update_status(order=order, new_status=OrderStatus.OUT_FOR_DELIVERY)

    order = OrderService.update_status(order=order, new_status=OrderStatus.COMPLETED)
    assert order.status == OrderStatus.COMPLETED


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_admin_bulk_and_regenerate_qr(api_client, demo_store, admin_token, table):
    old_token = table.qr_token
    regen = api_client.post(
        f"/api/v1/admin/tables/{table.id}/regenerate-qr/",
        HTTP_AUTHORIZATION=f"Bearer {admin_token}",
        HTTP_HOST="demo.localhost:8001",
    )
    assert regen.status_code == 200
    assert regen.json()["qr_token"] != old_token

    bulk = api_client.post(
        "/api/v1/admin/tables/bulk/",
        {"count": 3, "start": 20},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {admin_token}",
        HTTP_HOST="demo.localhost:8001",
    )
    assert bulk.status_code == 201
    assert len(bulk.json()) == 3


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_public_company_exposes_accepts_dine_in(api_client, demo_store):
    response = api_client.get(
        "/api/v1/public/company/",
        HTTP_HOST="demo.localhost:8001",
    )
    assert response.status_code == 200
    assert response.json()["settings"]["accepts_dine_in"] is True
