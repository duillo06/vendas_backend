import re

from django.core.exceptions import ValidationError

# subdomínios que o sistema já usa
RESERVED_SUBDOMAINS = frozenset(
    {
        "www",
        "api",
        "admin",
        "app",
        "mail",
        "ftp",
    }
)

SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?$")


def validate_subdomain(value: str) -> None:
    if not value or len(value) < 3 or len(value) > 63:
        raise ValidationError("Subdomínio deve ter entre 3 e 63 caracteres.")

    if value in RESERVED_SUBDOMAINS:
        raise ValidationError("Este subdomínio está reservado.")

    if not SUBDOMAIN_PATTERN.match(value):
        raise ValidationError("Use só letras minúsculas, números e hífen.")
