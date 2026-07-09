from django.db.models import Q

from apps.companies.models import Company
from apps.customers.models import Customer


class CustomerSelector:
    @staticmethod
    def list_customers(*, tenant: Company, params: dict | None = None):
        params = params or {}
        qs = Customer.all_objects.filter(tenant=tenant, deleted_at__isnull=True)

        if search := params.get("search"):
            qs = qs.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(email__icontains=search),
            )

        ordering = params.get("ordering") or "-last_order_at"
        allowed = {"last_order_at", "-last_order_at", "total_orders", "-total_orders", "created_at", "-created_at"}
        if ordering not in allowed:
            ordering = "-last_order_at"

        return qs.order_by(ordering)

    @staticmethod
    def get_customer(*, tenant: Company, customer_id) -> Customer:
        return Customer.all_objects.select_related("tenant").prefetch_related("addresses").get(
            tenant=tenant,
            id=customer_id,
            deleted_at__isnull=True,
        )
