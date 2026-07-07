from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.companies.models import Company
from apps.companies.services.settings_service import SettingsService
from apps.customers.services.customer_service import CustomerService
from apps.orders.domain.enums import (
    DeliveryType,
    OrderSource,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    VALID_TRANSITIONS,
)
from apps.orders.domain.exceptions import EmptyCartError, InvalidOrderTransition, MinOrderValueError
from apps.orders.models import Order, OrderItem, OrderItemOption, OrderPayment, OrderStatusHistory
from apps.orders.services.cart_validation_service import CartValidationService
from core.utils.money import round_money


class OrderService:
    @staticmethod
    @transaction.atomic
    def create_from_checkout(*, tenant: Company, data: dict) -> Order:
        items = data.get("items") or []
        if not items:
            raise EmptyCartError()

        validated_items = CartValidationService.validate(tenant=tenant, items=items)
        subtotal = round_money(sum((item["total_price"] for item in validated_items), Decimal("0")))

        settings = SettingsService.get_for_tenant(tenant)
        if settings.min_order_value and subtotal < settings.min_order_value:
            raise MinOrderValueError(
                f"Pedido mínimo: R$ {settings.min_order_value:.2f}".replace(".", ",")
            )

        delivery_type = data["delivery_type"]
        delivery_fee = OrderService._calculate_delivery_fee(
            tenant=tenant,
            delivery_type=delivery_type,
            subtotal=subtotal,
        )
        total = round_money(subtotal + delivery_fee)

        payment_method = data["payment_method"]
        change_for = data.get("change_for")
        if payment_method == PaymentMethod.CASH:
            if change_for is None:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"change_for": "Informe o valor para troco"})
            if Decimal(str(change_for)) <= total:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"change_for": "Troco deve ser maior que o total"})

        customer = CustomerService.get_or_create_from_checkout(
            tenant=tenant,
            name=data["customer_name"],
            phone=data["customer_phone"],
            email=data.get("customer_email"),
        )

        order_number = OrderService._generate_order_number(tenant)
        now = timezone.now()
        prep_delta = timedelta(minutes=settings.estimated_prep_time)
        delivery_delta = timedelta(minutes=settings.estimated_delivery_time)

        address = data.get("address") if delivery_type == DeliveryType.DELIVERY else None

        order = Order.objects.create(
            tenant=tenant,
            customer=customer,
            order_number=order_number,
            status=OrderStatus.PENDING,
            delivery_type=delivery_type,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            total=total,
            customer_name=data["customer_name"].strip(),
            customer_phone=customer.phone,
            delivery_address=address,
            notes=(data.get("notes") or "").strip(),
            source=OrderSource.STOREFRONT,
            estimated_prep_at=now + prep_delta,
            estimated_delivery_at=(
                now + prep_delta + delivery_delta
                if delivery_type == DeliveryType.DELIVERY
                else None
            ),
        )

        for item_data in validated_items:
            order_item = OrderItem.objects.create(
                tenant=tenant,
                order=order,
                product_id=item_data["product_id"],
                product_name=item_data["product_name"],
                unit_price=item_data["unit_price"],
                quantity=item_data["quantity"],
                total_price=item_data["total_price"],
                notes=item_data.get("notes", ""),
            )
            for opt in item_data["options"]:
                OrderItemOption.objects.create(
                    tenant=tenant,
                    order_item=order_item,
                    option_group_name=opt["group_name"],
                    option_name=opt["name"],
                    price_modifier=opt["price_modifier"],
                    option_id=opt.get("option_id"),
                )

        OrderPayment.objects.create(
            tenant=tenant,
            order=order,
            method=payment_method,
            status="pending",
            amount=total,
            change_for=Decimal(str(change_for)) if change_for is not None else None,
        )

        OrderService._record_status(order, None, OrderStatus.PENDING)
        CustomerService.record_order(customer=customer, total=total)

        return order

    @staticmethod
    def get_public_order(*, tenant: Company, order_id) -> Order:
        return (
            Order.objects.filter(id=order_id, tenant=tenant)
            .prefetch_related("items__options", "status_history", "payment")
            .get()
        )

    @staticmethod
    def get_admin_order(*, tenant: Company, order_id) -> Order:
        return (
            Order.objects.filter(id=order_id, tenant=tenant)
            .select_related("customer", "payment")
            .prefetch_related("items__options", "status_history__changed_by")
            .get()
        )

    @staticmethod
    @transaction.atomic
    def update_status(
        *,
        order: Order,
        new_status: str,
        employee=None,
        notes: str | None = None,
    ) -> Order:
        order = Order.objects.select_for_update().select_related("payment").get(pk=order.pk)
        current = order.status

        allowed = VALID_TRANSITIONS.get(current, [])
        if new_status not in allowed:
            raise InvalidOrderTransition(current, new_status)

        if new_status == OrderStatus.CANCELLED and not (notes or "").strip():
            raise ValidationError({"notes": "Informe o motivo do cancelamento"})

        now = timezone.now()
        order.status = new_status

        if new_status == OrderStatus.CONFIRMED:
            order.confirmed_at = now
        elif new_status == OrderStatus.COMPLETED:
            order.completed_at = now
        elif new_status == OrderStatus.CANCELLED:
            order.cancelled_at = now
            order.cancellation_reason = notes.strip()

        order.save()
        OrderService._record_status(order, current, new_status, employee, notes)
        return order

    @staticmethod
    @transaction.atomic
    def update_payment(*, order: Order, status: str) -> Order:
        order = Order.objects.select_for_update().select_related("payment").get(pk=order.pk)
        payment = order.payment

        if status != PaymentStatus.PAID:
            raise ValidationError({"status": "Status de pagamento inválido"})

        payment.status = PaymentStatus.PAID
        payment.paid_at = timezone.now()
        payment.save(update_fields=["status", "paid_at", "updated_at"])
        return order

    @staticmethod
    def _calculate_delivery_fee(*, tenant: Company, delivery_type: str, subtotal: Decimal) -> Decimal:
        if delivery_type != DeliveryType.DELIVERY:
            return Decimal("0.00")

        settings = SettingsService.get_for_tenant(tenant)
        fee = settings.delivery_fee or Decimal("0")

        if settings.free_delivery_above and subtotal >= settings.free_delivery_above:
            return Decimal("0.00")

        return round_money(fee)

    @staticmethod
    def _generate_order_number(tenant: Company) -> str:
        last = (
            Order.all_objects.filter(tenant=tenant)
            .order_by("-created_at")
            .values_list("order_number", flat=True)
            .first()
        )
        if last:
            num = int(last.replace("#", "")) + 1
        else:
            num = 1
        return f"#{num:04d}"

    @staticmethod
    def _record_status(order: Order, from_status: str | None, to_status: str, employee=None, notes=None):
        OrderStatusHistory.objects.create(
            tenant=order.tenant,
            order=order,
            from_status=from_status,
            to_status=to_status,
            changed_by=employee,
            notes=notes or "",
        )
