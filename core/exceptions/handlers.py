from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, APIException):
        code = getattr(exc, "default_code", "error")
        if isinstance(exc.detail, dict):
            message = exc.detail.get("detail", str(exc.detail))
        elif isinstance(exc.detail, list):
            message = str(exc.detail[0]) if exc.detail else str(exc)
        else:
            message = str(exc.detail)

        response.data = {
            "error": {
                "code": str(code).upper(),
                "message": message,
                "details": exc.detail if isinstance(exc.detail, (dict, list)) else None,
            }
        }

    return response
