from decimal import Decimal

from django.db import models

from apps.catalog.domain.enums import (
    CompositionPricingRule,
    CompositionSourceType,
    OptionDisplayType,
    OptionGroupVisibility,
    OptionPriceType,
    OptionSelectionMode,
    OptionSelectionType,
)
from core.models.base import SoftDeleteModel
from core.models.tenant_model import TenantAwareModel
from core.tenancy.managers import TenantManager, TenantQuerySet


class SoftDeleteTenantQuerySet(TenantQuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class SoftDeleteTenantManager(TenantManager):
    def get_queryset(self):
        return SoftDeleteTenantQuerySet(self.model, using=self._db).alive()


class Category(TenantAwareModel, SoftDeleteModel):
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        db_column="parent_id",
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120)
    emoji = models.CharField(max_length=16, blank=True, default="")
    description = models.TextField(blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True, null=True)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    objects = SoftDeleteTenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "categories"
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="uniq_category_tenant_slug"),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active", "sort_order"]),
            models.Index(fields=["tenant", "parent"]),
        ]

    def __str__(self) -> str:
        return self.name


class Product(TenantAwareModel, SoftDeleteModel):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        db_column="category_id",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    description = models.TextField(blank=True, null=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )
    sku = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    prep_time = models.PositiveIntegerField(blank=True, null=True)
    calories = models.PositiveIntegerField(blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(blank=True, null=True)

    objects = SoftDeleteTenantManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "products"
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="uniq_product_tenant_slug"),
            models.CheckConstraint(
                condition=models.Q(base_price__gte=0),
                name="products_positive_price",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "category", "is_active", "sort_order"]),
            models.Index(fields=["tenant", "is_available"]),
        ]

    def __str__(self) -> str:
        return self.name


class ProductImage(TenantAwareModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
        db_column="product_id",
    )
    image_url = models.CharField(max_length=500)
    alt_text = models.CharField(max_length=200, blank=True, null=True)
    sort_order = models.IntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "product_images"
        ordering = ["sort_order", "created_at"]

    def __str__(self) -> str:
        return f"Imagem {self.product.name}"


class OptionGroup(TenantAwareModel):
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True, null=True)
    selection_type = models.CharField(
        max_length=20,
        choices=OptionSelectionType.choices,
        default=OptionSelectionType.SINGLE,
    )
    selection_mode = models.CharField(
        max_length=20,
        choices=OptionSelectionMode.choices,
        default=OptionSelectionMode.PICK,
    )
    display_type = models.CharField(
        max_length=20,
        choices=OptionDisplayType.choices,
        default=OptionDisplayType.RADIO,
    )
    min_selections = models.PositiveIntegerField(default=0)
    max_selections = models.PositiveIntegerField(default=1)
    is_required = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    icon = models.CharField(max_length=16, blank=True, default="")
    image_url = models.URLField(max_length=500, blank=True, null=True)
    visibility = models.CharField(
        max_length=20,
        choices=OptionGroupVisibility.choices,
        default=OptionGroupVisibility.ALWAYS,
    )
    pricing_config = models.JSONField(default=dict, blank=True)
    ui_config = models.JSONField(default=dict, blank=True)
    default_option_ids = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "option_groups"
        ordering = ["sort_order", "name"]
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.name


class Option(TenantAwareModel):
    option_group = models.ForeignKey(
        OptionGroup,
        on_delete=models.CASCADE,
        related_name="options",
        db_column="option_group_id",
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True, null=True)
    price_modifier = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    price_type = models.CharField(
        max_length=20,
        choices=OptionPriceType.choices,
        default=OptionPriceType.FIXED,
    )
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    image_url = models.URLField(max_length=500, blank=True, null=True)
    icon = models.CharField(max_length=16, blank=True, default="")
    stock_quantity = models.PositiveIntegerField(blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)

    class Meta:
        db_table = "options"
        ordering = ["sort_order", "name"]
        indexes = [
            models.Index(fields=["option_group", "is_active", "sort_order"]),
            models.Index(fields=["tenant", "option_group"]),
        ]

    def __str__(self) -> str:
        return self.name


class ProductOptionGroup(TenantAwareModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="product_option_groups",
        db_column="product_id",
    )
    option_group = models.ForeignKey(
        OptionGroup,
        on_delete=models.CASCADE,
        related_name="product_option_groups",
        db_column="option_group_id",
    )
    sort_order = models.IntegerField(default=0)
    override_min = models.PositiveIntegerField(blank=True, null=True)
    override_max = models.PositiveIntegerField(blank=True, null=True)
    override_required = models.BooleanField(blank=True, null=True)
    override_display_type = models.CharField(
        max_length=20,
        choices=OptionDisplayType.choices,
        blank=True,
        null=True,
    )
    override_pricing_config = models.JSONField(blank=True, null=True)
    override_ui_config = models.JSONField(blank=True, null=True)

    class Meta:
        db_table = "product_option_groups"
        ordering = ["sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "option_group"],
                name="uniq_product_option_group",
            ),
        ]
        indexes = [
            models.Index(fields=["product", "sort_order"]),
        ]


class ProductComposition(TenantAwareModel):
    """Config genérica: um produto pode ser composto por OUTROS produtos.

    Ex: pizza meio a meio — o cliente escolhe outro produto (sabor) da mesma
    categoria pra compor. Não é grupo de opções: são produtos de verdade.
    """

    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="composition",
        db_column="product_id",
    )
    is_enabled = models.BooleanField(default=False)
    source_type = models.CharField(
        max_length=20,
        choices=CompositionSourceType.choices,
        default=CompositionSourceType.CATEGORY,
    )
    # usado quando source_type=category; vazio = usa a categoria do próprio produto
    source_category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="composition_sources",
        db_column="source_category_id",
    )
    source_tag = models.CharField(max_length=50, blank=True, default="")
    # lista personalizada (source_type=custom)
    custom_products = models.ManyToManyField(
        Product,
        related_name="composition_memberships",
        blank=True,
    )
    label = models.CharField(max_length=80, blank=True, default="Escolher outro sabor")
    # total de partes contando o produto principal (o cliente escolhe partes - 1)
    min_parts = models.PositiveIntegerField(default=2)
    max_parts = models.PositiveIntegerField(default=2)
    pricing_rule = models.CharField(
        max_length=20,
        choices=CompositionPricingRule.choices,
        default=CompositionPricingRule.HIGHEST,
    )

    class Meta:
        db_table = "product_compositions"
        indexes = [
            models.Index(fields=["tenant", "is_enabled"]),
        ]

    def __str__(self) -> str:
        return f"Composição de {self.product.name}"
