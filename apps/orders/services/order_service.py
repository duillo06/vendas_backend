from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.catalog.services.option_stock_service import OptionStockService
from apps.companies.models import Company
from apps.companies.services.geo_service import cities_match, normalize_state
from apps.companies.services.settings_service import SettingsService
from apps.customers.services.customer_service import CustomerService
from apps.orders.domain.enums import (
    VALID_TRANSITIONS,
    DeliveryType,
    OrderSource,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)
from apps.orders.domain.exceptions import (
    DineInNotAcceptedError,
    EmptyCartError,
    InvalidOrderTransition,
    MinOrderValueError,
    OutOfDeliveryAreaError,
)
from apps.orders.models import (
    Order,
    OrderItem,
    OrderItemComponent,
    OrderItemOption,
    OrderPayment,
    OrderStatusHistory,
)
from apps.orders.services.cart_validation_service import CartValidationService
from apps.orders.services.table_service import TableService
from core.utils.money import round_money


class OrderService:
    @staticmethod
    def _assert_delivery_area(*, settings, address: dict | None) -> None:
        store_city = (settings.delivery_city or "").strip()
        store_state = normalize_state(settings.delivery_state or "")
        if not store_city or not store_state:
            return
        if not address:
            return

        if settings.delivery_city_ref_id:
            if not address.get("city_id"):
                raise OutOfDeliveryAreaError(
                    "Escolha novamente a cidade do endereço para continuar."
                )
            if int(address["city_id"]) == settings.delivery_city_ref_id:
                return
            raise OutOfDeliveryAreaError(
                f"Nossa entrega é só em {store_city} ({store_state})."
            )

        city = (address.get("city") or "").strip()
        state = normalize_state(address.get("state") or "")
        if cities_match(city, store_city) and state == store_state:
            return

        raise OutOfDeliveryAreaError(
            f"Não entregamos em {city or 'outra cidade'}. "
            f"Nossa entrega é só em {store_city} ({store_state})."
        )

    @staticmethod
    def _json_safe_address(address: dict | None) -> dict | None:
        """JSONB não aceita Decimal — lat/lng viram float"""
        if not address:
            return None
        safe = dict(address)
        for key in ("latitude", "longitude"):
            value = safe.get(key)
            if isinstance(value, Decimal):
                safe[key] = float(value)
        return safe

    @staticmethod
    @transaction.atomic
    def create_from_checkout(
        *,
        tenant: Company,
        data: dict,
        authenticated_customer=None,
    ) -> Order:
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
        OrderService._assert_channel_accepted(settings=settings, delivery_type=delivery_type)

        dining_table = None
        table_number = None
        if delivery_type == DeliveryType.DINE_IN:
            dining_table = TableService.resolve_for_checkout(
                tenant=tenant,
                table_id=data.get("table_id"),
                qr_token=data.get("qr_token"),
            )
            table_number = dining_table.number

        address = data.get("address") if delivery_type == DeliveryType.DELIVERY else None
        if delivery_type == DeliveryType.DELIVERY:
            OrderService._assert_delivery_area(settings=settings, address=address)
        address = OrderService._json_safe_address(address)

        delivery_fee = OrderService._calculate_delivery_fee(
            tenant=tenant,
            delivery_type=delivery_type,
            subtotal=subtotal,
        )
        total = round_money(subtotal + delivery_fee)

        payment_method = data.get("payment_method") or (
            PaymentMethod.PAY_AT_VENUE if delivery_type == DeliveryType.DINE_IN else None
        )
        change_for = data.get("change_for")
        if payment_method == PaymentMethod.CASH:
            if change_for is None:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"change_for": "Informe o valor para troco"})
            if Decimal(str(change_for)) <= total:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"change_for": "Troco deve ser maior que o total"})

        if delivery_type == DeliveryType.DINE_IN:
            # mesa: sem WhatsApp — convidado anônimo (ou conta logada, se tiver)
            display_name = (data.get("customer_name") or "").strip() or f"Mesa {table_number}"
            if authenticated_customer is not None:
                if authenticated_customer.tenant_id != tenant.id:
                    raise ValidationError(
                        {"customer_id": "Cliente não pertence a este estabelecimento"}
                    )
                customer = authenticated_customer
                if display_name and display_name != f"Mesa {table_number}":
                    # só atualiza o nome se a pessoa digitou algo
                    from apps.customers.domain.validators import split_customer_name

                    first, last = split_customer_name(display_name)
                    customer.first_name = first
                    customer.last_name = last
                    customer.save(update_fields=["first_name", "last_name", "updated_at"])
            else:
                customer = CustomerService.create_mesa_guest(
                    tenant=tenant,
                    table_number=table_number or "?",
                    name=display_name,
                )
            customer_name_snapshot = display_name
            customer_phone_snapshot = ""
        elif authenticated_customer is not None:
            if authenticated_customer.tenant_id != tenant.id:
                raise ValidationError({"customer_id": "Cliente não pertence a este estabelecimento"})
            customer = CustomerService.update_from_checkout(
                customer=authenticated_customer,
                name=data["customer_name"],
                phone=data["customer_phone"],
                email=data.get("customer_email"),
            )
            customer_name_snapshot = data["customer_name"].strip()
            customer_phone_snapshot = customer.phone
        else:
            customer = CustomerService.get_or_create_from_checkout(
                tenant=tenant,
                name=data["customer_name"],
                phone=data["customer_phone"],
                email=data.get("customer_email"),
            )
            customer_name_snapshot = data["customer_name"].strip()
            customer_phone_snapshot = customer.phone

        order_number = OrderService._generate_order_number(tenant)
        now = timezone.now()
        prep_delta = timedelta(minutes=settings.estimated_prep_time)
        delivery_delta = timedelta(minutes=settings.estimated_delivery_time)

        order = Order.objects.create(
            tenant=tenant,
            customer=customer,
            order_number=order_number,
            status=OrderStatus.PENDING,
            delivery_type=delivery_type,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            total=total,
            customer_name=customer_name_snapshot,
            customer_phone=customer_phone_snapshot,
            delivery_address=address,
            table=dining_table,
            table_number=table_number,
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
                    quantity=opt.get("quantity", 1),
                    option_id=opt.get("option_id"),
                )
            for comp in item_data.get("components") or []:
                OrderItemComponent.objects.create(
                    tenant=tenant,
                    order_item=order_item,
                    product_id=comp["product_id"],
                    product_name=comp["product_name"],
                    base_price=comp["base_price"],
                    sort_order=comp.get("sort_order", 0),
                )

        OptionStockService.decrement_for_order(validated_items=validated_items)

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

        # pedido chegou → "Pedido recebido" (order.received)
        transaction.on_commit(lambda o=order: _emit_order_communication(o))
        return order

    @staticmethod
    def get_public_order(*, tenant: Company, order_id) -> Order:
        return (
            Order.objects.filter(id=order_id, tenant=tenant)
            .prefetch_related("items__options", "items__components", "status_history", "payment")
            .get()
        )

    @staticmethod
    def get_admin_order(*, tenant: Company, order_id) -> Order:
        return (
            Order.objects.filter(id=order_id, tenant=tenant)
            .select_related("customer", "payment")
            .prefetch_related("items__options", "items__components", "status_history__changed_by")
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
        order = Order.all_objects.select_for_update().get(pk=order.pk)
        current = order.status

        allowed = VALID_TRANSITIONS.get(current, [])
        if new_status not in allowed:
            raise InvalidOrderTransition(current, new_status)

        # mesa/retirada não sai pra entrega
        if (
            new_status == OrderStatus.OUT_FOR_DELIVERY
            and order.delivery_type != DeliveryType.DELIVERY
        ):
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
        # WhatsApp etc. — fail soft dentro do motor
        transaction.on_commit(lambda o=order: _emit_order_communication(o))
        return order

    @staticmethod
    @transaction.atomic
    def update_payment(*, order: Order, status: str) -> Order:
        order = Order.all_objects.select_for_update().get(pk=order.pk)
        payment = order.payment

        if status != PaymentStatus.PAID:
            raise ValidationError({"status": "Status de pagamento inválido"})

        payment.status = PaymentStatus.PAID
        payment.paid_at = timezone.now()
        payment.save(update_fields=["status", "paid_at", "updated_at"])
        return order

    @staticmethod
    def _assert_channel_accepted(*, settings, delivery_type: str) -> None:
        if delivery_type == DeliveryType.DELIVERY and not settings.accepts_delivery:
            raise ValidationError({"delivery_type": "Este estabelecimento não aceita entrega"})
        if delivery_type == DeliveryType.PICKUP and not settings.accepts_pickup:
            raise ValidationError({"delivery_type": "Este estabelecimento não aceita retirada"})
        if delivery_type == DeliveryType.DINE_IN and not settings.accepts_dine_in:
            raise DineInNotAcceptedError()

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
        """Próximo #NNNN do tenant — max numérico, não o último created_at
        (seed com datas antigas quebrava a sequência)."""
        from django.db import connection

        # serializa geração por tenant (mesmo com tabela vazia, no Postgres)
        if connection.vendor == "postgresql":
            lock_key = (tenant.id.int % (2**31 - 1)) or 1
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_key])
        else:
            # SQLite (testes): trava o que existir; race vazia é ok em unit test
            list(
                Order.all_objects.select_for_update()
                .filter(tenant=tenant)
                .order_by("pk")[:1]
            )

        max_num = 0
        for raw in (
            Order.all_objects.filter(tenant=tenant)
            .values_list("order_number", flat=True)
            .iterator(chunk_size=500)
        ):
            try:
                max_num = max(max_num, int(str(raw).lstrip("#")))
            except (TypeError, ValueError):
                continue
        return f"#{max_num + 1:04d}"

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


def _emit_order_communication(order: Order) -> None:
    from apps.communications.services.engine import emit_order_status_event

    # recarrega com customer pra payload completo
    order = (
        Order.all_objects.select_related("customer", "tenant")
        .filter(pk=order.pk)
        .first()
        or order
    )
    emit_order_status_event(order=order)
