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


class CompositionSourceType(models.TextChoices):
    # de onde vêm os produtos que compõem (ex: sabores de pizza)
    CATEGORY = "category", "Mesma categoria"
    TAG = "tag", "Por tag"
    CUSTOM = "custom", "Lista personalizada"


class CompositionPricingRule(models.TextChoices):
    # como cobrar quando o produto é composto por outros
    HIGHEST = "highest", "Maior preço"
    AVERAGE = "average", "Média dos preços"
    SUM = "sum", "Soma dos preços"
    MAIN = "main", "Preço do produto principal"


# kinds da receita / base reutilizável — internos; UI fala em perguntas
class CatalogKind(models.TextChoices):
    SIZE = "size", "Tamanhos"
    CRUST = "crust", "Bordas"
    EXTRAS = "extras", "Adicionais"
    BUILDABLE = "buildable", "Ingredientes"
    SAUCES = "sauces", "Molhos"
    DOUGH = "dough", "Massas"
    VOLUME = "volume", "Volumes"
    HALF = "half", "Meio a meio"
    OTHER = "other", "Outro"
