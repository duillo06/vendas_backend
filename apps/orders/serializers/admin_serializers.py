from rest_framework import serializers

from apps.orders.models import Order


class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class OrderPaymentUpdateSerializer(serializers.Serializer):
    status = serializers.CharField()


class OrderListSerializer(serializers.ModelSerializer):
    items_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "customer_name",
            "customer_phone",
            "delivery_type",
            "total",
            "items_count",
            "created_at",
        ]

    def to_representation(self, instance):
        return {
            "id": str(instance.id),
            "order_number": instance.order_number,
            "status": instance.status,
            "customer_name": instance.customer_name,
            "customer_phone": instance.customer_phone,
            "delivery_type": instance.delivery_type,
            "total": float(instance.total),
            "items_count": getattr(instance, "items_count", instance.items.count()),
            "created_at": instance.created_at.isoformat().replace("+00:00", "Z"),
        }


class OrderDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "delivery_type",
            "customer",
            "subtotal",
            "discount",
            "delivery_fee",
            "total",
            "currency",
            "notes",
            "internal_notes",
            "delivery_address",
            "payment",
            "items",
            "status_history",
            "confirmed_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        customer = instance.customer
        payment = getattr(instance, "payment", None)

        return {
            "id": str(instance.id),
            "order_number": instance.order_number,
            "status": instance.status,
            "delivery_type": instance.delivery_type,
            "customer": {
                "id": str(customer.id),
                "name": f"{customer.first_name} {customer.last_name}".strip() or instance.customer_name,
                "phone": instance.customer_phone,
                "email": customer.email,
            },
            "subtotal": float(instance.subtotal),
            "discount": float(instance.discount),
            "delivery_fee": float(instance.delivery_fee),
            "total": float(instance.total),
            "currency": instance.currency,
            "notes": instance.notes,
            "internal_notes": instance.internal_notes,
            "delivery_address": instance.delivery_address,
            "payment": {
                "method": payment.method,
                "status": payment.status,
                "amount": float(payment.amount),
                "change_for": float(payment.change_for) if payment.change_for is not None else None,
                "paid_at": payment.paid_at.isoformat().replace("+00:00", "Z")
                if payment.paid_at
                else None,
            }
            if payment
            else None,
            "items": [
                {
                    "id": str(item.id),
                    "product_id": str(item.product_id) if item.product_id else None,
                    "product_name": item.product_name,
                    "quantity": item.quantity,
                    "unit_price": float(item.unit_price),
                    "total_price": float(item.total_price),
                    "notes": item.notes,
                    "options": [
                        {
                            "option_group_name": opt.option_group_name,
                            "option_name": opt.option_name,
                            "price_modifier": float(opt.price_modifier),
                        }
                        for opt in item.options.all()
                    ],
                }
                for item in instance.items.all()
            ],
            "status_history": [
                {
                    "from_status": row.from_status,
                    "to_status": row.to_status,
                    # nome pra UI — UUID técnico nunca na tela
                    "changed_by": (
                        f"{row.changed_by.first_name} {row.changed_by.last_name}".strip()
                        if row.changed_by_id
                        else None
                    )
                    or None,
                    "notes": row.notes or None,
                    "created_at": row.created_at.isoformat().replace("+00:00", "Z"),
                }
                for row in instance.status_history.all()
            ],
            "confirmed_at": instance.confirmed_at.isoformat().replace("+00:00", "Z")
            if instance.confirmed_at
            else None,
            "completed_at": instance.completed_at.isoformat().replace("+00:00", "Z")
            if instance.completed_at
            else None,
            "created_at": instance.created_at.isoformat().replace("+00:00", "Z"),
            "updated_at": instance.updated_at.isoformat().replace("+00:00", "Z"),
        }
