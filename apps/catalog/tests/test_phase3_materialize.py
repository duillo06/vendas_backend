"""Fase 3 — materialize no create, exclusões, apply_mode, copiar preços."""

from decimal import Decimal

import pytest

from apps.catalog.domain.enums import OptionPriceType
from apps.catalog.models import (
    Category,
    Option,
    OptionGroup,
    ProductOptionExclusion,
    ProductOptionGroup,
    ProductOptionPrice,
)
from apps.catalog.services.category_recipe_service import CategoryRecipeService
from apps.catalog.services.materialize_service import MaterializeService
from apps.catalog.services.product_price_copy_service import ProductPriceCopyService
from apps.catalog.services.product_service import ProductService
from apps.companies.services.onboarding_service import OnboardingService


@pytest.fixture
def phase3_setup(db):
    company = OnboardingService.create_company(
        trade_name="Fase3 Demo",
        subdomain="fase3-demo",
        email="contato@fase3.com",
        owner_email="admin@fase3.com",
        owner_password="demo1234",
    )
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
        kind="size",
    )
    pequena = Option.all_objects.create(
        tenant=company,
        option_group=group,
        name="Pequena",
        price_modifier=Decimal("0"),
        price_type=OptionPriceType.FIXED,
    )
    grande = Option.all_objects.create(
        tenant=company,
        option_group=group,
        name="Grande",
        price_modifier=Decimal("0"),
        price_type=OptionPriceType.FIXED,
    )
    CategoryRecipeService.replace(
        category,
        data={
            "capabilities": [
                {"kind": "size", "enabled": True, "is_required": True, "sort_order": 0}
            ],
            "libraries": [
                {
                    "kind": "size",
                    "option_group_id": str(group.id),
                    "option_ids": [str(pequena.id), str(grande.id)],
                }
            ],
            "apply_mode": "new_only",
        },
    )
    return {
        "company": company,
        "category": category,
        "group": group,
        "pequena": pequena,
        "grande": grande,
    }


@pytest.mark.django_db
def test_create_product_materializes_recipe(phase3_setup):
    company = phase3_setup["company"]
    category = phase3_setup["category"]
    group = phase3_setup["group"]

    product = ProductService.create(
        tenant=company,
        data={
            "name": "Calabresa",
            "slug": "calabresa",
            "description": "",
            "base_price": Decimal("40"),
            "category_id": category.id,
        },
    )

    links = ProductOptionGroup.all_objects.filter(product=product)
    assert links.count() == 1
    assert str(links.first().option_group_id) == str(group.id)


@pytest.mark.django_db
def test_exclusions_and_visible_options(phase3_setup):
    company = phase3_setup["company"]
    category = phase3_setup["category"]
    group = phase3_setup["group"]
    pequena = phase3_setup["pequena"]
    grande = phase3_setup["grande"]

    product = ProductService.create(
        tenant=company,
        data={
            "name": "Mussarela",
            "slug": "mussarela",
            "description": "",
            "base_price": Decimal("35"),
            "category_id": category.id,
            "option_exclusions": [str(grande.id)],
        },
    )
    assert ProductOptionExclusion.all_objects.filter(product=product).count() == 1
    visible = MaterializeService.visible_option_ids(product, group.id)
    assert visible == {str(pequena.id)}


@pytest.mark.django_db
def test_apply_mode_all_rematerializes(phase3_setup):
    company = phase3_setup["company"]
    category = phase3_setup["category"]
    group = phase3_setup["group"]
    pequena = phase3_setup["pequena"]
    grande = phase3_setup["grande"]

    product = ProductService.create(
        tenant=company,
        data={
            "name": "Portuguesa",
            "slug": "portuguesa",
            "description": "",
            "base_price": Decimal("42"),
            "category_id": category.id,
            "from_recipe": False,
        },
    )
    assert ProductOptionGroup.all_objects.filter(product=product).count() == 0

    result = CategoryRecipeService.replace(
        category,
        data={
            "capabilities": [
                {"kind": "size", "enabled": True, "is_required": True, "sort_order": 0}
            ],
            "libraries": [
                {
                    "kind": "size",
                    "option_group_id": str(group.id),
                    "option_ids": [str(pequena.id), str(grande.id)],
                }
            ],
            "apply_mode": "all",
        },
    )
    assert result["apply_result"]["products"] >= 1
    assert ProductOptionGroup.all_objects.filter(product=product).count() == 1


@pytest.mark.django_db
def test_copy_prices_same(phase3_setup):
    company = phase3_setup["company"]
    category = phase3_setup["category"]
    grande = phase3_setup["grande"]

    source = ProductService.create(
        tenant=company,
        data={
            "name": "Calabresa",
            "slug": "calabresa-src",
            "description": "",
            "base_price": Decimal("40"),
            "category_id": category.id,
            "option_prices": [{"option_id": str(grande.id), "price": "15"}],
        },
    )
    target = ProductService.create(
        tenant=company,
        data={
            "name": "Frango",
            "slug": "frango-tgt",
            "description": "",
            "base_price": Decimal("38"),
            "category_id": category.id,
        },
    )

    count = ProductPriceCopyService.copy(target=target, source=source, mode="same")
    assert count >= 1
    row = ProductOptionPrice.all_objects.get(product=target, option=grande)
    assert row.price == Decimal("15.00")
