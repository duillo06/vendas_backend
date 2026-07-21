"""Tamanho = preço absoluto (não soma em cima da base)."""

from decimal import Decimal

import pytest

from apps.catalog.domain.enums import OptionPriceType
from apps.catalog.domain.selection_types import SelectedOptionEntry
from apps.catalog.models import (
    Category,
    Option,
    OptionGroup,
    Product,
    ProductOptionGroup,
    ProductOptionPrice,
)
from apps.catalog.services.price_calculator import PriceCalculator
from apps.companies.services.onboarding_service import OnboardingService


@pytest.fixture
def size_setup(db):
    company = OnboardingService.create_company(
        trade_name="Tamanho Abs",
        subdomain="tamanho-abs",
        email="contato@tam.com",
        owner_email="admin@tam.com",
        owner_password="demo1234",
    )
    category = Category.all_objects.create(
        tenant=company, name="Pizzas", slug="pizzas", sort_order=0
    )
    size_group = OptionGroup.all_objects.create(
        tenant=company,
        name="Tamanho",
        kind="size",
        selection_type="single",
        min_selections=1,
        max_selections=1,
        is_required=True,
        pricing_config={"strategy": "replace_base"},
    )
    crust_group = OptionGroup.all_objects.create(
        tenant=company,
        name="Borda",
        kind="crust",
        selection_type="single",
        min_selections=0,
        max_selections=1,
        is_required=False,
        pricing_config={"strategy": "additive"},
    )
    grande = Option.all_objects.create(
        tenant=company,
        option_group=size_group,
        name="Grande",
        price_modifier=Decimal("0"),
        price_type=OptionPriceType.FIXED,
    )
    catupiry = Option.all_objects.create(
        tenant=company,
        option_group=crust_group,
        name="Catupiry",
        price_modifier=Decimal("0"),
        price_type=OptionPriceType.FIXED,
    )
    product = Product.all_objects.create(
        tenant=company,
        category=category,
        name="Manjericao",
        slug="manjericao",
        base_price=Decimal("70"),
    )
    size_link = ProductOptionGroup.all_objects.create(
        tenant=company, product=product, option_group=size_group, sort_order=0
    )
    crust_link = ProductOptionGroup.all_objects.create(
        tenant=company, product=product, option_group=crust_group, sort_order=1
    )
    ProductOptionPrice.all_objects.create(
        tenant=company, product=product, option=grande, price=Decimal("80")
    )
    ProductOptionPrice.all_objects.create(
        tenant=company, product=product, option=catupiry, price=Decimal("10")
    )
    return {
        "product": product,
        "grande": grande,
        "catupiry": catupiry,
        "size_group": size_group,
        "crust_group": crust_group,
        "size_link": size_link,
        "crust_link": crust_link,
    }


@pytest.mark.django_db
def test_size_replaces_base_not_adds(size_setup):
    product = size_setup["product"]
    entries = [
        SelectedOptionEntry(
            option=size_setup["grande"],
            quantity=1,
            group=size_setup["size_group"],
            link=size_setup["size_link"],
        )
    ]
    # era 70+80=150; agora só 80
    assert PriceCalculator.calculate_item_price(product, entries) == Decimal("80.00")


@pytest.mark.django_db
def test_size_plus_crust_addon(size_setup):
    product = size_setup["product"]
    entries = [
        SelectedOptionEntry(
            option=size_setup["grande"],
            quantity=1,
            group=size_setup["size_group"],
            link=size_setup["size_link"],
        ),
        SelectedOptionEntry(
            option=size_setup["catupiry"],
            quantity=1,
            group=size_setup["crust_group"],
            link=size_setup["crust_link"],
        ),
    ]
    # 80 (grande) + 10 (borda)
    assert PriceCalculator.calculate_item_price(product, entries) == Decimal("90.00")
