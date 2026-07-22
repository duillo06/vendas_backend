from decimal import Decimal

from apps.catalog.domain.exceptions import InvalidOptionSelection
from apps.catalog.models import Option, Product
from apps.catalog.services.composition_service import CompositionService
from apps.catalog.services.option_price_resolver import OptionPriceResolver
from apps.catalog.services.price_calculator import PriceCalculator
from apps.catalog.services.pricing_engine import PricingEngine
from apps.companies.models import Company
from apps.companies.services.store_hours_service import StoreHoursService
from apps.orders.domain.exceptions import (
    EmptyCartError,
    InvalidOptionsError,
    ProductUnavailableError,
    StoreClosedError,
)
from core.utils.money import round_money


class CartValidationService:
    @staticmethod
    def validate(*, tenant: Company, items: list[dict]) -> list[dict]:
        if not items:
            raise EmptyCartError()

        if not StoreHoursService.is_store_open(tenant):
            raise StoreClosedError()

        validated: list[dict] = []

        for raw in items:
            product_id = raw.get("product_id")
            quantity = int(raw.get("quantity", 1))
            if quantity < 1 or quantity > 99:
                raise InvalidOptionsError("Quantidade inválida")

            try:
                product = Product.objects.select_related("composition").get(
                    id=product_id,
                    is_active=True,
                    deleted_at__isnull=True,
                )
            except Product.DoesNotExist:
                raise ProductUnavailableError(f"Produto {product_id} indisponível") from None

            if not product.is_available:
                raise ProductUnavailableError(f"{product.name} indisponível")

            raw_components = raw.get("components") or []
            try:
                chosen_parts = CompositionService.validate_selection(product, raw_components)
            except ValueError as exc:
                raise InvalidOptionsError(str(exc)) from exc

            raw_options = raw.get("options") or []
            selections = CartValidationService._group_options_by_product(product, raw_options)

            try:
                selected_entries = PriceCalculator.validate_selections(product, selections)
            except InvalidOptionSelection as exc:
                raise InvalidOptionsError(str(exc)) from exc

            price_with_options = PriceCalculator.calculate_item_price(product, selected_entries)
            # composição troca a base; opções somam em cima (igual ao cardápio)
            if chosen_parts:
                composed = CompositionService.composed_base_price(
                    product,
                    [product, *chosen_parts],
                )
                options_delta = price_with_options - Decimal(product.base_price)
                unit_price = round_money(composed + options_delta)
            else:
                unit_price = price_with_options
            total_price = round_money(unit_price * Decimal(quantity))

            price_overrides = OptionPriceResolver.effective_overrides_for_product(product)
            option_snapshots = [
                {
                    "option_id": str(entry.option.id),
                    "group_name": entry.group.name,
                    "name": entry.option.name,
                    "price_modifier": PricingEngine._unit_modifier(
                        Decimal(product.base_price),
                        entry.option,
                        price_overrides,
                    ),
                    "quantity": entry.quantity,
                }
                for entry in selected_entries
            ]
            component_snapshots = [
                {
                    "product_id": str(part.id),
                    "product_name": part.name,
                    "base_price": Decimal(part.base_price),
                    "sort_order": index,
                }
                for index, part in enumerate(chosen_parts)
            ]

            validated.append(
                {
                    "product_id": str(product.id),
                    "product_name": product.name,
                    "unit_price": unit_price,
                    "quantity": quantity,
                    "total_price": total_price,
                    "notes": (raw.get("notes") or "")[:255],
                    "options": option_snapshots,
                    "components": component_snapshots,
                }
            )

        return validated

    @staticmethod
    def _group_options_by_product(product: Product, raw_options: list) -> dict[str, list[dict]]:
        if not raw_options:
            return {}

        selections: dict[str, list[dict]] = {}

        for raw in raw_options:
            option_id = str(raw.get("option_id", ""))
            if not option_id:
                continue

            quantity = int(raw.get("quantity", 1))
            if quantity < 1 or quantity > 99:
                raise InvalidOptionsError(f"Opção inválida para {product.name}")

            try:
                option = Option.all_objects.select_related("option_group").get(
                    id=option_id,
                    option_group__product_option_groups__product=product,
                    is_active=True,
                    is_available=True,
                )
            except Option.DoesNotExist:
                raise InvalidOptionsError(f"Opção inválida para {product.name}") from None

            group_id = str(option.option_group_id)
            selections.setdefault(group_id, []).append(
                {"option_id": str(option.id), "quantity": quantity},
            )

        return selections
