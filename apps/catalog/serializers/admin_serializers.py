from rest_framework import serializers

from apps.catalog.models import (
    Category,
    Option,
    OptionGroup,
    Product,
    ProductImage,
    ProductOptionGroup,
)
from core.utils.media import absolutize_media_url


class CategoryAdminSerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "emoji",
            "description",
            "image_url",
            "parent_id",
            "sort_order",
            "is_active",
            "product_count",
        ]
        read_only_fields = ["id", "product_count", "slug"]

    def validate_emoji(self, value):
        emoji = (value or "").strip()
        if len(emoji) > 8:
            raise serializers.ValidationError("Use apenas um emoji.")
        return emoji

    def get_product_count(self, obj):
        return obj.products.filter(deleted_at__isnull=True).count()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        data["image_url"] = absolutize_media_url(instance.image_url, self.context.get("request"))
        if instance.parent_id:
            data["parent_id"] = str(instance.parent_id)
        else:
            data["parent_id"] = None
        return data


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image_url", "alt_text", "is_primary", "sort_order"]
        read_only_fields = fields

    def to_representation(self, instance):
        return {
            "id": str(instance.id),
            "image_url": absolutize_media_url(instance.image_url, self.context.get("request")),
            "alt_text": instance.alt_text,
            "is_primary": instance.is_primary,
            "sort_order": instance.sort_order,
        }


class ProductAdminListSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "base_price",
            "category",
            "is_active",
            "is_available",
            "sort_order",
            "image_url",
            "created_at",
        ]

    def get_category(self, obj):
        return {
            "id": str(obj.category_id),
            "name": obj.category.name,
            "slug": obj.category.slug,
        }

    def get_image_url(self, obj):
        primary = obj.images.filter(is_primary=True).first() or obj.images.first()
        if not primary:
            return None
        return absolutize_media_url(primary.image_url, self.context.get("request"))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        data["base_price"] = float(instance.base_price)
        return data


class ProductCompositionWriteSerializer(serializers.Serializer):
    enabled = serializers.BooleanField(required=False, default=False)
    source_type = serializers.ChoiceField(
        choices=["category", "tag", "custom"],
        required=False,
        default="category",
    )
    source_category_id = serializers.UUIDField(required=False, allow_null=True)
    source_tag = serializers.CharField(required=False, allow_blank=True, default="")
    custom_product_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )
    label = serializers.CharField(required=False, allow_blank=True, max_length=80, default="")
    min_parts = serializers.IntegerField(required=False, min_value=1, default=2)
    max_parts = serializers.IntegerField(required=False, min_value=1, default=2)
    pricing_rule = serializers.ChoiceField(
        choices=["highest", "average", "sum", "main"],
        required=False,
        default="highest",
    )

    def validate(self, attrs):
        if attrs.get("max_parts", 2) < attrs.get("min_parts", 2):
            raise serializers.ValidationError("max_parts deve ser >= min_parts")
        return attrs


class ProductOptionGroupWriteSerializer(serializers.Serializer):
    option_group_id = serializers.UUIDField()
    sort_order = serializers.IntegerField(required=False, default=0)
    override_min = serializers.IntegerField(required=False, allow_null=True)
    override_max = serializers.IntegerField(required=False, allow_null=True)
    override_required = serializers.BooleanField(required=False, allow_null=True)
    override_display_type = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    override_pricing_config = serializers.JSONField(required=False, allow_null=True)
    override_ui_config = serializers.JSONField(required=False, allow_null=True)


class ProductAdminDetailSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()
    category_id = serializers.UUIDField()
    images = ProductImageSerializer(many=True, read_only=True)
    option_group_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )
    product_option_groups = ProductOptionGroupWriteSerializer(many=True, required=False, write_only=True)
    composition = ProductCompositionWriteSerializer(required=False, write_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "base_price",
            "compare_price",
            "category_id",
            "category",
            "sku",
            "is_active",
            "is_available",
            "sort_order",
            "prep_time",
            "tags",
            "metadata",
            "images",
            "option_group_ids",
            "product_option_groups",
            "composition",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "category", "images", "created_at", "updated_at", "slug"]

    def validate_category_id(self, value):
        from core.tenancy.context import TenantContext

        tenant = TenantContext.get()
        if not Category.objects.filter(id=value, tenant=tenant).exists():
            raise serializers.ValidationError("Categoria inválida")
        return value

    def get_category(self, obj):
        return {
            "id": str(obj.category_id),
            "name": obj.category.name,
            "slug": obj.category.slug,
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        data["category_id"] = str(instance.category_id)
        data["base_price"] = float(instance.base_price)
        if instance.compare_price is not None:
            data["compare_price"] = float(instance.compare_price)
        links = instance.product_option_groups.select_related("option_group").prefetch_related(
            "option_group__options",
        ).order_by("sort_order")
        data["product_option_groups"] = ProductOptionGroupReadSerializer(
            links,
            many=True,
            context=self.context,
        ).data
        data["option_group_ids"] = [
            str(link.option_group_id) for link in instance.product_option_groups.all()
        ]
        config = getattr(instance, "composition", None)
        if config is not None:
            data["composition"] = {
                "enabled": config.is_enabled,
                "source_type": config.source_type,
                "source_category_id": str(config.source_category_id)
                if config.source_category_id
                else None,
                "source_tag": config.source_tag or "",
                "custom_product_ids": [str(p.id) for p in config.custom_products.all()],
                "label": config.label or "",
                "min_parts": config.min_parts,
                "max_parts": config.max_parts,
                "pricing_rule": config.pricing_rule,
            }
        else:
            data["composition"] = None
        return data


class OptionAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = [
            "id",
            "name",
            "description",
            "price_modifier",
            "price_type",
            "is_active",
            "is_available",
            "sort_order",
            "image_url",
            "icon",
            "stock_quantity",
            "metadata",
        ]
        read_only_fields = ["id"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        data["price_modifier"] = float(instance.price_modifier)
        data["image_url"] = absolutize_media_url(instance.image_url, self.context.get("request"))
        return data


class OptionGroupAdminSerializer(serializers.ModelSerializer):
    options = OptionAdminSerializer(many=True, read_only=True)
    options_count = serializers.SerializerMethodField()

    class Meta:
        model = OptionGroup
        fields = [
            "id",
            "name",
            "description",
            "selection_type",
            "selection_mode",
            "display_type",
            "min_selections",
            "max_selections",
            "is_required",
            "is_active",
            "sort_order",
            "icon",
            "image_url",
            "visibility",
            "pricing_config",
            "ui_config",
            "default_option_ids",
            "options",
            "options_count",
        ]
        read_only_fields = ["id", "options", "options_count"]

    def get_options_count(self, obj):
        return obj.options.count()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        data["image_url"] = absolutize_media_url(instance.image_url, self.context.get("request"))
        if not data.get("pricing_config"):
            data["pricing_config"] = {"strategy": "additive"}
        return data


class ProductOptionGroupReadSerializer(serializers.ModelSerializer):
    option_group_id = serializers.UUIDField(read_only=True)
    group = OptionGroupAdminSerializer(source="option_group", read_only=True)

    class Meta:
        model = ProductOptionGroup
        fields = [
            "id",
            "option_group_id",
            "sort_order",
            "override_min",
            "override_max",
            "override_required",
            "override_display_type",
            "override_pricing_config",
            "override_ui_config",
            "group",
        ]
        read_only_fields = fields
