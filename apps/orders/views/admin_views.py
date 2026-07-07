from django.http import Http404
from rest_framework import status, viewsets
from rest_framework.response import Response

from apps.accounts.authentication import EmployeeJWTAuthentication
from apps.accounts.permissions import IsEmployeeAuthenticated
from apps.orders.models import Order
from apps.orders.selectors.order_selector import OrderSelector
from apps.orders.serializers.admin_serializers import (
    OrderDetailSerializer,
    OrderListSerializer,
    OrderPaymentUpdateSerializer,
    OrderStatusUpdateSerializer,
)
from apps.orders.services.order_service import OrderService
from core.exceptions.domain import DomainException
from core.pagination import StandardPagination
from core.permissions.rbac import HasPermission


class AdminOrderMixin:
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get_tenant(self):
        return self.request.user.employee.tenant


class AdminOrderViewSet(AdminOrderMixin, viewsets.ViewSet):
    def list(self, request):
        if not HasPermission("orders.view").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        qs = OrderSelector.list_orders(tenant=self.get_tenant(), params=request.query_params)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(OrderListSerializer(page, many=True).data)

    def retrieve(self, request, pk=None):
        if not HasPermission("orders.view").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            order = OrderService.get_admin_order(tenant=self.get_tenant(), order_id=pk)
        except Order.DoesNotExist as exc:
            raise Http404 from exc

        return Response(OrderDetailSerializer(order).data)

    def update_status(self, request, pk=None):
        can_manage = HasPermission("orders.manage").has_permission(request, self)
        can_update = HasPermission("orders.update_status").has_permission(request, self)
        if not (can_manage or can_update):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = OrderStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = OrderService.get_admin_order(tenant=self.get_tenant(), order_id=pk)
        except Order.DoesNotExist as exc:
            raise Http404 from exc

        try:
            order = OrderService.update_status(
                order=order,
                new_status=serializer.validated_data["status"],
                employee=request.user.employee,
                notes=serializer.validated_data.get("notes"),
            )
        except DomainException as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        order = OrderService.get_admin_order(tenant=self.get_tenant(), order_id=order.id)
        return Response(OrderDetailSerializer(order).data)

    def update_payment(self, request, pk=None):
        if not HasPermission("orders.manage").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = OrderPaymentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = OrderService.get_admin_order(tenant=self.get_tenant(), order_id=pk)
        except Order.DoesNotExist as exc:
            raise Http404 from exc

        try:
            order = OrderService.update_payment(
                order=order,
                status=serializer.validated_data["status"],
            )
        except Exception as exc:
            if hasattr(exc, "detail"):
                return Response(
                    {"error": {"code": "VALIDATION_ERROR", "message": str(exc.detail)}},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            raise

        order = OrderService.get_admin_order(tenant=self.get_tenant(), order_id=order.id)
        return Response(OrderDetailSerializer(order).data)
