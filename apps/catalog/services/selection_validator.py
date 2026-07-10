from collections import defaultdict

from apps.catalog.domain.enums import OptionSelectionMode, OptionSelectionType
from apps.catalog.domain.exceptions import InvalidOptionSelection
from apps.catalog.domain.selection_types import SelectedOptionEntry
from apps.catalog.models import Option, Product, ProductOptionGroup
from apps.catalog.services.group_config import effective_group_fields


class SelectionValidator:
    @staticmethod
    def validate(
        product: Product,
        selections: dict[str, list[dict]],
    ) -> list[SelectedOptionEntry]:
        links = list(
            ProductOptionGroup.all_objects.filter(product=product)
            .select_related("option_group")
            .prefetch_related("option_group__options")
            .order_by("sort_order")
        )

        validated: list[SelectedOptionEntry] = []

        for link in links:
            group = link.option_group
            if not group.is_active:
                continue

            effective = effective_group_fields(link)
            group_id = str(group.id)
            raw_items = selections.get(group_id, [])
            if not raw_items and str(link.option_group_id) in selections:
                raw_items = selections[str(link.option_group_id)]

            if not SelectionValidator._is_group_visible(effective, selections):
                if raw_items:
                    raise InvalidOptionSelection(f"Seleção inválida em {group.name}")
                continue

            normalized = SelectionValidator._normalize_items(raw_items, effective["selection_mode"])
            count = SelectionValidator._selection_count(normalized, effective["selection_mode"])

            min_sel = effective["min_selections"]
            max_sel = effective["max_selections"]

            if effective["is_required"] and count < min_sel:
                raise InvalidOptionSelection(f"Selecione ao menos {min_sel} em {group.name}")

            if count < min_sel:
                raise InvalidOptionSelection(f"Seleção inválida em {group.name}")

            if max_sel > 0 and count > max_sel:
                raise InvalidOptionSelection(f"Seleção inválida em {group.name}")

            if effective["selection_type"] == OptionSelectionType.SINGLE and len(normalized) > 1:
                raise InvalidOptionSelection(f"Seleção inválida em {group.name}")

            option_ids = [item["option_id"] for item in normalized]
            options = {
                str(option.id): option
                for option in Option.all_objects.filter(
                    option_group=group,
                    id__in=option_ids,
                    is_active=True,
                    is_available=True,
                )
            }

            if len(options) != len(set(option_ids)):
                raise InvalidOptionSelection(f"Opção inválida em {group.name}")

            for item in normalized:
                option = options[item["option_id"]]
                SelectionValidator._validate_stock(option, item["quantity"])
                validated.append(
                    SelectedOptionEntry(
                        option=option,
                        quantity=item["quantity"],
                        group=group,
                        link=link,
                    )
                )

        return validated

    @staticmethod
    def _is_group_visible(effective: dict, selections: dict[str, list]) -> bool:
        visibility = effective.get("visibility", "always")
        if visibility == "hidden":
            return False
        if visibility != "conditional":
            return True

        show_when = (effective.get("ui_config") or {}).get("show_when") or {}
        group_id = str(show_when.get("group_id", ""))
        if not group_id:
            return False

        raw_items = selections.get(group_id, [])
        if not raw_items:
            return False

        option_ids_filter = [str(value) for value in (show_when.get("option_ids") or [])]
        if not option_ids_filter:
            return True

        selected_ids = {str(item.get("option_id") or item.get("optionId", "")) for item in raw_items}
        return bool(selected_ids.intersection(option_ids_filter))

    @staticmethod
    def _validate_stock(option: Option, quantity: int) -> None:
        if option.stock_quantity is None:
            return
        if quantity > option.stock_quantity:
            raise InvalidOptionSelection(f"{option.name} sem estoque suficiente")

    @staticmethod
    def _normalize_items(raw_items: list, selection_mode: str) -> list[dict]:
        merged: dict[str, int] = defaultdict(int)

        for raw in raw_items:
            option_id = str(raw.get("option_id") or raw.get("optionId", ""))
            if not option_id:
                continue
            quantity = int(raw.get("quantity", 1))
            if quantity < 1 or quantity > 99:
                raise InvalidOptionSelection("Quantidade de opção inválida")
            merged[option_id] += quantity

        if selection_mode == OptionSelectionMode.PICK:
            return [{"option_id": oid, "quantity": 1} for oid in merged]
        return [{"option_id": oid, "quantity": qty} for oid, qty in merged.items()]

    @staticmethod
    def _selection_count(items: list[dict], selection_mode: str) -> int:
        if selection_mode == OptionSelectionMode.QUANTITY:
            return sum(item["quantity"] for item in items)
        return len(items)
