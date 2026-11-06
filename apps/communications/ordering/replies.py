from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


PAGE = 9


def clip(text: str, limit: int) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= limit:
        return clean
    if limit <= 1:
        return clean[:limit]
    return clean[: limit - 1].rstrip() + "…"


def brl(value) -> str:
    quantized = Decimal(str(value)).quantize(Decimal("0.01"))
    return f"R$ {quantized:.2f}".replace(".", ",")


@dataclass
class Reply:
    body: str
    buttons: list[tuple[str, str]] = field(default_factory=list)
    rows: list[tuple[str, str, str]] = field(default_factory=list)
    button_label: str = "Ver opções"

    def with_hint(self, hint: str) -> Reply:
        if not hint:
            return self
        self.body = f"{hint}\n\n{self.body}"
        return self


def as_buttons(body: str, options: list[tuple[str, str]]) -> Reply:
    buttons = [(item_id, clip(label, 20)) for item_id, label in options[:3]]
    return Reply(body=body, buttons=buttons)


def as_list(
    body: str,
    options: list[tuple[str, str, str]],
    *,
    button_label: str = "Ver opções",
) -> Reply:
    rows = [
        (item_id, clip(title, 24), clip(desc, 72))
        for item_id, title, desc in options[:10]
    ]
    return Reply(body=body, rows=rows, button_label=clip(button_label, 20))


def paged(items: list, page: int, row_for, more_id: str) -> tuple[list, int]:
    start = max(page, 0) * PAGE
    chunk = items[start : start + PAGE]
    rows = [row_for(item) for item in chunk]
    if start + PAGE < len(items):
        rows.append((more_id, "Ver mais", ""))
    return rows, start
