from decimal import Decimal

from apps.catalog.domain.enums import OptionSelectionType
from apps.catalog.models import Category
from apps.catalog.services.option_group_service import OptionGroupService
from apps.catalog.services.product_service import ProductService


def seed_demo_catalog(company) -> None:
    if Category.all_objects.filter(tenant=company, slug="lanches").exists():
        return

    lanches = Category.all_objects.create(
        tenant=company,
        name="Lanches",
        slug="lanches",
        description="Sanduíches e salgados",
        sort_order=0,
        is_active=True,
    )

    bebidas = Category.all_objects.create(
        tenant=company,
        name="Bebidas",
        slug="bebidas",
        description="Refrigerantes e sucos",
        sort_order=1,
        is_active=True,
    )

    tamanho = OptionGroupService.create(
        tenant=company,
        data={
            "name": "Tamanho",
            "description": "Escolha o tamanho",
            "selection_type": OptionSelectionType.SINGLE,
            "min_selections": 1,
            "max_selections": 1,
            "is_required": True,
            "sort_order": 0,
            "is_active": True,
        },
    )
    OptionGroupService.create_option(
        group=tamanho,
        data={"name": "Normal", "price_modifier": Decimal("0"), "sort_order": 0},
    )
    OptionGroupService.create_option(
        group=tamanho,
        data={"name": "Duplo", "price_modifier": Decimal("8"), "sort_order": 1},
    )

    ProductService.create(
        tenant=company,
        data={
            "name": "X-Burger",
            "slug": "x-burger",
            "description": "Hambúrguer artesanal com queijo",
            "base_price": Decimal("22.00"),
            "category_id": lanches.id,
            "is_active": True,
            "is_available": True,
            "tags": ["mais-vendido"],
            "option_group_ids": [tamanho.id],
        },
    )

    ProductService.create(
        tenant=company,
        data={
            "name": "Suco de Laranja",
            "slug": "suco-de-laranja",
            "description": "500ml natural",
            "base_price": Decimal("9.00"),
            "category_id": bebidas.id,
            "is_active": True,
            "is_available": True,
            "tags": [],
            "option_group_ids": [],
        },
    )
