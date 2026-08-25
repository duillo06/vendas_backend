from rest_framework.throttling import SimpleRateThrottle


class AuthLoginThrottle(SimpleRateThrottle):
    """Limita tentativas de login (admin e cliente) por IP."""

    scope = "auth_login"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class CheckoutThrottle(SimpleRateThrottle):
    scope = "checkout"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class WhatsAppTestThrottle(SimpleRateThrottle):
    scope = "whatsapp_test"

    def get_cache_key(self, request, view):
        # por tenant + IP quando autenticado
        tenant = getattr(request, "tenant", None)
        tenant_part = str(getattr(tenant, "id", "")) or "anon"
        return self.cache_format % {
            "scope": self.scope,
            "ident": f"{tenant_part}:{self.get_ident(request)}",
        }
