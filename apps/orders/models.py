from decimal import Decimal

from django.db import models

from apps.orders.domain.enums import DeliveryType, OrderSource, OrderStatus
from core.models.tenant_model import TenantAwareModel


class Order(TenantAwareModel):
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="orders",
        db_column="customer_id",
    )
    order_number = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        db_index=True,
    )
    delivery_type = models.CharField(max_length=20, choices=DeliveryType.choices)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="BRL")
    coupon_id = models.UUIDField(null=True, blank=True)
    coupon_code = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, default="")
    internal_notes = models.TextField(blank=True, default="")
    delivery_address = models.JSONField(null=True, blank=True)
    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=20)
    estimated_prep_at = models.DateTimeField(null=True, blank=True)
    estimated_delivery_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, blank=True, default="")
    source = models.CharField(
        max_length=20,
        choices=OrderSource.choices,
        default=OrderSource.STOREFRONT,
    )

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "order_number"],
                name="unique_order_number_per_tenant",
            ),
            models.CheckConstraint(
                condition=models.Q(total__gte=0),
                name="orders_positive_total",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "-created_at"]),
            models.Index(fields=["tenant", "customer", "-created_at"]),
        ]

    def __str__(self) -> str:
        return self.order_number


class OrderItem(TenantAwareModel):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        db_column="order_id",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
        db_column="product_id",
    )
    product_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "order_items"
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["tenant", "product"]),
        ]

    def __str__(self) -> str:
        return f"{self.product_name} x{self.quantity}"


class OrderItemOption(TenantAwareModel):
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name="options",
        db_column="order_item_id",
    )
    option_group_name = models.CharField(max_length=100)
    option_name = models.CharField(max_length=100)
    price_modifier = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    option = models.ForeignKey(
        "catalog.Option",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_item_options",
        db_column="option_id",
    )

    class Meta:
        db_table = "order_item_options"
        indexes = [
            models.Index(fields=["order_item"]),
        ]


class OrderItemComponent(TenantAwareModel):
    """Snapshot dos produtos que compõem um item (ex: 2º sabor da pizza)."""

    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name="components",
        db_column="order_item_id",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_item_components",
        db_column="product_id",
    )
    product_name = models.CharField(max_length=200)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "order_item_components"
        ordering = ["sort_order"]
        indexes = [
            models.Index(fields=["order_item"]),
        ]

    def __str__(self) -> str:
        return self.product_name


class OrderStatusHistory(TenantAwareModel):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_history",
        db_column="order_id",
    )
    from_status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        null=True,
        blank=True,
    )
    to_status = models.CharField(max_length=20, choices=OrderStatus.choices)
    changed_by = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_status_changes",
        db_column="changed_by_id",
    )
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "order_status_history"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["order", "created_at"]),
        ]


class OrderPayment(TenantAwareModel):
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="payment",
        db_column="order_id",
    )
    method = models.CharField(max_length=30)
    status = models.CharField(max_length=20, default="pending")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    change_for = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True, default="")
    gateway_transaction_id = models.CharField(max_length=255, blank=True, null=True)
    gateway_data = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "order_payments"
