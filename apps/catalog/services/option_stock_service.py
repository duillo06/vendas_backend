from django.db.models import F

from apps.catalog.models import Option


class OptionStockService:
    @staticmethod
    def decrement_for_order(*, validated_items: list[dict]) -> None:
        # só mexe em opções com stock_quantity definido
        totals: dict[str, int] = {}

        for item in validated_items:
            product_qty = int(item.get("quantity", 1))
            for opt in item.get("options") or []:
                option_id = opt.get("option_id")
                if not option_id:
                    continue
                option_qty = int(opt.get("quantity", 1))
                totals[str(option_id)] = totals.get(str(option_id), 0) + option_qty * product_qty

        for option_id, used in totals.items():
            option = Option.all_objects.select_for_update().filter(id=option_id).first()
            if not option or option.stock_quantity is None:
                continue

            remaining = max(0, option.stock_quantity - used)
            option.stock_quantity = remaining
            if remaining == 0:
                option.is_available = False
            option.save(update_fields=["stock_quantity", "is_available", "updated_at"])
