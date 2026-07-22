import re

from apps.communications.domain.catalog import UI_TOKEN_TO_PAYLOAD
from apps.communications.domain.exceptions import TemplateValidationError

TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def extract_tokens(body: str) -> list[str]:
    return TOKEN_RE.findall(body or "")


def validate_body(body: str, allowed_ui_tokens: list[str]) -> None:
    text = (body or "").strip()
    if not text:
        raise TemplateValidationError("A mensagem não pode ficar vazia.")
    if len(text) > 4096:
        raise TemplateValidationError("Mensagem muito longa. Encurte um pouco.")
    allowed = set(allowed_ui_tokens)
    unknown = [t for t in extract_tokens(text) if t not in allowed]
    if unknown:
        raise TemplateValidationError(
            f"Remova ou corrija: {', '.join('{{' + u + '}}' for u in unknown)}"
        )


def render(body: str, payload: dict) -> str:
    """{{cliente}} → valor do payload via mapa de chips"""

    def repl(match: re.Match) -> str:
        token = match.group(1)
        key = UI_TOKEN_TO_PAYLOAD.get(token, token)
        value = payload.get(key)
        if value is None or value == "":
            return "—"
        return str(value)

    return TOKEN_RE.sub(repl, body or "")
