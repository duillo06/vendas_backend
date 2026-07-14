import pytest
from django.test import RequestFactory, override_settings

from apps.companies.models import BusinessHours
from core.tenancy.context import TenantContext
from core.tenancy.middleware import TenantMiddleware


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_middleware_resolves_foodservice_subdomain(demo_company):
    factory = RequestFactory()
    request = factory.get(
        "/api/v1/public/catalog/",
        HTTP_HOST="demo.foodservice.app",
    )

    middleware = TenantMiddleware(lambda req: req)
    middleware(request)

    assert request.tenant == demo_company


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_middleware_resolves_localhost_subdomain(demo_company):
    factory = RequestFactory()
    request = factory.get(
        "/api/v1/public/catalog/",
        HTTP_HOST="demo.localhost:8001",
    )

    middleware = TenantMiddleware(lambda req: req)
    middleware(request)

    assert request.tenant == demo_company


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_middleware_resolves_tenant_subdomain_header(demo_company):
    factory = RequestFactory()
    request = factory.get(
        "/api/v1/public/catalog/",
        HTTP_HOST="127.0.0.1:8001",
        HTTP_X_TENANT_SUBDOMAIN="demo",
    )

    middleware = TenantMiddleware(lambda req: req)
    middleware(request)

    assert request.tenant == demo_company


@pytest.mark.django_db
def test_middleware_skips_health_check():
    factory = RequestFactory()
    request = factory.get("/api/v1/health/", HTTP_HOST="demo.foodservice.app")

    middleware = TenantMiddleware(lambda req: req)
    middleware(request)

    assert not hasattr(request, "tenant")


@pytest.mark.django_db
def test_tenant_manager_filters_business_hours(demo_company, other_company):
    TenantContext.set(demo_company)

    visible = list(BusinessHours.objects.all())
    assert len(visible) == 7
    assert all(row.tenant_id == demo_company.id for row in visible)

    TenantContext.clear()


@pytest.mark.django_db
def test_tenant_manager_returns_empty_without_context(demo_company):
    assert BusinessHours.objects.count() == 0
