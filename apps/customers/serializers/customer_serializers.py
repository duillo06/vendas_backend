from rest_framework import serializers

from apps.customers.models import Customer, CustomerAddress
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
    zip_code = serializers.CharField(max_length=9, required=False, allow_blank=True, default="")
    reference = serializers.CharField(max_length=255, required=False, allow_blank=True)
    latitude = GeoCoordinateField()
    longitude = GeoCoordinateField()
    is_default = serializers.BooleanField(required=False, default=False)


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
