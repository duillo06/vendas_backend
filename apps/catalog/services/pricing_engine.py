from decimal import Decimal

from apps.catalog.domain.enums import OptionPriceType
from apps.catalog.models import Option
from core.utils.money import round_money


class PricingEngine:
    @staticmethod
    def modifier_amount(*, base_price: Decimal, option: Option, quantity: int = 1) -> Decimal:
        unit = PricingEngine._unit_modifier(base_price, option)
        return round_money(unit * Decimal(quantity))

    @staticmethod
    def apply_group(
        *,
        base_price: Decimal,
        entries: list[tuple[Option, int]],
        pricing_config: dict | None,
    ) -> Decimal:
        config = pricing_config or {}
        strategy = config.get("strategy", "additive")

        if strategy in ("additive", "quantity_multiplier"):
            return PricingEngine._additive(base_price, entries)

        if strategy == "charge_extras_only":
            included = int(config.get("included_count", 0))
            return PricingEngine._charge_from_nth(base_price, entries, included)

        if strategy == "first_n_free":
            free_count = int(config.get("free_count", 0))
            return PricingEngine._charge_from_nth(base_price, entries, free_count)

        if strategy == "tiered":
            return PricingEngine._tiered(entries, config.get("tiers") or [])

        return PricingEngine._additive(base_price, entries)

    @staticmethod
    def _additive(base_price: Decimal, entries: list[tuple[Option, int]]) -> Decimal:
        total = Decimal("0")
        for option, quantity in entries:
            total += PricingEngine.modifier_amount(
                base_price=base_price,
                option=option,
                quantity=quantity,
            )
        return round_money(total)

    @staticmethod
    def _charge_from_nth(
        base_price: Decimal,
        entries: list[tuple[Option, int]],
        free_units: int,
    ) -> Decimal:
        units: list[Option] = []
        for option, quantity in entries:
            units.extend([option] * quantity)

        total = Decimal("0")
        for index, option in enumerate(units):
            if index >= free_units:
                total += PricingEngine._unit_modifier(base_price, option)
        return round_money(total)

    @staticmethod
    def _tiered(entries: list[tuple[Option, int]], tiers: list) -> Decimal:
        total_count = sum(quantity for _, quantity in entries)
        if total_count <= 0:
            return Decimal("0.00")

        tier = PricingEngine._find_tier(total_count, tiers)
        if not tier:
            return Decimal("0.00")

        return round_money(Decimal(str(tier["unit_price"])) * Decimal(total_count))

    @staticmethod
    def _find_tier(count: int, tiers: list) -> dict | None:
        if not tiers:
            return None

        sorted_tiers = sorted(tiers, key=lambda item: int(item.get("from", 1)))
        for tier in sorted_tiers:
            start = int(tier.get("from", 1))
            end = tier.get("to")
            if count >= start and (end is None or count <= int(end)):
                return tier

        return sorted_tiers[-1]

    @staticmethod
    def _unit_modifier(base_price: Decimal, option: Option) -> Decimal:
        if option.price_type == OptionPriceType.PERCENTAGE:
            return round_money(base_price * (option.price_modifier / Decimal("100")))
        return round_money(Decimal(option.price_modifier))
