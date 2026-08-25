"""Headers básicos de segurança nas respostas da API."""


class ApiSecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # API JSON — CSP restritiva; HTML (ex. 404) também se beneficia
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )
        # storefront em outra origem precisa ler a API (CORS já cuida do resto)
        response.headers.setdefault("Cross-Origin-Resource-Policy", "cross-origin")
        # API autenticada não deve ficar em cache compartilhado
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response
