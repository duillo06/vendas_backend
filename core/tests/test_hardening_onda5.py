import pytest
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from apps.catalog.domain.validators import validate_product_image
from config.settings.production_guards import require_production_boot
from core.exceptions.handlers import custom_exception_handler
from core.throttling import AuthLoginThrottle


def test_production_boot_rejects_empty_hosts():
    with pytest.raises(ImproperlyConfigured, match="ALLOWED_HOSTS"):
        require_production_boot(secret_key="a" * 40, allowed_hosts=[])


def test_production_boot_rejects_weak_secret():
    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        require_production_boot(secret_key="changeme", allowed_hosts=["api.example.com"])


def test_production_boot_rejects_short_secret():
    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        require_production_boot(secret_key="short-but-not-placeholder", allowed_hosts=["api.example.com"])


def test_production_boot_ok():
    require_production_boot(secret_key="a" * 40, allowed_hosts=["api.foodservice.app"])


def test_validate_product_image_rejects_wrong_type():
    bad = SimpleUploadedFile("x.exe", b"MZ", content_type="application/octet-stream")
    with pytest.raises(ValidationError, match="Formato"):
        validate_product_image(bad)


def test_validate_product_image_rejects_oversize():
    big = SimpleUploadedFile(
        "big.jpg",
        b"x" * (5 * 1024 * 1024 + 1),
        content_type="image/jpeg",
    )
    with pytest.raises(ValidationError, match="5MB"):
        validate_product_image(big)


def test_validate_product_image_accepts_jpeg():
    ok = SimpleUploadedFile("ok.jpg", b"\xff\xd8\xff", content_type="image/jpeg")
    validate_product_image(ok)


@override_settings(DEBUG=False)
def test_unhandled_exception_hides_detail_when_debug_false():
    response = custom_exception_handler(RuntimeError("segredo-do-stack"), {})
    assert response is not None
    assert response.status_code == 500
    body = str(response.data)
    assert "segredo-do-stack" not in body
    assert response.data["error"]["code"] == "SERVER_ERROR"


@override_settings(DEBUG=True)
def test_unhandled_exception_passthrough_when_debug_true():
    assert custom_exception_handler(RuntimeError("boom"), {}) is None


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
        "DEFAULT_THROTTLE_RATES": {"auth_login": "2/min"},
        "EXCEPTION_HANDLER": "core.exceptions.handlers.custom_exception_handler",
    }
)
def test_auth_login_throttle_trips_after_limit():
    from rest_framework.settings import api_settings

    # força recarregar rates do DRF após override
    AuthLoginThrottle.THROTTLE_RATES = api_settings.DEFAULT_THROTTLE_RATES

    factory = APIRequestFactory()
    throttle = AuthLoginThrottle()
    view = type("V", (), {})()

    for _ in range(2):
        request = factory.post("/api/v1/auth/login/")
        assert throttle.allow_request(request, view) is True

    request = factory.post("/api/v1/auth/login/")
    assert throttle.allow_request(request, view) is False
