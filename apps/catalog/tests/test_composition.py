from decimal import Decimal

import pytest
from django.test import override_settings

from apps.catalog.models import Category, Product, ProductComposition
from apps.catalog.services.composition_service import CompositionService
from apps.companies.services.onboarding_service import OnboardingService
from apps.companies.services.settings_service import SettingsService


@pytest.fixture
def demo_store(db):
    company = OnboardingService.create_company(
        trade_name="Pizzaria Demo",
        subdomain="demo",
        email="contato@demo.com",
        owner_email="admin@demo.com",
        owner_password="demo1234",
    )
    SettingsService.update(company, auto_close_outside_hours=False, is_open=True)
    return company


@pytest.fixture
def pizza_setup(demo_store):
    cat = Category.all_objects.create(tenant=demo_store, name="Pizzas", slug="pizzas")
    calabresa = Product.all_objects.create(
        tenant=demo_store,
        category=cat,
        name="Pizza Calabresa",
        slug="pizza-calabresa",
        base_price=Decimal("40.00"),
    )
    portuguesa = Product.all_objects.create(
        tenant=demo_store,
        category=cat,
        name="Pizza Portuguesa",
        slug="pizza-portuguesa",
        base_price=Decimal("50.00"),
    )
    ProductComposition.all_objects.create(
        tenant=demo_store,
        product=calabresa,
        is_enabled=True,
        source_type="category",
        min_parts=2,
        max_parts=2,
        pricing_rule="highest",
    )
    return demo_store, calabresa, portuguesa


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_composition_options_endpoint_lists_same_category(api_client, pizza_setup):
    _, calabresa, portuguesa = pizza_setup

    response = api_client.get(
        f"/api/v1/public/catalog/products/{calabresa.slug}/composition/",
        HTTP_HOST="demo.localhost:8001",
    )

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    # traz a outra pizza da categoria, mas nunca ela mesma
    assert str(portuguesa.id) in ids
    assert str(calabresa.id) not in ids


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_product_detail_exposes_composition(api_client, pizza_setup):
    _, calabresa, _ = pizza_setup

    response = api_client.get(
        f"/api/v1/public/catalog/products/{calabresa.slug}/",
        HTTP_HOST="demo.localhost:8001",
    )

    assert response.status_code == 200
    composition = response.json()["composition"]
    assert composition is not None
    assert composition["enabled"] is True
    assert composition["max_parts"] == 2


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_checkout_with_composition_charges_highest(api_client, pizza_setup):
    from apps.orders.models import Order, OrderItem, OrderItemComponent

    _, calabresa, portuguesa = pizza_setup

    response = api_client.post(
        "/api/v1/public/orders/checkout/",
        {
            "customer_name": "Maria",
            "customer_phone": "(11) 98765-4321",
            "delivery_type": "pickup",
            "payment_method": "pix",
            "items": [
                {
                    "product_id": str(calabresa.id),
                    "quantity": 1,
                    "components": [str(portuguesa.id)],
                },
            ],
        },
        format="json",
        HTTP_HOST="demo.localhost:8001",
    )

    assert response.status_code == 201, response.json()
    body = response.json()
    # regra "highest": cobra 50 (portuguesa), não 40 (calabresa)
    assert Decimal(str(body["total"])) == Decimal("50.00")

    order = Order.all_objects.get(id=body["id"])
    item = OrderItem.all_objects.filter(order=order).first()
    components = OrderItemComponent.all_objects.filter(order_item=item)
    assert components.count() == 1
    assert components.first().product_name == "Pizza Portuguesa"


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_checkout_rejects_wrong_part_count(api_client, pizza_setup):
    _, calabresa, _ = pizza_setup

    # composição exige 2 partes (1 extra); mandar 0 extras deve falhar
    response = api_client.post(
        "/api/v1/public/orders/checkout/",
        {
            "customer_name": "Maria",
            "customer_phone": "(11) 98765-4321",
            "delivery_type": "pickup",
            "payment_method": "pix",
            "items": [{"product_id": str(calabresa.id), "quantity": 1}],
        },
        format="json",
        HTTP_HOST="demo.localhost:8001",
    )

    # erro de composição vira 422 (regra de negócio)
    assert response.status_code == 422


@pytest.mark.django_db
def test_composed_base_price_rules(pizza_setup):
    _, calabresa, portuguesa = pizza_setup
    parts = [calabresa, portuguesa]

    calabresa.composition.pricing_rule = "highest"
    assert CompositionService.composed_base_price(calabresa, parts) == Decimal("50.00")

    calabresa.composition.pricing_rule = "average"
    assert CompositionService.composed_base_price(calabresa, parts) == Decimal("45.00")

    calabresa.composition.pricing_rule = "main"
    assert CompositionService.composed_base_price(calabresa, parts) == Decimal("40.00")
