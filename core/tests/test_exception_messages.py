from decimal import Decimal

from rest_framework.exceptions import ErrorDetail

from core.exceptions.handlers import flatten_validation_detail
from core.serializers.fields import GeoCoordinateField


def test_flatten_nested_address_errors():
    detail = {
        "address": {
            "latitude": [ErrorDetail("muitos dígitos", code="max_digits")],
            "longitude": [ErrorDetail("muitos dígitos", code="max_digits")],
        }
    }
    messages = flatten_validation_detail(detail)
    assert any("Localização" in msg for msg in messages)
    assert "muitos dígitos" in " ".join(messages)
    assert "ErrorDetail" not in " ".join(messages)


def test_geo_coordinate_rounds_float_noise():
    field = GeoCoordinateField()
    # float típico do GPS com casas extras
    value = field.to_internal_value(-23.550519928747912)
    assert value == Decimal("-23.5505199")
