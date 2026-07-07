from decimal import Decimal

from apps.catalog.domain.exceptions import InvalidOptionSelection
from apps.catalog.models import Option, Product
from apps.catalog.services.price_calculator import PriceCalculator
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
                product = Product.objects.get(
                    id=product_id,
                    is_active=True,
                    deleted_at__isnull=True,
                )
            except Product.DoesNotExist:
                raise ProductUnavailableError(f"Produto {product_id} indisponível") from None

            if not product.is_available:
                raise ProductUnavailableError(f"{product.name} indisponível")

            option_ids = [str(opt["option_id"]) for opt in raw.get("options", []) if opt.get("option_id")]
            selections = CartValidationService._group_options_by_product(product, option_ids)

            try:
                selected_options = PriceCalculator.validate_selections(product, selections)
            except InvalidOptionSelection as exc:
                raise InvalidOptionsError(str(exc)) from exc

            unit_price = PriceCalculator.calculate_item_price(product, selected_options)
            total_price = round_money(unit_price * Decimal(quantity))

            option_snapshots = [
                {
                    "option_id": str(option.id),
                    "group_name": option.option_group.name,
                    "name": option.name,
                    "price_modifier": option.price_modifier,
                }
                for option in selected_options
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
                }
            )

        return validated

    @staticmethod
    def _group_options_by_product(product: Product, option_ids: list[str]) -> dict[str, list[str]]:
        if not option_ids:
            return {}

        selections: dict[str, list[str]] = {}
        for option_id in option_ids:
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
            selections.setdefault(group_id, []).append(str(option.id))

        return selections
