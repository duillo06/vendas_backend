from django.core.exceptions import ImproperlyConfigured

INSECURE_SECRET_KEYS = frozenset(
    {
        "",
        "dev-insecure-change-me",
        "changeme",
        "troque-por-uma-chave-segura-aleatoria",
    }
)


def require_production_boot(*, secret_key: str, allowed_hosts: list[str]) -> None:
    """Fail-fast: staging/prod não sobe com secret fraco ou hosts vazios."""
    if not secret_key or secret_key in INSECURE_SECRET_KEYS or len(secret_key) < 32:
        raise ImproperlyConfigured("SECRET_KEY forte (≥32 chars) é obrigatória em produção/staging")
    if not allowed_hosts:
        raise ImproperlyConfigured("ALLOWED_HOSTS não pode ficar vazio em produção/staging")
