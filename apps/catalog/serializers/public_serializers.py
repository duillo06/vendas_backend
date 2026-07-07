from rest_framework import serializers

from apps.catalog.models import (
    Category,
    Option,
    Product,
    ProductOptionGroup,
)


class CategoryPublicSerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
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
            "description": instance.description,
            "image_url": instance.image_url,
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
            return primary.image_url
        first = obj.images.first()
        return first.image_url if first else None

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
        fields = ["id", "name", "price_modifier", "price_type", "is_available"]

    def to_representation(self, instance):
        return {
            "id": str(instance.id),
            "name": instance.name,
            "price_modifier": float(instance.price_modifier),
            "price_type": instance.price_type,
            "is_available": instance.is_available,
        }


class OptionGroupPublicSerializer(serializers.Serializer):
    def to_representation(self, link: ProductOptionGroup):
        group = link.option_group
        min_sel = link.override_min if link.override_min is not None else group.min_selections
        max_sel = link.override_max if link.override_max is not None else group.max_selections

        return {
            "id": str(group.id),
            "name": group.name,
            "description": group.description,
            "selection_type": group.selection_type,
            "min_selections": min_sel,
            "max_selections": max_sel,
            "is_required": group.is_required,
            "sort_order": link.sort_order,
            "options": OptionPublicSerializer(group.options.all(), many=True).data,
        }


class ProductDetailPublicSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()
    option_groups = serializers.SerializerMethodField()

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
        ]

    def get_images(self, obj):
        return [
            {
                "id": str(img.id),
                "image_url": img.image_url,
                "alt_text": img.alt_text,
                "is_primary": img.is_primary,
            }
            for img in obj.images.all()
        ]

    def get_option_groups(self, obj):
        links = obj.product_option_groups.all()
        return OptionGroupPublicSerializer(links, many=True).data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        data["base_price"] = float(instance.base_price)
        if instance.compare_price is not None:
            data["compare_price"] = float(instance.compare_price)
        return data
