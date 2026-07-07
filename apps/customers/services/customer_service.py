from django.utils import timezone

from apps.customers.domain.validators import normalize_phone, split_customer_name
from apps.customers.models import Customer
from apps.companies.models import Company


class CustomerService:
    @staticmethod
    def get_or_create_from_checkout(
        *,
        tenant: Company,
        name: str,
        phone: str,
        email: str | None = None,
    ) -> Customer:
        normalized_phone = normalize_phone(phone)
        first_name, last_name = split_customer_name(name)

        customer, created = Customer.all_objects.get_or_create(
            tenant=tenant,
            phone=normalized_phone,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "email": email or None,
            },
        )

        if not created:
            customer.first_name = first_name
            customer.last_name = last_name
            if email:
                customer.email = email
            customer.deleted_at = None
            customer.is_active = True
            customer.save(
                update_fields=["first_name", "last_name", "email", "deleted_at", "is_active", "updated_at"]
            )

        return customer

    @staticmethod
    def record_order(*, customer: Customer, total) -> None:
        customer.total_orders += 1
        customer.total_spent += total
        customer.last_order_at = timezone.now()
        customer.save(update_fields=["total_orders", "total_spent", "last_order_at", "updated_at"])
