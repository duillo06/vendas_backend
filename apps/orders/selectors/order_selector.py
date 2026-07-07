from django.db.models import Count, Q

from apps.companies.models import Company
from apps.orders.domain.enums import OrderStatus
from apps.orders.models import Order


class OrderSelector:
    @staticmethod
    def list_orders(*, tenant: Company, params) -> tuple[list[Order], int]:
        qs = Order.all_objects.filter(tenant=tenant).annotate(items_count=Count("items"))

        if status := params.get("status"):
            statuses = [value.strip() for value in status.split(",") if value.strip()]
            if statuses:
                qs = qs.filter(status__in=statuses)

        if delivery_type := params.get("delivery_type"):
            qs = qs.filter(delivery_type=delivery_type)

        if created_after := params.get("created_after"):
            qs = qs.filter(created_at__date__gte=created_after)

        if created_before := params.get("created_before"):
            qs = qs.filter(created_at__date__lte=created_before)

        if search := params.get("search"):
            qs = qs.filter(
                Q(order_number__icontains=search)
                | Q(customer_name__icontains=search)
                | Q(customer_phone__icontains=search),
            )

        if params.get("active") in ("true", "1", "True"):
            qs = qs.exclude(status__in=[OrderStatus.COMPLETED, OrderStatus.CANCELLED])

        ordering = params.get("ordering") or "-created_at"
        allowed_ordering = {"created_at", "-created_at", "total", "-total"}
        if ordering not in allowed_ordering:
            ordering = "-created_at"

        return qs.order_by(ordering)
