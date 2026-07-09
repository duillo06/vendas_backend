from django.db import transaction

from apps.companies.models import Company
from apps.customers.models import Customer, CustomerAddress


class CustomerAddressService:
    @staticmethod
    def list_for_customer(*, customer: Customer) -> list[CustomerAddress]:
        return list(
            CustomerAddress.objects.filter(customer=customer).order_by("-is_default", "-created_at"),
        )

    @staticmethod
    @transaction.atomic
    def create(*, tenant: Company, customer: Customer, data: dict) -> CustomerAddress:
        is_default = data.get("is_default", False)
        has_addresses = CustomerAddress.objects.filter(customer=customer).exists()

        if has_addresses and is_default:
            CustomerAddress.objects.filter(customer=customer, is_default=True).update(is_default=False)
        elif not has_addresses:
            is_default = True

        return CustomerAddress.objects.create(
            tenant=tenant,
            customer=customer,
            label=data.get("label") or "",
            street=data["street"],
            number=data["number"],
            complement=data.get("complement") or "",
            neighborhood=data["neighborhood"],
            city=data["city"],
            state=data["state"],
            zip_code=data["zip_code"],
            reference=data.get("reference") or "",
            is_default=is_default,
        )

    @staticmethod
    @transaction.atomic
    def update(*, address: CustomerAddress, data: dict) -> CustomerAddress:
        for field in (
            "label",
            "street",
            "number",
            "complement",
            "neighborhood",
            "city",
            "state",
            "zip_code",
            "reference",
        ):
            if field in data:
                setattr(address, field, data[field] or "")

        if data.get("is_default") is True:
            CustomerAddress.objects.filter(customer=address.customer, is_default=True).exclude(
                pk=address.pk,
            ).update(is_default=False)
            address.is_default = True

        address.save()
        return address

    @staticmethod
    def delete(*, address: CustomerAddress) -> None:
        was_default = address.is_default
        customer = address.customer
        address.delete()

        if was_default:
            next_address = CustomerAddress.objects.filter(customer=customer).first()
            if next_address:
                next_address.is_default = True
                next_address.save(update_fields=["is_default", "updated_at"])
