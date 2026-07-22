from django.contrib.auth.hashers import check_password, make_password
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

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def set_password(self, raw_password: str) -> None:
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password(raw_password, self.password_hash)

    @property
    def has_account(self) -> bool:
        return bool(self.password_hash)


class CustomerAddress(TenantAwareModel):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="addresses",
        db_column="customer_id",
    )
    label = models.CharField(max_length=50, blank=True, default="")
    street = models.CharField(max_length=255)
    number = models.CharField(max_length=20)
    complement = models.CharField(max_length=100, blank=True, default="")
    neighborhood = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    zip_code = models.CharField(max_length=9)
    reference = models.CharField(max_length=255, blank=True, default="")
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = "customer_addresses"
        ordering = ["-is_default", "-created_at"]
        indexes = [
            models.Index(fields=["customer"], name="customer_ad_custome_0f0f0d_idx"),
            models.Index(fields=["tenant", "customer"], name="customer_ad_tenant__a1b2c3_idx"),
        ]
