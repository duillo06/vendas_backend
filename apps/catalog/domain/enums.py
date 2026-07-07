from django.db import models


class OptionSelectionType(models.TextChoices):
    SINGLE = "single", "Única"
    MULTIPLE = "multiple", "Múltipla"


class OptionPriceType(models.TextChoices):
    FIXED = "fixed", "Fixo"
    PERCENTAGE = "percentage", "Percentual"
