"""Preços padrão da categoria (Tipo 2 — Fase 5)."""

from decimal import Decimal

from django.db import transaction

from apps.catalog.models import Category, CategoryOptionPrice
from apps.catalog.services.catalog_cache import invalidate_catalog_cache


class CategoryOptionPriceService:
    @staticmethod
    @transaction.atomic
    def sync(
        category: Category,
        entries: list[dict],
        *,
        replace: bool = True,
    ) -> int:
        """Upsert preços. entries: [{option_id, price}, ...]"""
        kept: set[str] = set()
        count = 0

        for raw in entries:
            option_id = raw.get("option_id")
            if not option_id:
                continue
            price = Decimal(str(raw.get("price", 0)))
            if price < 0:
                price = Decimal("0")

            obj, created = CategoryOptionPrice.all_objects.update_or_create(
                category=category,
                option_id=option_id,
                defaults={
                    "tenant_id": category.tenant_id,
                    "price": price,
                },
            )
            kept.add(str(obj.option_id))
            count += 1 if created else 0

        if replace:
            CategoryOptionPrice.all_objects.filter(category=category).exclude(
                option_id__in=kept
            ).delete()

        invalidate_catalog_cache(category.tenant_id)
        return count
