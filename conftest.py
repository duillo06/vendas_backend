import pytest


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    # evita 429 entre testes (mesmo IP no CI)
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()
