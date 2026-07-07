from rest_framework import serializers

from apps.catalog.models import (
    Category,
    Option,
    OptionGroup,
    Product,
    ProductImage,
)


class CategoryAdminSerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "image_url",
            "parent_id",
            "sort_order",
            "is_active",
            "product_count",
        ]
        read_only_fields = ["id", "product_count", "slug"]

    def get_product_count(self, obj):
        return obj.products.filter(deleted_at__isnull=True).count()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
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
            "image_url": instance.image_url,
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
        return primary.image_url if primary else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        data["base_price"] = float(instance.base_price)
        return data


class ProductAdminDetailSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()
    images = ProductImageSerializer(many=True, read_only=True)
    option_group_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )

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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "category", "images", "created_at", "updated_at", "slug"]

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
        data["option_group_ids"] = [
            str(link.option_group_id) for link in instance.product_option_groups.all()
        ]
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
        ]
        read_only_fields = ["id"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        data["price_modifier"] = float(instance.price_modifier)
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
            "min_selections",
            "max_selections",
            "is_required",
            "is_active",
            "sort_order",
            "options",
            "options_count",
        ]
        read_only_fields = ["id", "options", "options_count"]

    def get_options_count(self, obj):
        return obj.options.count()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        return data
