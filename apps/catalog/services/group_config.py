from apps.catalog.models import ProductOptionGroup


def merge_json_config(
    base: dict | None,
    override: dict | None,
    *,
    default: dict | None = None,
) -> dict:
    merged = dict(default or {})
    if base:
        merged.update(base)
    if override:
        merged.update(override)
    return merged


def effective_group_fields(link: ProductOptionGroup) -> dict:
    group = link.option_group
    return {
        "min_selections": link.override_min if link.override_min is not None else group.min_selections,
        "max_selections": link.override_max if link.override_max is not None else group.max_selections,
        "is_required": (
            link.override_required if link.override_required is not None else group.is_required
        ),
        "display_type": link.override_display_type or group.display_type,
        "selection_mode": group.selection_mode,
        "selection_type": group.selection_type,
        "pricing_config": merge_json_config(
            group.pricing_config,
            link.override_pricing_config,
            default={"strategy": "additive"},
        ),
        "ui_config": merge_json_config(group.ui_config, link.override_ui_config),
        "icon": group.icon or None,
        "image_url": group.image_url or None,
        "visibility": group.visibility,
        "default_option_ids": group.default_option_ids or [],
        "name": group.name,
        "description": group.description,
    }
