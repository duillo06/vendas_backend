"""Fase 1 — preços no produto (ProductOptionPrice) + dual-read público."""

from decimal import Decimal

import pytest
from django.test import override_settings

from apps.catalog.domain.enums import OptionPriceType
from apps.catalog.models import Option, OptionGroup, ProductOptionPrice
from apps.catalog.services.price_calculator import PriceCalculator
from apps.catalog.services.product_option_price_service import ProductOptionPriceService
from apps.catalog.services.product_service import ProductService
from apps.companies.services.onboarding_service import OnboardingService


@pytest.fixture
def price_setup(db):
    company = OnboardingService.create_company(
        trade_name="Pizzaria Preço",
        subdomain="preco-fase1",
        email="contato@preco.com",
        owner_email="admin@preco.com",
        owner_password="demo1234",
    )

    from apps.catalog.models import Category

    category = Category.all_objects.create(
        tenant=company,
        name="Pizzas",
        slug="pizzas",
        sort_order=0,
    )

    group = OptionGroup.all_objects.create(
        tenant=company,
        name="Tamanho",
        selection_type="single",
        min_selections=1,
        max_selections=1,
        is_required=True,
    )

    # identidade na base — price_modifier 0
    grande = Option.all_objects.create(
        tenant=company,
        option_group=group,
        name="Grande",
        price_modifier=Decimal("0"),
        price_type=OptionPriceType.FIXED,
    )

    product_a = ProductService.create(
        tenant=company,
        data={
            "name": "Calabresa",
            "slug": "calabresa",
            "description": "",
            "base_price": Decimal("40.00"),
            "category_id": category.id,
            "option_group_ids": [group.id],
            "option_prices": [{"option_id": str(grande.id), "price": "15.00"}],
        },
    )

    product_b = ProductService.create(
        tenant=company,
        data={
            "name": "Mussarela",
            "slug": "mussarela",
            "description": "",
            "base_price": Decimal("35.00"),
            "category_id": category.id,
            "option_group_ids": [group.id],
            "option_prices": [{"option_id": str(grande.id), "price": "10.00"}],
        },
    )

    return {
        "company": company,
        "group": group,
        "grande": grande,
        "product_a": product_a,
        "product_b": product_b,
    }


def _sel(group_id, option_id):
    return {str(group_id): [{"option_id": str(option_id), "quantity": 1}]}


@pytest.mark.django_db
def test_same_option_different_product_prices(price_setup):
    group = price_setup["group"]
    grande = price_setup["grande"]
    a = price_setup["product_a"]
    b = price_setup["product_b"]

    total_a = PriceCalculator.calculate_item_price(
        a, PriceCalculator.validate_selections(a, _sel(group.id, grande.id))
    )
    total_b = PriceCalculator.calculate_item_price(
        b, PriceCalculator.validate_selections(b, _sel(group.id, grande.id))
    )

    assert total_a == Decimal("55.00")
    assert total_b == Decimal("45.00")


@pytest.mark.django_db
def test_sync_option_prices_upsert(price_setup):
    product = price_setup["product_a"]
    grande = price_setup["grande"]

    ProductOptionPriceService.sync(
        product,
        [{"option_id": str(grande.id), "price": "20"}],
    )
    row = ProductOptionPrice.all_objects.get(product=product, option=grande)
    assert row.price == Decimal("20.00")


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_public_product_detail_uses_product_price(api_client, price_setup):
    product = price_setup["product_a"]
    response = api_client.get(
        f"/api/v1/public/catalog/products/{product.slug}/",
        HTTP_HOST="preco-fase1.localhost:8001",
    )
    assert response.status_code == 200
    body = response.json()
    options = body["option_groups"][0]["options"]
    grande = next(o for o in options if o["name"] == "Grande")
    assert grande["price_modifier"] == 15.0


@pytest.mark.django_db
def test_admin_patch_option_prices(api_client, price_setup):
    company = price_setup["company"]
    product = price_setup["product_a"]
    grande = price_setup["grande"]

    login = api_client.post(
        "/api/v1/auth/login/",
        {"email": "admin@preco.com", "password": "demo1234", "subdomain": "preco-fase1"},
        format="json",
    ).json()

    response = api_client.patch(
        f"/api/v1/admin/products/{product.id}/",
        {"option_prices": [{"option_id": str(grande.id), "price": 22}]},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
        HTTP_HOST="preco-fase1.localhost:8001",
    )
    assert response.status_code == 200
    body = response.json()
    assert any(
        row["option_id"] == str(grande.id) and float(row["price"]) == 22.0
        for row in body["option_prices"]
    )
    assert ProductOptionPrice.all_objects.get(product=product, option=grande).price == Decimal("22")
