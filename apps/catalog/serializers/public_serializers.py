from rest_framework import serializers

from apps.catalog.models import (
    Category,
    Option,
    Product,
    ProductOptionGroup,
)
from apps.catalog.services.group_config import effective_group_fields
from core.utils.media import absolutize_media_url


class CategoryPublicSerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "emoji",
            "description",
            "image_url",
            "sort_order",
            "product_count",
        ]

    def to_representation(self, instance):
        product_count = getattr(instance, "product_count", None)
        if product_count is None:
            product_count = instance.products.filter(is_active=True, deleted_at__isnull=True).count()

        return {
            "id": str(instance.id),
            "name": instance.name,
            "slug": instance.slug,
            "emoji": instance.emoji or None,
            "description": instance.description,
            "image_url": absolutize_media_url(instance.image_url, self.context.get("request")),
            "sort_order": instance.sort_order,
            "product_count": product_count,
        }


class ProductListPublicSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    has_options = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "base_price",
            "compare_price",
            "image_url",
            "category",
            "is_available",
            "tags",
            "has_options",
        ]

    def get_category(self, obj):
        return {
            "id": str(obj.category_id),
            "name": obj.category.name,
            "slug": obj.category.slug,
        }

    def get_image_url(self, obj):
        primary = next((img for img in obj.images.all() if img.is_primary), None)
        if primary:
            return absolutize_media_url(primary.image_url, self.context.get("request"))
        first = obj.images.first()
        return absolutize_media_url(first.image_url, self.context.get("request")) if first else None

    def get_has_options(self, obj):
        if hasattr(obj, "option_groups_count"):
            return obj.option_groups_count > 0
        return obj.product_option_groups.exists()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        data["base_price"] = float(instance.base_price)
        if instance.compare_price is not None:
            data["compare_price"] = float(instance.compare_price)
        return data


class OptionPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = [
            "id",
            "name",
            "description",
            "price_modifier",
            "price_type",
            "is_available",
            "image_url",
            "icon",
            "stock_quantity",
            "metadata",
        ]

    def to_representation(self, instance):
        request = self.context.get("request")
        in_stock = instance.stock_quantity is None or instance.stock_quantity > 0
        return {
            "id": str(instance.id),
            "name": instance.name,
            "description": instance.description,
            "price_modifier": float(instance.price_modifier),
            "price_type": instance.price_type,
            "is_available": instance.is_available and in_stock,
            "image_url": absolutize_media_url(instance.image_url, request),
            "icon": instance.icon or None,
            "stock_quantity": instance.stock_quantity,
            "metadata": instance.metadata or None,
        }


class OptionGroupPublicSerializer(serializers.Serializer):
    def to_representation(self, link: ProductOptionGroup):
        group = link.option_group
        effective = effective_group_fields(link)
        request = self.context.get("request")

        if effective["visibility"] == "hidden":
            return None

        options = [
            opt
            for opt in OptionPublicSerializer(group.options.all(), many=True, context=self.context).data
            if opt is not None
        ]

        return {
            "id": str(group.id),
            "name": effective["name"],
            "description": effective["description"],
            "selection_type": effective["selection_type"],
            "selection_mode": effective["selection_mode"],
            "display_type": effective["display_type"],
            "min_selections": effective["min_selections"],
            "max_selections": effective["max_selections"],
            "is_required": effective["is_required"],
            "sort_order": link.sort_order,
            "icon": effective["icon"],
            "image_url": absolutize_media_url(effective["image_url"], request),
            "visibility": effective["visibility"],
            "pricing_config": effective["pricing_config"],
            "ui_config": effective["ui_config"],
            "default_option_ids": effective["default_option_ids"],
            "options": options,
        }


class ProductDetailPublicSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()
    option_groups = serializers.SerializerMethodField()
    composition = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "base_price",
            "compare_price",
            "is_available",
            "prep_time",
            "tags",
            "images",
            "option_groups",
            "composition",
        ]

    def get_images(self, obj):
        request = self.context.get("request")
        return [
            {
                "id": str(img.id),
                "image_url": absolutize_media_url(img.image_url, request),
                "alt_text": img.alt_text,
                "is_primary": img.is_primary,
            }
            for img in obj.images.all()
        ]

    def get_option_groups(self, obj):
        links = obj.product_option_groups.all()
        groups = OptionGroupPublicSerializer(links, many=True, context=self.context).data
        return [group for group in groups if group is not None]

    def get_composition(self, obj):
        config = getattr(obj, "composition", None)
        if config is None or not config.is_enabled:
            return None
        return {
            "enabled": True,
            "label": config.label or "Escolher outro sabor",
            "min_parts": config.min_parts,
            "max_parts": config.max_parts,
            "pricing_rule": config.pricing_rule,
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        data["base_price"] = float(instance.base_price)
        if instance.compare_price is not None:
            data["compare_price"] = float(instance.compare_price)
        return data
