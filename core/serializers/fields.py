from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from rest_framework import serializers


class GeoCoordinateField(serializers.DecimalField):
    """lat/lng com 7 casas — evita estouro de max_digits por float do GPS"""

    def __init__(self, **kwargs):
        kwargs.setdefault("max_digits", 10)
        kwargs.setdefault("decimal_places", 7)
        kwargs.setdefault("required", False)
        kwargs.setdefault("allow_null", True)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if data is None or data == "":
            return None
        try:
            value = Decimal(str(data)).quantize(
                Decimal("0.0000001"),
                rounding=ROUND_HALF_UP,
            )
        except (InvalidOperation, TypeError, ValueError):
            self.fail("invalid")
        return super().to_internal_value(format(value, "f"))
