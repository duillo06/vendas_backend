"""Preços de opção no produto — fonte da verdade na autoria nova (Fase 1)."""

from decimal import Decimal

from django.db import transaction

from apps.catalog.models import Product, ProductOptionPrice
from apps.catalog.services.catalog_cache import invalidate_product_cache


class ProductOptionPriceService:
    @staticmethod
    @transaction.atomic
    def sync(
        product: Product,
        entries: list[dict],
        *,
        replace: bool = False,
    ) -> int:
        """Upsert preços. entries: [{option_id, price}, ...]

        replace=True remove preços que não vieram na lista.
        """
        kept: set[str] = set()
        count = 0

        for raw in entries:
            option_id = raw.get("option_id")
            if not option_id:
                continue
            price = Decimal(str(raw.get("price", 0)))
            if price < 0:
                price = Decimal("0")

            obj, created = ProductOptionPrice.all_objects.update_or_create(
                product=product,
                option_id=option_id,
                defaults={
                    "tenant_id": product.tenant_id,
                    "price": price,
                },
            )
            kept.add(str(obj.option_id))
            count += 1 if created else 0

        if replace:
            ProductOptionPrice.all_objects.filter(product=product).exclude(
                option_id__in=kept
            ).delete()

        invalidate_product_cache(product.tenant_id, product.slug)
        return count
