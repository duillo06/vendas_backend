from django.conf import settings

from core.tenancy.context import TenantContext

RESERVED_SUBDOMAINS = frozenset({"www", "api", "admin", "app"})


class TenantMiddleware:
    """Resolve tenant por subdomínio (storefront) ou header (backoffice). Sprint 1 completa resolução."""

    EXEMPT_PREFIXES = (
        "/api/v1/health/",
        "/api/v1/auth/login/",
        "/api/v1/auth/refresh/",
        "/api/v1/auth/logout/",
    )

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

        # Vite proxy / LAN: Host vira 127.0.0.1 — tenant vem do header
        tenant_subdomain = request.headers.get("X-Tenant-Subdomain")
        if tenant_subdomain:
            subdomain = tenant_subdomain.strip().lower()
            if subdomain and subdomain not in RESERVED_SUBDOMAINS:
                return self._get_active_company(subdomain=subdomain)

        host = request.get_host().split(":")[0].lower()
        subdomain = self._subdomain_from_host(host)
        if subdomain:
            return self._get_active_company(subdomain=subdomain)

        return None

    def _subdomain_from_host(self, host: str) -> str | None:
        # prod: demo.pediu.cloud (STOREFRONT_BASE_DOMAIN)
        base = getattr(settings, "STOREFRONT_BASE_DOMAIN", "") or ""
        base = base.lstrip(".").lower()
        if base and host.endswith(f".{base}"):
            subdomain = host[: -(len(base) + 1)]
            if subdomain and subdomain not in RESERVED_SUBDOMAINS and "." not in subdomain:
                return subdomain

        # legado / docs
        if host.endswith(".foodservice.app"):
            subdomain = host[: -len(".foodservice.app")]
            if subdomain and subdomain not in RESERVED_SUBDOMAINS and "." not in subdomain:
                return subdomain

        if host.endswith(".localhost"):
            subdomain = host[: -len(".localhost")]
            if subdomain and subdomain not in RESERVED_SUBDOMAINS and "." not in subdomain:
                return subdomain

        return None

    def _get_active_company(self, **filters):
        from django.http import Http404

        from apps.companies.models import Company

        try:
            return Company.objects.get(status="active", **filters)
        except Company.DoesNotExist:
            raise Http404("Estabelecimento não encontrado") from None
