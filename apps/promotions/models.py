from django.db import models

from apps.promotions.domain.enums import (
    CampaignMechanism,
    CampaignStatus,
    CommercialGoal,
    RecurrenceType,
)
from core.models.tenant_model import TenantAwareModel


class Campaign(TenantAwareModel):
    """Campanha de promoção — o comerciante vê só a conversa, não este nome."""

    commercial_goal = models.CharField(
        max_length=40,
        choices=CommercialGoal.choices,
        default=CommercialGoal.INCREASE_SALES,
    )
    mechanism = models.CharField(
        max_length=40,
        choices=CampaignMechanism.choices,
        default=CampaignMechanism.PRODUCT_PRICE,
    )
    status = models.CharField(
        max_length=20,
        choices=CampaignStatus.choices,
        default=CampaignStatus.ACTIVE,
    )
    title = models.CharField(max_length=200, blank=True, default="")

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="campaigns",
        db_column="product_id",
        null=True,
        blank=True,
    )
    promo_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    reference_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    recurrence_type = models.CharField(
        max_length=20,
        choices=RecurrenceType.choices,
        default=RecurrenceType.ONCE,
    )
    # 0=segunda … 6=domingo
    weekdays = models.JSONField(default=list, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    time_start = models.TimeField(null=True, blank=True)
    time_end = models.TimeField(null=True, blank=True)

    show_on_home = models.BooleanField(default=True)
    show_on_menu = models.BooleanField(default=True)
    show_on_product = models.BooleanField(default=True)
    link_only = models.BooleanField(default=False)
    show_as_banner = models.BooleanField(default=False)

    class Meta:
        db_table = "campaigns"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "product", "status"]),
            models.Index(fields=["tenant", "starts_at", "ends_at"]),
        ]

    def __str__(self) -> str:
        return self.title or f"Campanha {self.id}"
