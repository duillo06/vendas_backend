from django.core.exceptions import ValidationError

from apps.catalog.domain.enums import OptionSelectionMode, OptionSelectionType

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024


def validate_product_image(file) -> None:
    content_type = getattr(file, "content_type", None)
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError("Formato de imagem não suportado")

    if file.size > MAX_IMAGE_SIZE:
        raise ValidationError("Imagem deve ter no máximo 5MB")


def validate_option_group_rules(
    *,
    selection_type: str,
    min_selections: int,
    max_selections: int,
    is_required: bool,
    selection_mode: str = OptionSelectionMode.PICK,
) -> None:
    if max_selections == 0:
        if selection_type != OptionSelectionType.MULTIPLE:
            raise ValidationError("max_selections=0 só é permitido em seleção múltipla")
    elif min_selections > max_selections:
        raise ValidationError("min_selections não pode ser maior que max_selections")

    if is_required and min_selections < 1:
        raise ValidationError("Grupo obrigatório precisa de min_selections >= 1")

    if selection_type == OptionSelectionType.SINGLE:
        if max_selections != 1:
            raise ValidationError("Seleção única exige max_selections = 1")
        if selection_mode != OptionSelectionMode.PICK:
            raise ValidationError("Seleção única não suporta selection_mode quantity")

    if selection_mode == OptionSelectionMode.QUANTITY and selection_type != OptionSelectionType.MULTIPLE:
        raise ValidationError("Modo quantity exige selection_type multiple")


def validate_pricing_config(pricing_config: dict | None) -> None:
    config = pricing_config or {}
    strategy = config.get("strategy", "additive")

    if strategy == "tiered":
        tiers = config.get("tiers") or []
        if not tiers:
            raise ValidationError("Estratégia tiered exige ao menos uma faixa")
        for tier in tiers:
            if "unit_price" not in tier or "from" not in tier:
                raise ValidationError("Cada faixa precisa de from e unit_price")


def validate_ui_config(*, visibility: str, ui_config: dict | None) -> None:
    if visibility != "conditional":
        return

    show_when = (ui_config or {}).get("show_when") or {}
    if not show_when.get("group_id"):
        raise ValidationError("Visibilidade condicional exige ui_config.show_when.group_id")


def validate_default_option_ids(
    *,
    option_group,
    default_option_ids: list,
    max_selections: int,
    selection_mode: str,
) -> None:
    if not default_option_ids:
        return

    active_ids = {
        str(option.id)
        for option in option_group.options.filter(is_active=True, is_available=True)
    }

    for option_id in default_option_ids:
        if str(option_id) not in active_ids:
            raise ValidationError("default_option_ids contém opção inválida ou inativa")

    default_count = len(default_option_ids)
    if selection_mode == OptionSelectionMode.QUANTITY:
        default_count = len(default_option_ids)

    if max_selections > 0 and default_count > max_selections:
        raise ValidationError("Defaults excedem max_selections do grupo")
