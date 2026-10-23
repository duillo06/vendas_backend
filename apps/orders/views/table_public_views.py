from django.http import Http404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.domain.exceptions import TableInactiveError, TableNotFoundError
from apps.orders.services.table_service import TableService
from core.tenancy.context import TenantContext


def _table_payload(table) -> dict:
    return {
        "table_id": str(table.id),
        "table_number": table.number,
        "label": table.label or "",
        "is_active": table.is_active,
        "qr_token": table.qr_token,
    }


def _resolve_response(resolver):
    try:
        table = resolver()
    except TableNotFoundError as exc:
        return Response(
            {"error": {"code": exc.code, "message": exc.message}},
            status=status.HTTP_404_NOT_FOUND,
        )
    except TableInactiveError as exc:
        return Response(
            {"error": {"code": exc.code, "message": exc.message}},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return Response(_table_payload(table))


class PublicTableByTokenView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, qr_token: str):
        tenant = TenantContext.get()
        if tenant is None:
            raise Http404("Estabelecimento não encontrado") from None
        return _resolve_response(
            lambda: TableService.resolve_public(tenant=tenant, qr_token=qr_token)
        )


class PublicTableByNumberView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, number: str):
        tenant = TenantContext.get()
        if tenant is None:
            raise Http404("Estabelecimento não encontrado") from None
        return _resolve_response(
            lambda: TableService.resolve_by_number(tenant=tenant, number=number)
        )
