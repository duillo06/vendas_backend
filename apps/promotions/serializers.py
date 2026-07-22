from rest_framework import serializers

from apps.promotions.domain.enums import (
    CampaignMechanism,
    CampaignStatus,
    CommercialGoal,
    RecurrenceType,
)
from apps.promotions.models import Campaign
from apps.promotions.services.campaign_resolver import CampaignResolver
from core.utils.media import absolutize_media_url


class CampaignWriteSerializer(serializers.Serializer):
    commercial_goal = serializers.ChoiceField(
        choices=CommercialGoal.values,
        required=False,
        default=CommercialGoal.INCREASE_SALES,
    )
    mechanism = serializers.ChoiceField(
        choices=CampaignMechanism.values,
        required=False,
        default=CampaignMechanism.PRODUCT_PRICE,
    )
    status = serializers.ChoiceField(
        choices=CampaignStatus.values,
        required=False,
        default=CampaignStatus.ACTIVE,
    )
    title = serializers.CharField(required=False, allow_blank=True, max_length=200)
    product_id = serializers.UUIDField(required=False)
    promo_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    recurrence_type = serializers.ChoiceField(
        choices=RecurrenceType.values,
        required=False,
        default=RecurrenceType.ONCE,
    )
    weekdays = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
        default=list,
    )
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    show_on_home = serializers.BooleanField(required=False, default=True)
    show_on_menu = serializers.BooleanField(required=False, default=True)
    show_on_product = serializers.BooleanField(required=False, default=True)
    link_only = serializers.BooleanField(required=False, default=False)
    show_as_banner = serializers.BooleanField(required=False, default=False)


class CampaignAdminSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True, default="")
    save_amount = serializers.SerializerMethodField()
    discount_percent = serializers.SerializerMethodField()
    badges = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            "id",
            "commercial_goal",
            "mechanism",
            "status",
            "title",
            "product_id",
            "product_name",
            "promo_price",
            "reference_price",
            "recurrence_type",
            "weekdays",
            "starts_at",
            "ends_at",
            "show_on_home",
            "show_on_menu",
            "show_on_product",
            "link_only",
            "show_as_banner",
            "save_amount",
            "discount_percent",
            "badges",
            "created_at",
            "updated_at",
        ]

    def get_save_amount(self, obj):
        if obj.reference_price is None or obj.promo_price is None:
            return None
        save, _ = CampaignResolver.indicators(obj.reference_price, obj.promo_price)
        return float(save)

    def get_discount_percent(self, obj):
        if obj.reference_price is None or obj.promo_price is None:
            return None
        _, pct = CampaignResolver.indicators(obj.reference_price, obj.promo_price)
        return pct

    def get_badges(self, obj):
        if obj.reference_price is None or obj.promo_price is None:
            return []
        save, pct = CampaignResolver.indicators(obj.reference_price, obj.promo_price)
        from django.utils import timezone

        return CampaignResolver.badges_for(
            save=save,
            pct=pct,
            ends_at=obj.ends_at,
            now=timezone.now(),
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        if instance.promo_price is not None:
            data["promo_price"] = float(instance.promo_price)
        if instance.reference_price is not None:
            data["reference_price"] = float(instance.reference_price)
        return data


def serialize_public_offer(offer, request=None) -> dict:
    product = offer.campaign.product
    image_url = None
    if product is not None:
        primary = next((img for img in product.images.all() if img.is_primary), None)
        img = primary or product.images.first()
        if img:
            image_url = absolutize_media_url(img.image_url, request)

    payload = offer.as_public_dict()
    payload.update(
        {
            "product_id": str(product.id) if product else None,
            "product_slug": product.slug if product else None,
            "product_name": product.name if product else offer.campaign.title,
            "image_url": image_url,
            "is_available": bool(product and product.is_available),
        }
    )
    return payload
