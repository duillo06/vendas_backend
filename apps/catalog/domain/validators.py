from django.core.exceptions import ValidationError

from apps.catalog.domain.enums import OptionSelectionType

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
) -> None:
    if min_selections > max_selections:
        raise ValidationError("min_selections não pode ser maior que max_selections")

    if is_required and min_selections < 1:
        raise ValidationError("Grupo obrigatório precisa de min_selections >= 1")

    if selection_type == OptionSelectionType.SINGLE and max_selections != 1:
        raise ValidationError("Seleção única exige max_selections = 1")
