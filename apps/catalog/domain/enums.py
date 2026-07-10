from django.db import models


class OptionSelectionType(models.TextChoices):
    SINGLE = "single", "Única"
    MULTIPLE = "multiple", "Múltipla"


class OptionSelectionMode(models.TextChoices):
    PICK = "pick", "Escolha"
    QUANTITY = "quantity", "Quantidade"


class OptionDisplayType(models.TextChoices):
    LIST = "list", "Lista"
    RADIO = "radio", "Radio"
    CHECKBOX = "checkbox", "Checkbox"
    CARDS = "cards", "Cards"
    IMAGE_CARDS = "image_cards", "Cards com imagem"
    DROPDOWN = "dropdown", "Dropdown"
    STEPPER = "stepper", "Stepper"
    ICON_CHIPS = "icon_chips", "Chips"
    COLOR_SWATCH = "color_swatch", "Cor"


class OptionGroupVisibility(models.TextChoices):
    ALWAYS = "always", "Sempre"
    HIDDEN = "hidden", "Oculto"
    CONDITIONAL = "conditional", "Condicional"


class OptionPriceType(models.TextChoices):
    FIXED = "fixed", "Fixo"
    PERCENTAGE = "percentage", "Percentual"
