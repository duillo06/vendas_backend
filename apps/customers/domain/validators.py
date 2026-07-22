import re

from django.core.exceptions import ValidationError


def normalize_phone(phone: str) -> str:
    """aceita só celular BR: DDD + 9 + 8 dígitos → (11) 98765-4321"""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits[2] == "9":
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    raise ValidationError("Informe um celular válido com DDD")


def split_customer_name(name: str) -> tuple[str, str]:
    parts = (name or "").strip().split(maxsplit=1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]
