import pytest

from apps.accounts.models import Employee, EmployeeRole, Role
from apps.accounts.services.customer_auth_service import CustomerAuthService
from apps.catalog.models import Category, Option, OptionGroup, Product, ProductOptionGroup
from apps.catalog.services.seed_catalog import seed_demo_catalog
from apps.companies.services.onboarding_service import OnboardingService
from apps.companies.services.settings_service import SettingsService
from apps.customers.models import Customer
from apps.orders.models import Order
from apps.promotions.models import Campaign
from apps.promotions.services.campaign_service import CampaignService


def _create_staff(*, company, email: str, password: str, role_name: str) -> Employee:
    employee = Employee(
        tenant=company,
        email=email,
        first_name=role_name.title(),
        last_name="Teste",
        is_owner=False,
        is_active=True,
    )
    employee.set_password(password)
    employee.save()
    role = Role.all_objects.get(tenant=company, name=role_name)
    EmployeeRole.objects.get_or_create(employee=employee, role=role)
    return employee


def _checkout(api_client, *, host: str, product_id, options=None, phone="(11) 91111-2222"):
    return api_client.post(
        "/api/v1/public/orders/checkout/",
        {
            "customer_name": "Cliente Isolamento",
            "customer_phone": phone,
            "delivery_type": "pickup",
            "payment_method": "pix",
            "items": [
                {
                    "product_id": str(product_id),
                    "quantity": 1,
                    "options": options or [],
                }
            ],
        },
        format="json",
        HTTP_HOST=host,
    )


def _product_options(company) -> tuple[Product, list[dict]]:
    product = Product.all_objects.get(tenant=company, slug="x-burger")
    link = (
        ProductOptionGroup.all_objects.filter(product=product)
        .select_related("option_group")
        .first()
    )
    option = Option.all_objects.filter(option_group=link.option_group).first()
    return product, [{"option_id": str(option.id)}]


@pytest.fixture
def isolation_world(db, api_client):
    """Dois tenants + roles + pedido/produto/cliente/campanha em cada um (Onda 0)."""
    tenant_a = OnboardingService.create_company(
        trade_name="Loja Alfa",
        subdomain="demo",
        email="contato@demo.com",
        owner_email="admin@demo.com",
        owner_password="demo1234",
    )
    tenant_b = OnboardingService.create_company(
        trade_name="Loja Beta",
        subdomain="outra-loja",
        email="contato@outra.com",
        owner_email="admin@outra.com",
        owner_password="outra1234",
    )
    seed_demo_catalog(tenant_a)
    seed_demo_catalog(tenant_b)
    SettingsService.update(tenant_a, auto_close_outside_hours=False, is_open=True)
    SettingsService.update(tenant_b, auto_close_outside_hours=False, is_open=True)

    kitchen = _create_staff(
        company=tenant_a,
        email="kitchen@demo.com",
        password="kitchen12",
        role_name="kitchen",
    )
    operator = _create_staff(
        company=tenant_a,
        email="operator@demo.com",
        password="operator12",
        role_name="operator",
    )

    product_a, options_a = _product_options(tenant_a)
    product_b, options_b = _product_options(tenant_b)

    order_a_resp = _checkout(
        api_client,
        host="demo.localhost:8001",
        product_id=product_a.id,
        options=options_a,
        phone="(11) 91111-0001",
    )
    assert order_a_resp.status_code == 201, order_a_resp.content
    order_b_resp = _checkout(
        api_client,
        host="outra-loja.localhost:8001",
        product_id=product_b.id,
        options=options_b,
        phone="(11) 91111-0002",
    )
    assert order_b_resp.status_code == 201, order_b_resp.content

    order_a = Order.all_objects.select_related("customer").get(id=order_a_resp.json()["id"])
    order_b = Order.all_objects.select_related("customer").get(id=order_b_resp.json()["id"])

    category_a = Category.all_objects.get(tenant=tenant_a, slug="lanches")
    category_b = Category.all_objects.get(tenant=tenant_b, slug="lanches")
    group_a = OptionGroup.all_objects.filter(tenant=tenant_a).first()
    group_b = OptionGroup.all_objects.filter(tenant=tenant_b).first()

    campaign_a = CampaignService.create(
        tenant=tenant_a,
        data={"product_id": product_a.id, "promo_price": "18.00"},
    )
    campaign_b = CampaignService.create(
        tenant=tenant_b,
        data={"product_id": product_b.id, "promo_price": "18.00"},
    )

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "kitchen": kitchen,
        "operator": operator,
        "product_a": product_a,
        "product_b": product_b,
        "options_a": options_a,
        "options_b": options_b,
        "order_a": order_a,
        "order_b": order_b,
        "customer_a": order_a.customer,
        "customer_b": order_b.customer,
        "category_a": category_a,
        "category_b": category_b,
        "group_a": group_a,
        "group_b": group_b,
        "campaign_a": campaign_a,
        "campaign_b": campaign_b,
    }


