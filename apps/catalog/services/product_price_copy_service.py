"""Copia preços de um produto para outro (mesma base de opções)."""

from decimal import Decimal

from django.db import transaction

from apps.catalog.models import Product, ProductOptionPrice
from apps.catalog.services.catalog_cache import invalidate_product_cache
from apps.catalog.services.product_option_price_service import ProductOptionPriceService


class ProductPriceCopyError(Exception):
    def __init__(self, message: str, code: str = "copy_prices_failed"):
        self.message = message
        self.code = code
        super().__init__(message)


class ProductPriceCopyService:
    @staticmethod
    @transaction.atomic
    def copy(
        *,
        target: Product,
        source: Product,
        mode: str = "same",
        percent: Decimal | None = None,
        fixed: Decimal | None = None,
    ) -> int:
        """mode: same | percent | fixed — só opções que o target também usa."""
        if source.tenant_id != target.tenant_id:
            raise ProductPriceCopyError("Produtos de estabelecimentos diferentes")
        if str(source.id) == str(target.id):
            raise ProductPriceCopyError("Escolha outro produto pra copiar")

        source_rows = list(
            ProductOptionPrice.all_objects.filter(product=source).values("option_id", "price")
        )
        if not source_rows:
            raise ProductPriceCopyError("Esse produto ainda não tem preços de opção")

        # opções vinculadas ao target (via grupos)
        target_option_ids = set()
        for link in target.product_option_groups.select_related("option_group").all():
            for opt in link.option_group.options.all():
                target_option_ids.add(str(opt.id))

        entries = []
        for row in source_rows:
            oid = str(row["option_id"])
            if target_option_ids and oid not in target_option_ids:
                continue
            price = Decimal(row["price"])
            if mode == "percent":
                pct = Decimal(str(percent if percent is not None else 0))
                price = (price * (Decimal("100") + pct) / Decimal("100")).quantize(
                    Decimal("0.01")
                )
            elif mode == "fixed":
                price = Decimal(str(fixed if fixed is not None else 0))
            if price < 0:
                price = Decimal("0")
            entries.append({"option_id": oid, "price": price})

        if not entries:
            raise ProductPriceCopyError(
                "Não achamos opções em comum pra copiar os preços"
            )

        ProductOptionPriceService.sync(target, entries, replace=False)
        invalidate_product_cache(target.tenant_id, target.slug)
        return len(entries)
