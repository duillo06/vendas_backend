from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import EmployeeJWTAuthentication
from apps.accounts.permissions import IsEmployeeAuthenticated
from apps.orders.domain.exceptions import TableNotFoundError
from apps.orders.serializers.table_serializers import (
    DiningTableBulkSerializer,
    DiningTablePatchSerializer,
    DiningTableWriteSerializer,
)
from apps.orders.services.table_service import TableService
from core.permissions.rbac import HasPermission


def _can_manage_tables(request, view) -> bool:
    return HasPermission("tables.manage").has_permission(request, view) or HasPermission(
        "settings.manage"
    ).has_permission(request, view)


class AdminTableViewSet(viewsets.ViewSet):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get_tenant(self):
        return self.request.user.employee.tenant

    def list(self, request):
        if not _can_manage_tables(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)
        tenant = self.get_tenant()
        tables = TableService.list_tables(tenant=tenant)
        return Response(
            [TableService.serialize(t, subdomain=tenant.subdomain) for t in tables]
        )

    def create(self, request):
        if not _can_manage_tables(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = DiningTableWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = self.get_tenant()
        try:
            table = TableService.create(tenant=tenant, **serializer.validated_data)
        except Exception as exc:
            if hasattr(exc, "detail"):
                return Response(
                    {"error": {"code": "VALIDATION_ERROR", "message": str(exc.detail)}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            raise
        return Response(
            TableService.serialize(table, subdomain=tenant.subdomain),
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, pk=None):
        if not _can_manage_tables(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = DiningTablePatchSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        tenant = self.get_tenant()
        try:
            table = TableService.get_for_tenant(tenant=tenant, table_id=pk)
            table = TableService.update(table=table, **serializer.validated_data)
        except TableNotFoundError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message}},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as exc:
            if hasattr(exc, "detail"):
                return Response(
                    {"error": {"code": "VALIDATION_ERROR", "message": str(exc.detail)}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            raise
        return Response(TableService.serialize(table, subdomain=tenant.subdomain))

    def destroy(self, request, pk=None):
        if not _can_manage_tables(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)
        tenant = self.get_tenant()
        try:
            table = TableService.get_for_tenant(tenant=tenant, table_id=pk)
            TableService.delete(table=table)
        except TableNotFoundError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminTableRegenerateQrView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def post(self, request, pk):
        if not _can_manage_tables(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)
        tenant = request.user.employee.tenant
        try:
            table = TableService.get_for_tenant(tenant=tenant, table_id=pk)
            table = TableService.regenerate_qr(table=table)
        except TableNotFoundError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(TableService.serialize(table, subdomain=tenant.subdomain))


class AdminTableQrView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get(self, request, pk):
        if not _can_manage_tables(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)
        tenant = request.user.employee.tenant
        try:
            table = TableService.get_for_tenant(tenant=tenant, table_id=pk)
        except TableNotFoundError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message}},
                status=status.HTTP_404_NOT_FOUND,
            )
        data = TableService.serialize(table, subdomain=tenant.subdomain)
        return Response(
            {
                "table_id": data["id"],
                "number": data["number"],
                "label": data["label"],
                "qr_token": data["qr_token"],
                "qr_url": data["qr_url"],
            }
        )


class AdminTableBulkView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def post(self, request):
        if not _can_manage_tables(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = DiningTableBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = request.user.employee.tenant
        try:
            tables = TableService.bulk_create(
                tenant=tenant,
                count=serializer.validated_data["count"],
                start=serializer.validated_data.get("start", 1),
            )
        except Exception as exc:
            if hasattr(exc, "detail"):
                return Response(
                    {"error": {"code": "VALIDATION_ERROR", "message": str(exc.detail)}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            raise
        return Response(
            [TableService.serialize(t, subdomain=tenant.subdomain) for t in tables],
            status=status.HTTP_201_CREATED,
        )