def _login(api_client, *, email: str, password: str, subdomain: str) -> dict:
    response = api_client.post(
        "/api/v1/auth/login/",
        {"email": email, "password": password, "subdomain": subdomain},
        format="json",
    )
    assert response.status_code == 200, response.content
    return response.json()


def _auth(token: str) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def _assert_denied(response):
    assert response.status_code in (403, 404), (
        f"esperado 403/404, veio {response.status_code}: {response.content}"
    )


# --- Onda 0 ---


@pytest.mark.django_db
def test_f0_fixtures_ready(isolation_world):
    assert isolation_world["tenant_a"].subdomain == "demo"
    assert isolation_world["tenant_b"].subdomain == "outra-loja"
    assert isolation_world["kitchen"].email == "kitchen@demo.com"
    assert isolation_world["operator"].email == "operator@demo.com"
    assert isolation_world["order_a"].id != isolation_world["order_b"].id
    assert Campaign.all_objects.filter(tenant=isolation_world["tenant_b"]).exists()
    assert Customer.all_objects.filter(tenant=isolation_world["tenant_a"]).exists()


# --- 5.1 Cross-tenant IDOR ---


@pytest.mark.django_db
def test_p1_cross_tenant_orders(api_client, isolation_world):
    login = _login(api_client, email="admin@demo.com", password="demo1234", subdomain="demo")
    headers = _auth(login["access"])
    oid = isolation_world["order_b"].id

    _assert_denied(api_client.get(f"/api/v1/admin/orders/{oid}/", **headers))
    _assert_denied(
        api_client.patch(
            f"/api/v1/admin/orders/{oid}/status/",
            {"status": "confirmed"},
            format="json",
            **headers,
        )
    )
    _assert_denied(
        api_client.patch(
            f"/api/v1/admin/orders/{oid}/payment/",
            {"status": "paid"},
            format="json",
            **headers,
        )
    )


@pytest.mark.django_db
def test_p1_cross_tenant_catalog(api_client, isolation_world):
    login = _login(api_client, email="admin@demo.com", password="demo1234", subdomain="demo")
    headers = _auth(login["access"])
    pid = isolation_world["product_b"].id
    cid = isolation_world["category_b"].id
    gid = isolation_world["group_b"].id

    _assert_denied(api_client.get(f"/api/v1/admin/products/{pid}/", **headers))
    _assert_denied(
        api_client.patch(
            f"/api/v1/admin/products/{pid}/",
            {"name": "Hack"},
            format="json",
            **headers,
        )
    )
    _assert_denied(api_client.delete(f"/api/v1/admin/products/{pid}/", **headers))
    _assert_denied(
        api_client.patch(
            f"/api/v1/admin/categories/{cid}/",
            {"name": "Hack"},
            format="json",
            **headers,
        )
    )
    _assert_denied(
        api_client.patch(
            f"/api/v1/admin/option-groups/{gid}/",
            {"name": "Hack"},
            format="json",
            **headers,
        )
    )


@pytest.mark.django_db
def test_p1_cross_tenant_customers_and_campaigns(api_client, isolation_world):
    login = _login(api_client, email="admin@demo.com", password="demo1234", subdomain="demo")
    headers = _auth(login["access"])
    cust = isolation_world["customer_b"].id
    camp = isolation_world["campaign_b"].id

    _assert_denied(api_client.get(f"/api/v1/admin/customers/{cust}/", **headers))
    _assert_denied(api_client.get(f"/api/v1/admin/campaigns/{camp}/", **headers))
    _assert_denied(
        api_client.patch(
            f"/api/v1/admin/campaigns/{camp}/",
            {"promo_price": "1.00"},
            format="json",
            **headers,
        )
    )


