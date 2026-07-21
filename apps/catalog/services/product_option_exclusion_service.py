"""Exclusões de opção no produto — “não oferece este item da receita”."""

from django.db import transaction

from apps.catalog.models import Product, ProductOptionExclusion
from apps.catalog.services.catalog_cache import invalidate_product_cache


class ProductOptionExclusionService:
    @staticmethod
    @transaction.atomic
    def sync(product: Product, option_ids: list, *, replace: bool = True) -> int:
        """Grava exclusões. replace=True troca a lista inteira."""
        normalized = [str(oid) for oid in option_ids if oid]
        kept: set[str] = set()

        for option_id in normalized:
            obj, _ = ProductOptionExclusion.all_objects.update_or_create(
                product=product,
                option_id=option_id,
                defaults={"tenant_id": product.tenant_id},
            )
            kept.add(str(obj.option_id))

        if replace:
            ProductOptionExclusion.all_objects.filter(product=product).exclude(
                option_id__in=kept
            ).delete()

        invalidate_product_cache(product.tenant_id, product.slug)
        return len(kept)
