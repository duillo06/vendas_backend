from decimal import Decimal

import pytest

from apps.catalog.domain.enums import OptionPriceType
from apps.catalog.models import Option, OptionGroup
from apps.catalog.services.pricing_engine import PricingEngine
from apps.catalog.services.price_calculator import PriceCalculator
from apps.catalog.services.product_service import ProductService
from apps.companies.services.onboarding_service import OnboardingService


@pytest.fixture
def pricing_setup(db):
    company = OnboardingService.create_company(
        trade_name="Pricing Demo",
        subdomain="demo-pricing",
        email="p@demo.com",
        owner_email="admin@demo.com",
        owner_password="demo1234",
    )

    from apps.catalog.models import Category

    category = Category.all_objects.create(
        tenant=company,
        name="Pizzas",
        slug="pizzas",
        sort_order=0,
    )

    flavors = OptionGroup.all_objects.create(
        tenant=company,
        name="Sabores",
        selection_type="multiple",
        selection_mode="pick",
        min_selections=2,
        max_selections=2,
        is_required=True,
        pricing_config={"strategy": "charge_extras_only", "included_count": 1},
    )

    s1 = Option.all_objects.create(
        tenant=company,
        option_group=flavors,
        name="Calabresa",
        price_modifier=Decimal("5"),
        price_type=OptionPriceType.FIXED,
    )
    s2 = Option.all_objects.create(
        tenant=company,
        option_group=flavors,
        name="Frango",
        price_modifier=Decimal("7"),
        price_type=OptionPriceType.FIXED,
    )

    extras = OptionGroup.all_objects.create(
        tenant=company,
        name="Adicionais",
        selection_type="multiple",
        selection_mode="quantity",
        min_selections=0,
        max_selections=0,
        is_required=False,
        pricing_config={"strategy": "quantity_multiplier"},
    )

    bacon = Option.all_objects.create(
        tenant=company,
        option_group=extras,
        name="Bacon",
        price_modifier=Decimal("3"),
        price_type=OptionPriceType.FIXED,
    )

    product = ProductService.create(
        tenant=company,
        data={
            "name": "Pizza",
            "slug": "pizza",
            "description": "Pizza",
            "base_price": Decimal("40.00"),
            "category_id": category.id,
            "option_group_ids": [flavors.id, extras.id],
        },
    )

    return {
        "product": product,
        "flavors": flavors,
        "extras": extras,
        "s1": s1,
        "s2": s2,
        "bacon": bacon,
    }


@pytest.mark.django_db
def test_charge_extras_only_first_flavor_free(pricing_setup):
    product = pricing_setup["product"]
    flavors = pricing_setup["flavors"]
    s1 = pricing_setup["s1"]
    s2 = pricing_setup["s2"]

    selected = PriceCalculator.validate_selections(
        product,
        {
            str(flavors.id): [
                {"option_id": str(s1.id), "quantity": 1},
                {"option_id": str(s2.id), "quantity": 1},
            ],
        },
    )
    total = PriceCalculator.calculate_item_price(product, selected)
    # base 40 + segundo sabor 7 (primeiro incluso)
    assert total == Decimal("47.00")


@pytest.mark.django_db
def test_quantity_multiplier_extras(pricing_setup):
    product = pricing_setup["product"]
    flavors = pricing_setup["flavors"]
    extras = pricing_setup["extras"]
    s1 = pricing_setup["s1"]
    s2 = pricing_setup["s2"]
    bacon = pricing_setup["bacon"]

    selected = PriceCalculator.validate_selections(
        product,
        {
            str(flavors.id): [
                {"option_id": str(s1.id), "quantity": 1},
                {"option_id": str(s2.id), "quantity": 1},
            ],
            str(extras.id): [{"option_id": str(bacon.id), "quantity": 2}],
        },
    )
    total = PriceCalculator.calculate_item_price(product, selected)
    # 40 + 7 (1 sabor extra) + 6 (2x bacon)
    assert total == Decimal("53.00")


@pytest.mark.django_db
def test_pricing_engine_first_n_free():
    base = Decimal("20")
    o1 = Option(price_modifier=Decimal("4"), price_type=OptionPriceType.FIXED)
    o2 = Option(price_modifier=Decimal("5"), price_type=OptionPriceType.FIXED)

    total = PricingEngine.apply_group(
        base_price=base,
        entries=[(o1, 1), (o2, 1)],
        pricing_config={"strategy": "first_n_free", "free_count": 1},
    )
    assert total == Decimal("5.00")


def test_pricing_engine_product_price_override_wins():
    """preço no produto ganha do price_modifier legado"""
    base = Decimal("40")
    option = Option(price_modifier=Decimal("8"), price_type=OptionPriceType.FIXED)
    option.pk = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    total = PricingEngine.apply_group(
        base_price=base,
        entries=[(option, 1)],
        pricing_config={"strategy": "additive"},
        price_overrides={str(option.pk): Decimal("12")},
    )
    assert total == Decimal("12.00")
