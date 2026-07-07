from core.tenancy.context import TenantContext


class TenantMiddleware:
    """Resolve tenant por subdomínio (storefront) ou header (backoffice). Sprint 1 completa resolução."""

    EXEMPT_PREFIXES = ("/api/v1/auth/", "/api/v1/health/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = self._resolve_tenant(request)
        if tenant is not None:
            TenantContext.set(tenant)
            request.tenant = tenant

        try:
            return self.get_response(request)
        finally:
            TenantContext.clear()

    def _resolve_tenant(self, request):
        if request.path.startswith(self.EXEMPT_PREFIXES):
            return None

        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            return self._get_active_company(id=tenant_id)

        host = request.get_host().split(":")[0]
        if host.endswith(".foodservice.app"):
            subdomain = host.replace(".foodservice.app", "")
            if subdomain and subdomain not in ("www", "api", "admin", "app"):
                return self._get_active_company(subdomain=subdomain)

        if host.endswith(".localhost"):
            subdomain = host.replace(".localhost", "")
            if subdomain and subdomain not in ("www", "api", "admin", "app"):
                return self._get_active_company(subdomain=subdomain)

        return None

    def _get_active_company(self, **filters):
        try:
            from apps.companies.models import Company
        except ImportError:
            return None

        try:
            return Company.objects.get(status="active", **filters)
        except Company.DoesNotExist:
            from django.http import Http404

            raise Http404("Estabelecimento não encontrado") from None
