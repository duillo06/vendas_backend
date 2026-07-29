from rest_framework import serializers

from apps.customers.models import Customer, CustomerAddress
from apps.locations.services import LocationCatalogService
from core.serializers.fields import GeoCoordinateField


class CustomerSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True) # o readonly indica que esse campo será apenas enviado para o cliente, não para o backend
    has_account = serializers.BooleanField(read_only=True)

    class Meta:
        model = Customer
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "total_orders",
            "total_spent",
            "last_order_at",
            "has_account",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        data["total_spent"] = float(instance.total_spent)
        return data


class CustomerAddressSerializer(serializers.ModelSerializer):
    city_id = serializers.IntegerField(source="city_ref_id", read_only=True)
    state_id = serializers.IntegerField(source="city_ref.state_id", read_only=True)

    class Meta:
        model = CustomerAddress
        fields = [
            "id",
            "label",
            "street",
            "number",
            "complement",
            "neighborhood",
            "city",
            "state",
            "city_id",
            "state_id",
            "zip_code",
            "reference",
            "latitude",
            "longitude",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        if instance.latitude is not None:
            data["latitude"] = float(instance.latitude)
        if instance.longitude is not None:
            data["longitude"] = float(instance.longitude)
        return data


class CustomerAddressWriteSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=50, required=False, allow_blank=True)
    street = serializers.CharField(max_length=255)
    number = serializers.CharField(max_length=20)
    complement = serializers.CharField(max_length=100, required=False, allow_blank=True)
    neighborhood = serializers.CharField(max_length=100)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=2)
    city_id = serializers.IntegerField(required=False, allow_null=True)
    state_id = serializers.IntegerField(required=False, allow_null=True)
    zip_code = serializers.CharField(max_length=9, required=False, allow_blank=True, default="")
    reference = serializers.CharField(max_length=255, required=False, allow_blank=True)
    latitude = GeoCoordinateField()
    longitude = GeoCoordinateField()
    is_default = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        has_city_id = "city_id" in attrs
        city_id = attrs.pop("city_id", None)
        state_id = attrs.pop("state_id", None)
        if has_city_id and city_id is None:
            attrs["city_ref"] = None
            return attrs
        if city_id is None:
            city_name = attrs.get("city")
            state_acronym = attrs.get("state")
            if city_name and state_acronym:
                city = LocationCatalogService.find_city(
                    city_name=city_name,
                    state_acronym=state_acronym,
                )
                if city:
                    attrs["city"] = city.name
                    attrs["state"] = city.state.acronym
                attrs["city_ref"] = city
            elif "city" in attrs or "state" in attrs:
                attrs["city_ref"] = None
            return attrs

        city = LocationCatalogService.get_city(city_id=city_id, state_id=state_id)
        attrs["city"] = city.name
        attrs["state"] = city.state.acronym
        attrs["city_ref"] = city
        return attrs


class CustomerAdminListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    has_account = serializers.BooleanField(read_only=True)

    class Meta:
        model = Customer
        fields = [
            "id",
            "full_name",
            "phone",
            "email",
            "total_orders",
            "total_spent",
            "last_order_at",
            "has_account",
            "created_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        data["total_spent"] = float(instance.total_spent)
        return data


class CustomerAdminDetailSerializer(CustomerAdminListSerializer):
    addresses = CustomerAddressSerializer(many=True, read_only=True)
    recent_orders = serializers.SerializerMethodField()

    class Meta(CustomerAdminListSerializer.Meta):
        fields = CustomerAdminListSerializer.Meta.fields + ["addresses", "recent_orders"]

    def get_recent_orders(self, instance):
        orders = getattr(instance, "recent_orders_list", [])
        return [
            {
                "id": str(order.id),
                "order_number": order.order_number,
                "status": order.status,
                "total": float(order.total),
                "created_at": order.created_at,
            }
            for order in orders
        ]
