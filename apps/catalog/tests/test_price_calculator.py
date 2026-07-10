from decimal import Decimal

import pytest

from apps.catalog.domain.enums import OptionPriceType
from apps.catalog.domain.exceptions import InvalidOptionSelection
from apps.catalog.models import Option, OptionGroup
from apps.catalog.services.price_calculator import PriceCalculator
from apps.companies.services.onboarding_service import OnboardingService


@pytest.fixture
def catalog_setup(db):
    company = OnboardingService.create_company(
        trade_name="Lanchonete Demo",
        subdomain="demo-catalog",
        email="contato@catalog.com",
        owner_email="admin@catalog.com",
        owner_password="demo1234",
    )

    from apps.catalog.models import Category
    from apps.catalog.services.product_service import ProductService

    category = Category.all_objects.create(
        tenant=company,
        name="Lanches",
        slug="lanches",
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

    small = Option.all_objects.create(
        tenant=company,
        option_group=group,
        name="Normal",
        price_modifier=Decimal("0"),
        price_type=OptionPriceType.FIXED,
    )
    large = Option.all_objects.create(
        tenant=company,
        option_group=group,
        name="Duplo",
        price_modifier=Decimal("10"),
        price_type=OptionPriceType.FIXED,
    )

    product = ProductService.create(
        tenant=company,
        data={
            "name": "X-Burger",
            "slug": "x-burger",
            "description": "Burger",
            "base_price": Decimal("20.00"),
            "category_id": category.id,
            "option_group_ids": [group.id],
        },
    )

    return {
        "company": company,
        "product": product,
        "group": group,
        "small": small,
        "large": large,
    }


def _sel(group_id, option_id, quantity=1):
    return {str(group_id): [{"option_id": str(option_id), "quantity": quantity}]}


@pytest.mark.django_db
def test_price_calculator_fixed_modifier(catalog_setup):
    product = catalog_setup["product"]
    large = catalog_setup["large"]
    group = catalog_setup["group"]

    selected = PriceCalculator.validate_selections(product, _sel(group.id, large.id))
    total = PriceCalculator.calculate_item_price(product, selected)
    assert total == Decimal("30.00")


@pytest.mark.django_db
def test_price_calculator_percentage_modifier(catalog_setup):
    product = catalog_setup["product"]
    group = catalog_setup["group"]

    percent = Option.all_objects.create(
        tenant=product.tenant,
        option_group=group,
        name="Premium",
        price_modifier=Decimal("10"),
        price_type=OptionPriceType.PERCENTAGE,
    )

    selected = PriceCalculator.validate_selections(product, _sel(group.id, percent.id))
    total = PriceCalculator.calculate_item_price(product, selected)
    assert total == Decimal("22.00")


@pytest.mark.django_db
def test_validate_selections_required_group(catalog_setup):
    product = catalog_setup["product"]
    group = catalog_setup["group"]
    large = catalog_setup["large"]

    selected = PriceCalculator.validate_selections(product, _sel(group.id, large.id))
    assert len(selected) == 1

    with pytest.raises(InvalidOptionSelection):
        PriceCalculator.validate_selections(product, {str(group.id): []})


@pytest.mark.django_db
def test_validate_legacy_option_without_quantity(catalog_setup):
    product = catalog_setup["product"]
    group = catalog_setup["group"]
    large = catalog_setup["large"]

    selected = PriceCalculator.validate_selections(
        product,
        {str(group.id): [{"option_id": str(large.id)}]},
    )
    assert selected[0].quantity == 1
