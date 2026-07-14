from decimal import Decimal

from rest_framework import serializers

from apps.orders.domain.enums import DeliveryType, PaymentMethod
from apps.orders.models import Order


class CheckoutAddressSerializer(serializers.Serializer):
    street = serializers.CharField(max_length=255)
    number = serializers.CharField(max_length=20)
    complement = serializers.CharField(max_length=100, required=False, allow_blank=True)
    neighborhood = serializers.CharField(max_length=100)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=2)
    zip_code = serializers.CharField(max_length=9)
    reference = serializers.CharField(max_length=255, required=False, allow_blank=True)


class CheckoutItemOptionSerializer(serializers.Serializer):
    option_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=99, required=False, default=1)


class CheckoutItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=99)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True)
    options = CheckoutItemOptionSerializer(many=True, required=False, default=list)


class CheckoutSerializer(serializers.Serializer):
    customer_name = serializers.CharField(min_length=2, max_length=200)
    customer_phone = serializers.CharField(max_length=20)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    delivery_type = serializers.ChoiceField(choices=DeliveryType.choices)
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    change_for = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    address = CheckoutAddressSerializer(required=False, allow_null=True)
    items = CheckoutItemSerializer(many=True, min_length=1)

    def validate(self, attrs):
        delivery_type = attrs.get("delivery_type")
        address = attrs.get("address")
        payment_method = attrs.get("payment_method")
        change_for = attrs.get("change_for")

        if delivery_type == DeliveryType.DELIVERY and not address:
            raise serializers.ValidationError({"address": "Endereço obrigatório para entrega"})

        if delivery_type == DeliveryType.PICKUP:
            attrs["address"] = None

        if payment_method == PaymentMethod.CASH:
            if change_for is None:
                raise serializers.ValidationError({"change_for": "Informe o valor para troco"})
        else:
            attrs["change_for"] = None

        if attrs.get("customer_email") == "":
            attrs["customer_email"] = None

        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        customer_id = attrs.get("customer_id")

        from apps.accounts.principal import CustomerPrincipal

        if isinstance(user, CustomerPrincipal):
            if customer_id and str(user.customer.id) != str(customer_id):
                raise serializers.ValidationError(
                    {"customer_id": "Cliente não corresponde à sessão autenticada"}
                )
            attrs["customer_id"] = user.customer.id
        elif customer_id:
            raise serializers.ValidationError(
                {"customer_id": "Autenticação necessária para vincular o pedido à conta"}
            )

        return attrs


class OrderItemOptionPublicSerializer(serializers.Serializer):
    option_group_name = serializers.CharField()
    option_name = serializers.CharField()
    price_modifier = serializers.DecimalField(max_digits=10, decimal_places=2)


class OrderItemPublicSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    product_name = serializers.CharField()
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    notes = serializers.CharField()
    options = serializers.SerializerMethodField()

    def get_options(self, obj):
        return [
            {
                "option_group_name": opt.option_group_name,
                "option_name": opt.option_name,
                "price_modifier": float(opt.price_modifier),
                "quantity": opt.quantity,
            }
            for opt in obj.options.all()
        ]


class OrderPaymentPublicSerializer(serializers.Serializer):
    method = serializers.CharField()
    status = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class OrderStatusHistoryPublicSerializer(serializers.Serializer):
    status = serializers.CharField(source="to_status")
    created_at = serializers.DateTimeField()


class OrderPublicSerializer(serializers.ModelSerializer):
    payment = OrderPaymentPublicSerializer(read_only=True)
    items = OrderItemPublicSerializer(many=True, read_only=True)
    status_history = OrderStatusHistoryPublicSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "delivery_type",
            "customer_name",
            "customer_phone",
            "subtotal",
            "discount",
            "delivery_fee",
            "total",
            "currency",
            "payment",
            "items",
            "status_history",
            "estimated_prep_at",
            "estimated_delivery_at",
            "created_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["id"] = str(instance.id)
        data["subtotal"] = float(instance.subtotal)
        data["discount"] = float(instance.discount)
        data["delivery_fee"] = float(instance.delivery_fee)
        data["total"] = float(instance.total)
        if instance.payment:
            data["payment"] = {
                "method": instance.payment.method,
                "status": instance.payment.status,
                "amount": float(instance.payment.amount),
            }
        data["items"] = OrderItemPublicSerializer(instance.items.all(), many=True).data
        data["status_history"] = [
            {
                "status": row.to_status,
                "created_at": row.created_at,
            }
            for row in instance.status_history.all()
        ]
        return data
