from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler

from core.exceptions.domain import DomainException

# nomes amigáveis pra montar a mensagem pro usuário
FIELD_LABELS = {
    "address": "Endereço",
    "latitude": "Localização",
    "longitude": "Localização",
    "customer_name": "Nome",
    "customer_phone": "Celular",
    "customer_email": "E-mail",
    "delivery_type": "Tipo de entrega",
    "payment_method": "Pagamento",
    "change_for": "Troco",
    "items": "Itens",
    "street": "Rua",
    "number": "Número",
    "neighborhood": "Bairro",
    "city": "Cidade",
    "state": "Estado",
    "zip_code": "CEP",
    "phone": "Celular",
    "password": "Senha",
    "email": "E-mail",
    "first_name": "Nome",
    "non_field_errors": "",
    "detail": "",
}


def _label_for(path: str) -> str:
    parts = [p for p in path.split(".") if p and not p.isdigit()]
    if not parts:
        return ""
    key = parts[-1]
    return FIELD_LABELS.get(key, key.replace("_", " ").capitalize())


def flatten_validation_detail(detail, prefix: str = "") -> list[str]:
    """transforma ErrorDetail aninhado em frases curtas"""
    messages: list[str] = []

    if isinstance(detail, dict):
        for key, value in detail.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            messages.extend(flatten_validation_detail(value, path))
        return messages

    if isinstance(detail, list):
        for index, item in enumerate(detail):
            path = prefix if not isinstance(item, (dict, list)) else f"{prefix}.{index}"
            messages.extend(flatten_validation_detail(item, path or prefix))
        return messages

    text = str(detail).strip()
    if not text:
        return messages

    label = _label_for(prefix)
    if label:
        messages.append(f"{label}: {text}")
    else:
        messages.append(text)
    return messages


def custom_exception_handler(exc, context):
    if isinstance(exc, DomainException):
        from rest_framework.response import Response

        return Response(
            {"error": {"code": exc.code, "message": exc.message}},
            status=422,
        )

    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, APIException):
        code = getattr(exc, "default_code", "error")
        details = exc.detail if isinstance(exc.detail, (dict, list)) else None

        if isinstance(exc.detail, dict):
            flat = flatten_validation_detail(exc.detail)
            message = " · ".join(flat) if flat else str(exc.detail.get("detail", exc.detail))
        elif isinstance(exc.detail, list):
            flat = flatten_validation_detail(exc.detail)
            message = " · ".join(flat) if flat else str(exc.detail[0] if exc.detail else exc)
        else:
            message = str(exc.detail)

        response.data = {
            "error": {
                "code": str(code).upper(),
                "message": message,
                "details": details,
            }
        }

    return response
