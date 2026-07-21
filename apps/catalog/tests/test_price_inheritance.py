"""Fase 5 — herança de preço categoria → produto."""

from decimal import Decimal

import pytest

from apps.catalog.domain.enums import OptionPriceType
from apps.catalog.models import (
    Category,
    CategoryOptionPrice,
    Option,
    OptionGroup,
    Product,
    ProductOptionPrice,
)
from apps.catalog.services.category_recipe_service import CategoryRecipeService
from apps.catalog.services.option_price_resolver import OptionPriceResolver
from apps.catalog.services.price_calculator import PriceCalculator
from apps.companies.services.onboarding_service import OnboardingService


@pytest.fixture
def inherit_setup(db):
    company = OnboardingService.create_company(
        trade_name="Herança Demo",
        subdomain="heranca-fase5",
        email="contato@heranca.com",
        owner_email="admin@heranca.com",
        owner_password="demo1234",
    )
    category = Category.all_objects.create(
        tenant=company,
        name="Pizzas",
        slug="pizzas",
        sort_order=0,
    )
    size_group = OptionGroup.all_objects.create(
        tenant=company,
        name="Tamanho",
        kind="size",
        selection_type="single",
        min_selections=1,
        max_selections=1,
        is_required=True,
    )
    crust_group = OptionGroup.all_objects.create(
        tenant=company,
        name="Borda",
        kind="crust",
        selection_type="single",
        min_selections=0,
        max_selections=1,
        is_required=False,
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
        price_modifier=Decimal("99"),  # legado — não deve ganhar se houver categoria
        price_type=OptionPriceType.FIXED,
    )
    product = Product.all_objects.create(
        tenant=company,
        category=category,
        name="Calabresa",
        slug="calabresa",
        base_price=Decimal("40"),
    )
    return {
        "company": company,
        "category": category,
        "size_group": size_group,
        "crust_group": crust_group,
        "grande": grande,
        "catupiry": catupiry,
        "product": product,
    }


@pytest.mark.django_db
def test_recipe_stores_category_option_prices(inherit_setup):
    category = inherit_setup["category"]
    crust_group = inherit_setup["crust_group"]
    catupiry = inherit_setup["catupiry"]

    result = CategoryRecipeService.replace(
        category,
        data={
            "capabilities": [
                {"kind": "crust", "enabled": True, "is_required": False, "sort_order": 0},
            ],
            "libraries": [
                {
                    "kind": "crust",
                    "option_group_id": str(crust_group.id),
                    "option_ids": [str(catupiry.id)],
                }
            ],
            "option_prices": [{"option_id": str(catupiry.id), "price": "10.00"}],
        },
    )

    assert result["option_prices"] == [
        {"option_id": str(catupiry.id), "price": 10.0},
    ]
    assert CategoryOptionPrice.all_objects.filter(
        category=category, option=catupiry, price=Decimal("10.00")
    ).exists()


@pytest.mark.django_db
def test_resolver_product_wins_over_category(inherit_setup):
    category = inherit_setup["category"]
    product = inherit_setup["product"]
    catupiry = inherit_setup["catupiry"]

    CategoryOptionPrice.all_objects.create(
        tenant=category.tenant,
        category=category,
        option=catupiry,
        price=Decimal("10"),
    )
    ProductOptionPrice.all_objects.create(
        tenant=product.tenant,
        product=product,
        option=catupiry,
        price=Decimal("15"),
    )

    overrides = OptionPriceResolver.effective_overrides_for_product(product)
    assert overrides[str(catupiry.id)] == Decimal("15")


@pytest.mark.django_db
def test_resolver_falls_back_to_category(inherit_setup):
    category = inherit_setup["category"]
    product = inherit_setup["product"]
    catupiry = inherit_setup["catupiry"]

    CategoryOptionPrice.all_objects.create(
        tenant=category.tenant,
        category=category,
        option=catupiry,
        price=Decimal("10"),
    )

    overrides = OptionPriceResolver.effective_overrides_for_product(product)
    assert overrides[str(catupiry.id)] == Decimal("10")


@pytest.mark.django_db
def test_calculator_uses_category_price_without_product_row(inherit_setup):
    """Sem preço no produto, engine usa o da categoria (não o legado 99)."""
    from apps.catalog.models import ProductOptionGroup
    from apps.catalog.domain.selection_types import SelectedOptionEntry

    category = inherit_setup["category"]
    product = inherit_setup["product"]
    catupiry = inherit_setup["catupiry"]
    crust_group = inherit_setup["crust_group"]

    CategoryOptionPrice.all_objects.create(
        tenant=category.tenant,
        category=category,
        option=catupiry,
        price=Decimal("10"),
    )
    link = ProductOptionGroup.all_objects.create(
        tenant=product.tenant,
        product=product,
        option_group=crust_group,
        sort_order=0,
    )

    # PriceCalculator precisa de SelectedOptionEntry — monta na mão
    entry = SelectedOptionEntry(
        group=crust_group,
        option=catupiry,
        quantity=1,
        link=link,
    )
    total = PriceCalculator.calculate_item_price(product, [entry])
    # base 40 + catupiry 10
    assert total == Decimal("50.00")
