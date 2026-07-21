from decimal import Decimal

from apps.catalog.domain.selection_types import SelectedOptionEntry
from apps.catalog.models import Product, ProductOptionPrice
from apps.catalog.services.group_config import effective_group_fields
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

        base_price = Decimal(product.base_price)
        by_group: dict[str, list[tuple]] = {}
        link_by_group: dict = {}
        # dual-read: preço no produto se existir (all_objects — produto já resolve tenant)
        price_overrides = PricingEngine.overrides_from_rows(
            ProductOptionPrice.all_objects.filter(product=product)
        )

        for entry in selected:
            group_id = str(entry.group.id)
            by_group.setdefault(group_id, []).append((entry.option, entry.quantity))
            link_by_group[group_id] = entry.link

        options_total = Decimal("0")
        for group_id, group_entries in by_group.items():
            link = link_by_group[group_id]
            effective = effective_group_fields(link)
            options_total += PricingEngine.apply_group(
                base_price=base_price,
                entries=group_entries,
                pricing_config=effective["pricing_config"],
                price_overrides=price_overrides,
            )

        total = round_money(base_price + options_total)
        if total < 0:
            return Decimal("0.00")
        return total

    @staticmethod
    def validate_selections(
        product: Product,
        selections: dict[str, list],
    ) -> list[SelectedOptionEntry]:
        return SelectionValidator.validate(product, selections)
