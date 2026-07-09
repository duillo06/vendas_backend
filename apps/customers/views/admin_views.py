from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import EmployeeJWTAuthentication
from apps.accounts.permissions import IsEmployeeAuthenticated
from apps.customers.models import Customer
from apps.customers.selectors.customer_selector import CustomerSelector
from apps.customers.serializers.customer_serializers import (
    CustomerAdminDetailSerializer,
    CustomerAdminListSerializer,
)
from apps.orders.models import Order
from core.pagination import StandardPagination
from core.permissions.rbac import HasPermission


class AdminCustomerMixin:
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get_tenant(self):
        return self.request.user.employee.tenant


class AdminCustomerListView(AdminCustomerMixin, APIView):
    def get(self, request):
        if not HasPermission("customers.view").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        qs = CustomerSelector.list_customers(
            tenant=self.get_tenant(),
            params=request.query_params.dict(),
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        data = CustomerAdminListSerializer(page, many=True).data
        return paginator.get_paginated_response(data)


class AdminCustomerDetailView(AdminCustomerMixin, APIView):
    def get(self, request, customer_id):
        if not HasPermission("customers.view").has_permission(request, self):
            return Response(status=status.HTTP_403_FORBIDDEN)

        tenant = self.get_tenant()
        try:
            customer = CustomerSelector.get_customer(tenant=tenant, customer_id=customer_id)
        except Customer.DoesNotExist:
            raise Http404("Cliente não encontrado") from None

        customer.recent_orders_list = list(
            Order.objects.filter(tenant=tenant, customer=customer)
            .order_by("-created_at")[:10],
        )
        return Response(CustomerAdminDetailSerializer(customer).data)
