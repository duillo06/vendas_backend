from decimal import Decimal

from apps.catalog.domain.enums import OptionPriceType
from apps.catalog.domain.exceptions import InvalidOptionSelection
from apps.catalog.models import Option, Product, ProductOptionGroup
from core.utils.money import round_money


class PriceCalculator:
    @staticmethod
    def calculate_item_price(
        product: Product,
        selected_options: list[Option],
    ) -> Decimal:
        total = Decimal(product.base_price)

        for option in selected_options:
            total += PriceCalculator._modifier_amount(product.base_price, option)

        total = round_money(total)
        if total < 0:
            return Decimal("0.00")
        return total

    @staticmethod
    def validate_selections(
        product: Product,
        selections: dict[str, list[str]],
    ) -> list[Option]:
        links = (
            ProductOptionGroup.all_objects.filter(product=product)
            .select_related("option_group")
            .prefetch_related("option_group__options")
        )

        selected_options: list[Option] = []

        for link in links:
            group = link.option_group
            if not group.is_active:
                continue

            min_sel = link.override_min if link.override_min is not None else group.min_selections
            max_sel = link.override_max if link.override_max is not None else group.max_selections

            chosen_ids = selections.get(str(group.id), [])
            if not chosen_ids and str(link.option_group_id) in selections:
                chosen_ids = selections[str(link.option_group_id)]

            if group.is_required and len(chosen_ids) < min_sel:
                raise InvalidOptionSelection(f"Selecione ao menos {min_sel} em {group.name}")

            if len(chosen_ids) < min_sel or len(chosen_ids) > max_sel:
                raise InvalidOptionSelection(f"Seleção inválida em {group.name}")

            options = list(
                Option.all_objects.filter(
                    option_group=group,
                    id__in=chosen_ids,
                    is_active=True,
                    is_available=True,
                )
            )

            if len(options) != len(chosen_ids):
                raise InvalidOptionSelection(f"Opção inválida em {group.name}")

            selected_options.extend(options)

        return selected_options

    @staticmethod
    def _modifier_amount(base_price: Decimal, option: Option) -> Decimal:
        if option.price_type == OptionPriceType.PERCENTAGE:
            return round_money(base_price * (option.price_modifier / Decimal("100")))
        return round_money(Decimal(option.price_modifier))
