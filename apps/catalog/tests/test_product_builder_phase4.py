from decimal import Decimal

import pytest

from apps.catalog.domain.enums import OptionPriceType
from apps.catalog.domain.exceptions import InvalidOptionSelection
from apps.catalog.models import Option, OptionGroup
from apps.catalog.services.option_stock_service import OptionStockService
from apps.catalog.services.pricing_engine import PricingEngine
from apps.catalog.services.product_service import ProductService
from apps.catalog.services.selection_validator import SelectionValidator
from apps.companies.services.onboarding_service import OnboardingService


@pytest.fixture
def phase4_setup(db):
    company = OnboardingService.create_company(
        trade_name="Phase4 Demo",
        subdomain="demo-phase4",
        email="p4@demo.com",
        owner_email="admin@demo.com",
        owner_password="demo1234",
    )

    from apps.catalog.models import Category

    category = Category.all_objects.create(
        tenant=company,
        name="Bebidas",
        slug="bebidas",
        sort_order=0,
    )

    size_group = OptionGroup.all_objects.create(
        tenant=company,
        name="Tamanho",
        selection_type="single",
        min_selections=1,
        max_selections=1,
        is_required=True,
    )
    small = Option.all_objects.create(
        tenant=company,
        option_group=size_group,
        name="300ml",
        price_modifier=Decimal("0"),
    )
    large = Option.all_objects.create(
        tenant=company,
        option_group=size_group,
        name="500ml",
        price_modifier=Decimal("2"),
    )

    extras = OptionGroup.all_objects.create(
        tenant=company,
        name="Extras",
        selection_type="multiple",
        selection_mode="quantity",
        min_selections=0,
        max_selections=0,
        is_required=False,
        visibility="conditional",
        ui_config={
            "show_when": {
                "group_id": str(size_group.id),
                "option_ids": [str(large.id)],
            },
        },
        pricing_config={
            "strategy": "tiered",
            "tiers": [
                {"from": 1, "to": 2, "unit_price": 3},
                {"from": 3, "unit_price": 2},
            ],
        },
    )
    gelo = Option.all_objects.create(
        tenant=company,
        option_group=extras,
        name="Gelo extra",
        price_modifier=Decimal("1"),
        stock_quantity=2,
    )

    product = ProductService.create(
        tenant=company,
        data={
            "name": "Suco",
            "slug": "suco",
            "description": "Suco",
            "base_price": Decimal("10.00"),
            "category_id": category.id,
            "option_group_ids": [size_group.id, extras.id],
        },
    )

    return {
        "product": product,
        "size_group": size_group,
        "extras": extras,
        "small": small,
        "large": large,
        "gelo": gelo,
    }


@pytest.mark.django_db
def test_tiered_pricing_by_total_quantity():
    option = Option(price_modifier=Decimal("9"), price_type=OptionPriceType.FIXED)
    total = PricingEngine.apply_group(
        base_price=Decimal("10"),
        entries=[(option, 2)],
        pricing_config={
            "strategy": "tiered",
            "tiers": [
                {"from": 1, "to": 2, "unit_price": 3},
                {"from": 3, "unit_price": 2},
            ],
        },
    )
    assert total == Decimal("6.00")


@pytest.mark.django_db
def test_conditional_group_rejects_selection_without_trigger(phase4_setup):
    product = phase4_setup["product"]
    size_group = phase4_setup["size_group"]
    extras = phase4_setup["extras"]
    small = phase4_setup["small"]

    with pytest.raises(InvalidOptionSelection):
        SelectionValidator.validate(
            product,
            {
                str(size_group.id): [{"option_id": str(small.id), "quantity": 1}],
                str(extras.id): [{"option_id": str(phase4_setup["gelo"].id), "quantity": 1}],
            },
        )


@pytest.mark.django_db
def test_conditional_group_valid_when_trigger_selected(phase4_setup):
    product = phase4_setup["product"]
    size_group = phase4_setup["size_group"]
    extras = phase4_setup["extras"]
    large = phase4_setup["large"]
    gelo = phase4_setup["gelo"]

    selected = SelectionValidator.validate(
        product,
        {
            str(size_group.id): [{"option_id": str(large.id), "quantity": 1}],
            str(extras.id): [{"option_id": str(gelo.id), "quantity": 1}],
        },
    )
    assert len(selected) == 2


@pytest.mark.django_db
def test_stock_validation_blocks_over_quantity(phase4_setup):
    product = phase4_setup["product"]
    size_group = phase4_setup["size_group"]
    extras = phase4_setup["extras"]
    large = phase4_setup["large"]
    gelo = phase4_setup["gelo"]

    with pytest.raises(InvalidOptionSelection):
        SelectionValidator.validate(
            product,
            {
                str(size_group.id): [{"option_id": str(large.id), "quantity": 1}],
                str(extras.id): [{"option_id": str(gelo.id), "quantity": 3}],
            },
        )


@pytest.mark.django_db
def test_stock_decrement_on_order(phase4_setup):
    gelo = phase4_setup["gelo"]
    validated_items = [
        {
            "quantity": 1,
            "options": [{"option_id": str(gelo.id), "quantity": 2}],
        },
    ]

    OptionStockService.decrement_for_order(validated_items=validated_items)
    gelo.refresh_from_db()
    assert gelo.stock_quantity == 0
    assert gelo.is_available is False
