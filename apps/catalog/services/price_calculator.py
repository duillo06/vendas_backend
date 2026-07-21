from decimal import Decimal

from apps.catalog.domain.enums import PRODUCT_PRICE_KINDS
from apps.catalog.domain.selection_types import SelectedOptionEntry
from apps.catalog.models import Product
from apps.catalog.services.group_config import effective_group_fields
from apps.catalog.services.option_price_resolver import OptionPriceResolver
from apps.catalog.services.pricing_engine import PricingEngine
from apps.catalog.services.selection_validator import SelectionValidator
from core.utils.money import round_money


class PriceCalculator:
    @staticmethod
    def calculate_item_price(
        product: Product,
        selected: list[SelectedOptionEntry] | list,
    ) -> Decimal:
        if not selected:
            return round_money(max(Decimal(product.base_price), Decimal("0")))

        if selected and not isinstance(selected[0], SelectedOptionEntry):
            raise TypeError("Use SelectionValidator.validate antes de calcular preço")

        catalog_base = Decimal(product.base_price)
        by_group: dict[str, list[tuple]] = {}
        link_by_group: dict = {}
        price_overrides = OptionPriceResolver.effective_overrides_for_product(product)

        for entry in selected:
            group_id = str(entry.group.id)
            by_group.setdefault(group_id, []).append((entry.option, entry.quantity))
            link_by_group[group_id] = entry.link

        # tamanho/volume = preço absoluto do produto; resto soma em cima
        effective_base = catalog_base
        addons = Decimal("0")
        for group_id, group_entries in by_group.items():
            link = link_by_group[group_id]
            effective = effective_group_fields(link)
            config = effective["pricing_config"] or {}
            strategy = config.get("strategy", "additive")
            kind = getattr(link.option_group, "kind", "") or ""
            amount = PricingEngine.apply_group(
                base_price=catalog_base,
                entries=group_entries,
                pricing_config=config,
                price_overrides=price_overrides,
            )
            if strategy == "replace_base" or kind in PRODUCT_PRICE_KINDS:
                effective_base = amount
            else:
                addons += amount

        total = round_money(effective_base + addons)
        if total < 0:
            return Decimal("0.00")
        return total

    @staticmethod
    def validate_selections(
        product: Product,
        selections: dict[str, list],
    ) -> list[SelectedOptionEntry]:
        return SelectionValidator.validate(product, selections)
