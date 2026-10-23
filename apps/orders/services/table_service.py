import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.companies.models import Company
from apps.orders.domain.exceptions import TableInactiveError, TableNotFoundError
from apps.orders.models import DiningTable


def _new_qr_token() -> str:
    # token opaco — não é o número da mesa
    return secrets.token_urlsafe(24)


def build_mesa_qr_url(*, subdomain: str, token: str) -> str:
    template = settings.STOREFRONT_MESA_URL_TEMPLATE
    return template.format(
        subdomain=subdomain,
        token=token,
        domain=settings.STOREFRONT_BASE_DOMAIN,
    )


class TableService:
    @staticmethod
    def serialize(table: DiningTable, *, subdomain: str | None = None) -> dict:
        sub = subdomain or table.tenant.subdomain
        return {
            "id": str(table.id),
            "number": table.number,
            "label": table.label or "",
            "capacity": table.capacity,
            "is_active": table.is_active,
            "qr_token": table.qr_token,
            "qr_url": build_mesa_qr_url(subdomain=sub, token=table.qr_token),
            "sort_order": table.sort_order,
            "created_at": table.created_at.isoformat().replace("+00:00", "Z"),
        }

    @staticmethod
    def list_tables(*, tenant: Company) -> list[DiningTable]:
        return list(
            DiningTable.all_objects.filter(tenant=tenant).order_by("sort_order", "number")
        )

    @staticmethod
    def get_for_tenant(*, tenant: Company, table_id) -> DiningTable:
        try:
            return DiningTable.all_objects.get(id=table_id, tenant=tenant)
        except DiningTable.DoesNotExist as exc:
            raise TableNotFoundError() from exc

    @staticmethod
    def resolve_public(*, tenant: Company, qr_token: str) -> DiningTable:
        try:
            table = DiningTable.all_objects.get(tenant=tenant, qr_token=qr_token)
        except DiningTable.DoesNotExist as exc:
            raise TableNotFoundError() from exc
        if not table.is_active:
            raise TableInactiveError()
        return table

    @staticmethod
    def resolve_by_number(*, tenant: Company, number: str) -> DiningTable:
        number = (number or "").strip()
        if not number:
            raise TableNotFoundError()
        try:
            table = DiningTable.all_objects.get(tenant=tenant, number=number)
        except DiningTable.DoesNotExist as exc:
            raise TableNotFoundError() from exc
        if not table.is_active:
            raise TableInactiveError()
        return table

    @staticmethod
    def resolve_for_checkout(
        *,
        tenant: Company,
        table_id=None,
        qr_token: str | None = None,
    ) -> DiningTable:
        if qr_token:
            return TableService.resolve_public(tenant=tenant, qr_token=qr_token)
        if table_id:
            table = TableService.get_for_tenant(tenant=tenant, table_id=table_id)
            if not table.is_active:
                raise TableInactiveError()
            return table
        raise TableNotFoundError()

    @staticmethod
    @transaction.atomic
    def create(
        *,
        tenant: Company,
        number: str,
        label: str = "",
        capacity: int | None = None,
        is_active: bool = True,
        sort_order: int | None = None,
    ) -> DiningTable:
        number = number.strip()
        if not number:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"number": "Informe o número da mesa"})

        if DiningTable.all_objects.filter(tenant=tenant, number=number).exists():
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"number": "Já existe uma mesa com esse número"})

        if sort_order is None:
            sort_order = TableService._next_sort(tenant)

        now = timezone.now()
        return DiningTable.all_objects.create(
            tenant=tenant,
            number=number,
            label=(label or "").strip(),
            capacity=capacity,
            is_active=is_active,
            qr_token=_new_qr_token(),
            qr_generated_at=now,
            sort_order=sort_order,
        )

    @staticmethod
    @transaction.atomic
    def bulk_create(*, tenant: Company, count: int, start: int = 1) -> list[DiningTable]:
        if count < 1 or count > 100:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"count": "Informe entre 1 e 100 mesas"})

        created: list[DiningTable] = []
        n = start
        while len(created) < count:
            number = str(n)
            n += 1
            if DiningTable.all_objects.filter(tenant=tenant, number=number).exists():
                continue
            created.append(
                TableService.create(
                    tenant=tenant,
                    number=number,
                    sort_order=TableService._next_sort(tenant),
                )
            )
        return created

    @staticmethod
    @transaction.atomic
    def update(*, table: DiningTable, **fields) -> DiningTable:
        allowed = {"number", "label", "capacity", "is_active", "sort_order"}
        if "number" in fields and fields["number"] is not None:
            number = str(fields["number"]).strip()
            if not number:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"number": "Informe o número da mesa"})
            clash = (
                DiningTable.all_objects.filter(tenant=table.tenant, number=number)
                .exclude(pk=table.pk)
                .exists()
            )
            if clash:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"number": "Já existe uma mesa com esse número"})
            fields["number"] = number

        for key, value in fields.items():
            if key not in allowed:
                continue
            if key == "label" and value is not None:
                value = str(value).strip()
            setattr(table, key, value)

        table.save()
        return table

    @staticmethod
    @transaction.atomic
    def regenerate_qr(*, table: DiningTable) -> DiningTable:
        table.qr_token = _new_qr_token()
        table.qr_generated_at = timezone.now()
        table.save(update_fields=["qr_token", "qr_generated_at", "updated_at"])
        return table

    @staticmethod
    @transaction.atomic
    def delete(*, table: DiningTable) -> None:
        # se já teve pedido, só desativa (histórico fica)
        has_orders = table.orders.exists()
        if has_orders:
            table.is_active = False
            table.save(update_fields=["is_active", "updated_at"])
            return
        table.delete()

    @staticmethod
    def count_active(*, tenant: Company) -> int:
        return DiningTable.all_objects.filter(tenant=tenant, is_active=True).count()

    @staticmethod
    def _next_sort(tenant: Company) -> int:
        last = (
            DiningTable.all_objects.filter(tenant=tenant)
            .order_by("-sort_order")
            .values_list("sort_order", flat=True)
            .first()
        )
        return (last or 0) + 1
