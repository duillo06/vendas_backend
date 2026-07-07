from django.db import models


class CompanyStatus(models.TextChoices):
    ACTIVE = "active", "Ativa"
    INACTIVE = "inactive", "Inativa"
    SUSPENDED = "suspended", "Suspensa"
    TRIAL = "trial", "Trial"
