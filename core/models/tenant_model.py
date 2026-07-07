from django.db import models

from core.models.base import BaseModel
from core.tenancy.managers import TenantManager


class TenantAwareModel(BaseModel):
    tenant = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="%(class)ss",
        db_column="tenant_id",
    )

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
