"""Resolução de preço de opção — produto → categoria → legado (doc 17 §8)."""

from decimal import Decimal
from uuid import UUID

from apps.catalog.models import CategoryOptionPrice, Product, ProductOptionPrice
from apps.catalog.services.pricing_engine import PriceOverrides, PricingEngine


class OptionPriceResolver:
    @staticmethod
    def effective_overrides_for_product(product: Product) -> PriceOverrides:
        """Mapa option_id → preço efetivo (sem cair no price_modifier legado).

        Ordem: preços da categoria, depois overlay do produto.
        Quem não está no mapa → PricingEngine usa options.price_modifier.
        """
        result: PriceOverrides = {}
        category_id = getattr(product, "category_id", None)
        if category_id:
            for row in CategoryOptionPrice.all_objects.filter(category_id=category_id):
                result[str(row.option_id)] = Decimal(row.price)

        for row in ProductOptionPrice.all_objects.filter(product=product):
            result[str(row.option_id)] = Decimal(row.price)

        return result

    @staticmethod
    def category_overrides(category_id: str | UUID | None) -> PriceOverrides:
        if not category_id:
            return {}
        return PricingEngine.overrides_from_rows(
            CategoryOptionPrice.all_objects.filter(category_id=category_id)
        )