@pytest.mark.django_db
def test_p1_settings_follow_jwt_tenant_not_host(api_client, isolation_world):
    login = _login(api_client, email="admin@demo.com", password="demo1234", subdomain="demo")
    response = api_client.get(
        "/api/v1/admin/settings/",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
        HTTP_HOST="outra-loja.localhost:8001",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["company"]["trade_name"] == "Loja Alfa"
    assert body["company"]["trade_name"] != "Loja Beta"


@pytest.mark.django_db
def test_p1_lists_exclude_other_tenant(api_client, isolation_world):
    login = _login(api_client, email="admin@demo.com", password="demo1234", subdomain="demo")
    headers = _auth(login["access"])
    id_b_order = str(isolation_world["order_b"].id)
    id_b_product = str(isolation_world["product_b"].id)
    id_b_customer = str(isolation_world["customer_b"].id)
    id_b_campaign = str(isolation_world["campaign_b"].id)
    id_b_category = str(isolation_world["category_b"].id)

    orders = api_client.get("/api/v1/admin/orders/", **headers)
    assert orders.status_code == 200
    assert all(row["id"] != id_b_order for row in orders.json()["results"])

    products = api_client.get("/api/v1/admin/products/", **headers)
    assert products.status_code == 200
    assert all(row["id"] != id_b_product for row in products.json()["results"])

    customers = api_client.get("/api/v1/admin/customers/", **headers)
    assert customers.status_code == 200
    assert all(row["id"] != id_b_customer for row in customers.json()["results"])

    campaigns = api_client.get("/api/v1/admin/campaigns/", **headers)
    assert campaigns.status_code == 200
    assert all(row["id"] != id_b_campaign for row in campaigns.json())

    categories = api_client.get("/api/v1/admin/categories/", **headers)
    assert categories.status_code == 200
    assert all(row["id"] != id_b_category for row in categories.json())


# --- 5.2 Público vs admin ---


@pytest.mark.django_db
def test_p2_admin_requires_employee_auth(api_client, isolation_world):
    assert api_client.get("/api/v1/admin/orders/").status_code == 401

    customer_auth = CustomerAuthService.register(
        tenant=isolation_world["tenant_a"],
        phone="(11) 98888-1111",
        password="cliente12",
        first_name="Cliente",
        last_name="A",
    )
    response = api_client.get(
        "/api/v1/admin/orders/",
        HTTP_AUTHORIZATION=f"Bearer {customer_auth['access']}",
    )
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_p2_employee_token_rejected_on_customer_account(api_client, isolation_world):
    login = _login(api_client, email="admin@demo.com", password="demo1234", subdomain="demo")
    response = api_client.get(
        "/api/v1/public/account/me/",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
        HTTP_HOST="demo.localhost:8001",
    )
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_p2_public_order_and_catalog_isolated(api_client, isolation_world):
    oid_b = isolation_world["order_b"].id
    detail = api_client.get(
        f"/api/v1/public/orders/{oid_b}/",
        HTTP_HOST="demo.localhost:8001",
    )
    _assert_denied(detail)

    catalog = api_client.get(
        "/api/v1/public/catalog/products/",
        HTTP_HOST="demo.localhost:8001",
    )
    assert catalog.status_code == 200
    payload = catalog.json()
    rows = payload["results"] if isinstance(payload, dict) and "results" in payload else payload
    ids = {row["id"] for row in rows}
    assert str(isolation_world["product_b"].id) not in ids
    assert str(isolation_world["product_a"].id) in ids


@pytest.mark.django_db
def test_p2_checkout_rejects_foreign_product(api_client, isolation_world):
    response = _checkout(
        api_client,
        host="demo.localhost:8001",
        product_id=isolation_world["product_b"].id,
        options=isolation_world["options_b"],
        phone="(11) 91111-0099",
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PRODUCT_UNAVAILABLE"


# --- 5.3 Matriz de papéis ---


@pytest.mark.django_db
def test_p3_kitchen_permissions(api_client, isolation_world):
    login = _login(
        api_client,
        email="kitchen@demo.com",
        password="kitchen12",
        subdomain="demo",
    )
    headers = _auth(login["access"])
    oid = isolation_world["order_a"].id

    assert api_client.patch(
        "/api/v1/admin/settings/",
        {"settings": {"is_open": False}},
        format="json",
        **headers,
    ).status_code == 403

    assert api_client.post(
        "/api/v1/admin/products/",
        {
            "name": "Hack",
            "base_price": 10,
            "category_id": str(isolation_world["category_a"].id),
        },
        format="json",
        **headers,
    ).status_code == 403

    confirmed = api_client.patch(
        f"/api/v1/admin/orders/{oid}/status/",
        {"status": "confirmed"},
        format="json",
        **headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"


@pytest.mark.django_db
def test_p3_operator_permissions(api_client, isolation_world):
    login = _login(
        api_client,
        email="operator@demo.com",
        password="operator12",
        subdomain="demo",
    )
    headers = _auth(login["access"])

    assert api_client.post(
        "/api/v1/admin/campaigns/",
        {
            "product_id": str(isolation_world["product_a"].id),
            "promo_price": "10.00",
        },
        format="json",
        **headers,
    ).status_code == 403

    assert api_client.get(
        "/api/v1/admin/communications/whatsapp/",
        **headers,
    ).status_code == 403

    orders = api_client.get("/api/v1/admin/orders/", **headers)
    assert orders.status_code == 200


@pytest.mark.django_db
def test_p3_owner_can_manage_settings_and_catalog(api_client, isolation_world):
    login = _login(api_client, email="admin@demo.com", password="demo1234", subdomain="demo")
    headers = _auth(login["access"])

    settings = api_client.get("/api/v1/admin/settings/", **headers)
    assert settings.status_code == 200

    products = api_client.get("/api/v1/admin/products/", **headers)
    assert products.status_code == 200

    wa = api_client.get("/api/v1/admin/communications/whatsapp/", **headers)
    assert wa.status_code == 200


# --- 5.4 Auth / sessão ---


@pytest.mark.django_db
def test_p4_invalid_token_rejected(api_client, isolation_world):
    response = api_client.get(
        "/api/v1/admin/orders/",
        HTTP_AUTHORIZATION="Bearer token.invalido.aqui",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_p4_logout_revokes_access_and_refresh(api_client, isolation_world):
    login = _login(api_client, email="admin@demo.com", password="demo1234", subdomain="demo")
    access = login["access"]
    refresh = login["refresh"]

    logout = api_client.post(
        "/api/v1/auth/logout/",
        {"refresh": refresh},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {access}",
    )
    assert logout.status_code == 204

    assert api_client.get(
        "/api/v1/admin/me/",
        HTTP_AUTHORIZATION=f"Bearer {access}",
    ).status_code == 401

    assert api_client.post(
        "/api/v1/auth/refresh/",
        {"refresh": refresh},
        format="json",
    ).status_code in (401, 403)


@pytest.mark.django_db
def test_p4_refresh_of_other_user_not_swapped(api_client, isolation_world):
    login_a = _login(api_client, email="admin@demo.com", password="demo1234", subdomain="demo")
    login_b = _login(
        api_client,
        email="admin@outra.com",
        password="outra1234",
        subdomain="outra-loja",
    )

    refreshed = api_client.post(
        "/api/v1/auth/refresh/",
        {"refresh": login_b["refresh"]},
        format="json",
    )
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access"]

    me = api_client.get(
        "/api/v1/admin/me/",
        HTTP_AUTHORIZATION=f"Bearer {new_access}",
    )
    assert me.status_code == 200
    assert me.json()["tenant"]["subdomain"] == "outra-loja"
    assert me.json()["user"]["email"] == "admin@outra.com"
    assert me.json()["user"]["email"] != login_a["user"]["email"]


@pytest.mark.django_db
def test_p4_login_wrong_subdomain_fails(api_client, isolation_world):
    response = api_client.post(
        "/api/v1/auth/login/",
        {
            "email": "admin@outra.com",
            "password": "outra1234",
            "subdomain": "demo",
        },
        format="json",
    )
    assert response.status_code in (401, 403)
