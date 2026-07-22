import pytest
from django.core.exceptions import ValidationError

from apps.customers.domain.validators import normalize_phone


def test_normalize_phone_mobile_ok():
    assert normalize_phone("11987654321") == "(11) 98765-4321"
    assert normalize_phone("(11) 98765-4321") == "(11) 98765-4321"


def test_normalize_phone_rejects_landline():
    with pytest.raises(ValidationError):
        normalize_phone("1134567890")


def test_normalize_phone_rejects_short():
    with pytest.raises(ValidationError):
        normalize_phone("1198765")
