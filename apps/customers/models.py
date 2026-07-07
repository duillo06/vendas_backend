from django.db import models

from core.models.base import BaseModel, SoftDeleteModel
from core.models.tenant_model import TenantAwareModel


class Customer(TenantAwareModel, SoftDeleteModel):
    email = models.EmailField(max_length=254, blank=True, null=True)
    phone = models.CharField(max_length=20)
    password_hash = models.CharField(max_length=255, blank=True, null=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True, default="")
    is_active = models.BooleanField(default=True)
    last_order_at = models.DateTimeField(null=True, blank=True)
    total_orders = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = "customers"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "phone"], name="uniq_customer_tenant_phone"),
        ]
        indexes = [
            models.Index(fields=["tenant", "last_order_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.phone
