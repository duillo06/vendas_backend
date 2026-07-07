from django.core.cache import cache

from core.cache.keys import tenant_key


def invalidate_catalog_cache(tenant_id) -> None:
    tenant_id = str(tenant_id)
    cache.delete(tenant_key(tenant_id, "catalog", "categories"))
    cache.delete(tenant_key(tenant_id, "catalog", "products"))


def invalidate_product_cache(tenant_id, slug: str) -> None:
    tenant_id = str(tenant_id)
    cache.delete(tenant_key(tenant_id, "catalog", "product", slug))
    invalidate_catalog_cache(tenant_id)
