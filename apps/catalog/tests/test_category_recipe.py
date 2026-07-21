"""Fase 2 — receita da categoria (capabilities + libraries)."""

from decimal import Decimal

import pytest

from apps.catalog.domain.enums import OptionPriceType
from apps.catalog.models import (
    Category,
    CategoryCapability,
    CategoryLibrary,
    Option,
    OptionGroup,
)
from apps.catalog.services.category_recipe_service import (
    CategoryRecipeError,
    CategoryRecipeService,
)
from apps.companies.services.onboarding_service import OnboardingService


@pytest.fixture
def recipe_setup(db):
    company = OnboardingService.create_company(
        trade_name="Receita Demo",
        subdomain="receita-fase2",
        email="contato@receita.com",
        owner_email="admin@receita.com",
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
    return {
        "company": company,
        "category": category,
        "group": group,
        "pequena": pequena,
        "grande": grande,
    }


@pytest.mark.django_db
def test_replace_recipe_roundtrip(recipe_setup):
    category = recipe_setup["category"]
    group = recipe_setup["group"]
    pequena = recipe_setup["pequena"]
    grande = recipe_setup["grande"]

    result = CategoryRecipeService.replace(
        category,
        data={
            "template_key": "pizza",
            "capabilities": [
                {
                    "kind": "size",
                    "enabled": True,
                    "is_required": True,
                    "sort_order": 0,
                    "settings": {},
                },
                {
                    "kind": "half",
                    "enabled": True,
                    "is_required": False,
                    "sort_order": 1,
                    "settings": {"max_parts": 2, "pricing_rule": "highest"},
                },
            ],
            "libraries": [
                {
                    "kind": "size",
                    "option_group_id": str(group.id),
                    "sort_order": 0,
                    "option_ids": [str(pequena.id), str(grande.id)],
                }
            ],
        },
    )

    assert result["template_key"] == "pizza"
    assert len(result["capabilities"]) == 2
    assert result["libraries"][0]["option_group_name"] == "Tamanho"
    assert len(result["libraries"][0]["options"]) == 2
    assert CategoryCapability.all_objects.filter(category=category).count() == 2
    assert CategoryLibrary.all_objects.filter(category=category).count() == 1
    group.refresh_from_db()
    assert group.kind == "size"


@pytest.mark.django_db
def test_replace_rejects_empty_options(recipe_setup):
    category = recipe_setup["category"]
    group = recipe_setup["group"]

    with pytest.raises(CategoryRecipeError):
        CategoryRecipeService.replace(
            category,
            data={
                "capabilities": [{"kind": "size", "enabled": True}],
                "libraries": [
                    {
                        "kind": "size",
                        "option_group_id": str(group.id),
                        "option_ids": [],
                    }
                ],
            },
        )


@pytest.mark.django_db
def test_admin_recipe_get_put(api_client, recipe_setup):
    category = recipe_setup["category"]
    group = recipe_setup["group"]
    pequena = recipe_setup["pequena"]

    login = api_client.post(
        "/api/v1/auth/login/",
        {
            "email": "admin@receita.com",
            "password": "demo1234",
            "subdomain": "receita-fase2",
        },
        format="json",
    ).json()
    headers = {"HTTP_AUTHORIZATION": f"Bearer {login['access']}"}

    empty = api_client.get(
        f"/api/v1/admin/categories/{category.id}/recipe/",
        **headers,
    )
    assert empty.status_code == 200
    assert empty.json()["capabilities"] == []

    put = api_client.put(
        f"/api/v1/admin/categories/{category.id}/recipe/",
        {
            "capabilities": [
                {"kind": "size", "enabled": True, "is_required": True, "sort_order": 0}
            ],
            "libraries": [
                {
                    "kind": "size",
                    "option_group_id": str(group.id),
                    "option_ids": [str(pequena.id)],
                }
            ],
        },
        format="json",
        **headers,
    )
    assert put.status_code == 200
    body = put.json()
    assert body["capabilities"][0]["kind"] == "size"
    assert body["libraries"][0]["options"][0]["name"] == "Pequena"

    # lista marca has_recipe
    listing = api_client.get("/api/v1/admin/categories/", **headers)
    assert listing.status_code == 200
    row = next(c for c in listing.json() if c["id"] == str(category.id))
    assert row["has_recipe"] is True
