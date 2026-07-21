from decimal import Decimal

from django.core.validators import EmailValidator
from django.db import models

from apps.companies.domain.enums import CompanyStatus
from apps.companies.domain.validators import validate_subdomain
from core.models.base import BaseModel
from core.models.tenant_model import TenantAwareModel

DEFAULT_PAYMENT_METHODS = ["cash", "pix", "card_on_delivery"]


class Company(BaseModel):
    # a company É o tenant — não tem tenant_id
    subdomain = models.CharField(max_length=63, unique=True, validators=[validate_subdomain])
    slug = models.SlugField(max_length=100, unique=True)
    legal_name = models.CharField(max_length=255)
    trade_name = models.CharField(max_length=255)
    document = models.CharField(max_length=18, blank=True, null=True)
    email = models.EmailField(max_length=254, validators=[EmailValidator()])
    phone = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=CompanyStatus.choices,
        default=CompanyStatus.ACTIVE,
        db_index=True,
    )
    logo_url = models.URLField(max_length=500, blank=True, null=True)
    cover_url = models.URLField(max_length=500, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    timezone = models.CharField(max_length=50, default="America/Sao_Paulo")

    class Meta:
        db_table = "companies"
        ordering = ["trade_name"]

    def __str__(self) -> str:
        return self.trade_name


class CompanySettings(TenantAwareModel):
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    free_delivery_above = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    estimated_prep_time = models.PositiveIntegerField(default=30)
    estimated_delivery_time = models.PositiveIntegerField(default=45)
    accepts_delivery = models.BooleanField(default=True)
    accepts_pickup = models.BooleanField(default=True)
    accepts_dine_in = models.BooleanField(default=False)
    is_open = models.BooleanField(default=True)
    auto_close_outside_hours = models.BooleanField(default=True)
    payment_methods = models.JSONField(default=list)
    delivery_areas = models.JSONField(blank=True, null=True)
    theme = models.JSONField(blank=True, null=True)
    notification_settings = models.JSONField(blank=True, null=True)
    # Fase 4 — progresso do assistente de 1ª configuração
    setup = models.JSONField(blank=True, null=True, default=dict)

    class Meta:
        db_table = "company_settings"
        constraints = [
            models.UniqueConstraint(fields=["tenant"], name="uniq_company_settings_tenant"),
        ]

    def save(self, *args, **kwargs):
        # garante lista padrão de pagamento no MVP
        if not self.payment_methods:
            self.payment_methods = list(DEFAULT_PAYMENT_METHODS)
        super().save(*args, **kwargs)


class BusinessHours(TenantAwareModel):
    # 0=segunda ... 6=domingo
    day_of_week = models.PositiveSmallIntegerField()
    opens_at = models.TimeField()
    closes_at = models.TimeField()
    is_closed = models.BooleanField(default=False)

    class Meta:
        db_table = "business_hours"
        ordering = ["day_of_week"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "day_of_week"],
                name="uniq_business_hours_tenant_day",
            ),
            models.CheckConstraint(
                condition=models.Q(day_of_week__gte=0, day_of_week__lte=6),
                name="business_hours_valid_day",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.tenant.trade_name} — dia {self.day_of_week}"
