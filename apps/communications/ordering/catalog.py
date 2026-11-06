from __future__ import annotations

from django.conf import settings
from django.db.models import Q

from apps.catalog.models import Category, Product
from apps.catalog.serializers.public_serializers import ProductDetailPublicSerializer
from apps.catalog.services.composition_service import CompositionService
from apps.companies.models import Company


def product_public_url(tenant: Company, slug: str) -> str:
    domain = getattr(settings, "STOREFRONT_BASE_DOMAIN", "") or "localhost"
    if "localhost" in domain:
        return f"http://{tenant.subdomain}.localhost:5174/produto/{slug}"
    return f"https://{tenant.subdomain}.{domain}/produto/{slug}"


def list_categories(tenant: Company) -> list[Category]:
    alive = Q(products__is_active=True, products__is_available=True, products__deleted_at__isnull=True)
    return list(
        Category.all_objects.filter(tenant=tenant, is_active=True, deleted_at__isnull=True)
        .filter(alive)
        .distinct()
        .order_by("sort_order", "name")
    )


def list_products(tenant: Company, category_id: str) -> list[Product]:
    return list(
        Product.all_objects.filter(
            tenant=tenant,
            category_id=category_id,
            is_active=True,
            is_available=True,
            deleted_at__isnull=True,
        ).order_by("sort_order", "name")
    )


def load_product(tenant: Company, product_id: str) -> Product | None:
    try:
        return (
            Product.all_objects.select_related("category", "composition")
            .prefetch_related(
                "images",
                "product_option_groups__option_group__options",
            )
            .get(
                tenant=tenant,
                id=product_id,
                is_active=True,
                is_available=True,
                deleted_at__isnull=True,
            )
        )
    except Product.DoesNotExist:
        return None


def snapshot_product(product: Product) -> dict:
    data = ProductDetailPublicSerializer(product).data
    groups = []
    for group in data.get("option_groups") or []:
        options = [
            {
                "id": option["id"],
                "name": option["name"],
                "price": option["price_modifier"],
            }
            for option in group.get("options") or []
            if option.get("is_available")
        ]
        groups.append(
            {
                "id": group["id"],
                "name": group["name"],
                "kind": group.get("kind") or "",
                "selection_type": group["selection_type"],
                "selection_mode": group["selection_mode"],
                "min": int(group.get("min_selections") or 0),
                "max": int(group.get("max_selections") or 0),
                "required": bool(group.get("is_required")),
                "options": options,
            }
        )
    composition = data.get("composition") or None
    if composition and not composition.get("enabled"):
        composition = None
    return {
        "product_id": data["id"],
        "name": data["name"],
        "slug": data["slug"],
        "groups": groups,
        "composition": composition,
    }


def flavor_candidates(product: Product) -> list[Product]:
    return list(CompositionService.get_candidates(product))
