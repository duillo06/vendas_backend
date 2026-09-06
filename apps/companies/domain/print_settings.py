# defaults + sanitize do JSON de impressão da comanda

DEFAULT_PRINT_SETTINGS = {
    "paper_width": "80",  # 58 | 80
    "font_size": "normal",  # normal | large
    "show_prices": True,
    "show_payment": True,
    "show_store_phone": True,
    "show_customer_phone": True,
    "show_order_notes": True,
    "show_internal_notes": True,
    "show_prep_time": True,
    "copies": 1,  # 1 | 2
    "footer_text": "Obrigado!",
}


def normalize_print_settings(raw) -> dict:
    base = dict(DEFAULT_PRINT_SETTINGS)
    if not isinstance(raw, dict):
        return base

    paper = str(raw.get("paper_width", base["paper_width"]))
    base["paper_width"] = paper if paper in {"58", "80"} else "80"

    font = str(raw.get("font_size", base["font_size"]))
    base["font_size"] = font if font in {"normal", "large"} else "normal"

    for key in (
        "show_prices",
        "show_payment",
        "show_store_phone",
        "show_customer_phone",
        "show_order_notes",
        "show_internal_notes",
        "show_prep_time",
    ):
        if key in raw:
            base[key] = bool(raw[key])

    try:
        copies = int(raw.get("copies", base["copies"]))
    except (TypeError, ValueError):
        copies = 1
    base["copies"] = copies if copies in {1, 2} else 1

    footer = raw.get("footer_text", base["footer_text"])
    if footer is None:
        base["footer_text"] = ""
    else:
        base["footer_text"] = str(footer)[:120]

    return base
