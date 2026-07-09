from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import CustomerJWTAuthentication
from apps.accounts.permissions import IsCustomerAuthenticated
from apps.accounts.principal import CustomerPrincipal
from apps.customers.models import CustomerAddress
from apps.customers.serializers.customer_serializers import (
    CustomerAddressSerializer,
    CustomerAddressWriteSerializer,
    CustomerSerializer,
)
from apps.customers.services.customer_address_service import CustomerAddressService
from apps.orders.models import Order
from apps.orders.serializers.public_serializers import OrderPublicSerializer
from core.pagination import StandardPagination
from core.tenancy.context import TenantContext


class AccountMixin:
    authentication_classes = [CustomerJWTAuthentication]
    permission_classes = [IsCustomerAuthenticated]

    def get_customer(self, request):
        principal: CustomerPrincipal = request.user
        return principal.customer

    def get_tenant(self):
        tenant = TenantContext.get()
        if tenant is None:
            raise Http404("Estabelecimento não encontrado") from None
        return tenant


class AccountMeView(AccountMixin, APIView):
    def get(self, request):
        customer = self.get_customer(request)
        from apps.companies.serializers.company_serializers import CompanyMinimalSerializer

        return Response(
            {
                "customer": CustomerSerializer(customer).data,
                "tenant": CompanyMinimalSerializer(self.get_tenant()).data,
            },
        )


class AccountOrderListView(AccountMixin, APIView):
    def get(self, request):
        customer = self.get_customer(request)
        tenant = self.get_tenant()

        qs = (
            Order.objects.filter(tenant=tenant, customer=customer)
            .select_related("payment")
            .prefetch_related("items", "items__options", "status_history")
            .order_by("-created_at")
        )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        data = OrderPublicSerializer(page, many=True).data
        return paginator.get_paginated_response(data)


class AccountOrderDetailView(AccountMixin, APIView):
    def get(self, request, order_id):
        customer = self.get_customer(request)
        tenant = self.get_tenant()

        try:
            order = (
                Order.objects.filter(tenant=tenant, customer=customer, id=order_id)
                .select_related("payment")
                .prefetch_related("items", "items__options", "status_history")
                .get()
            )
        except Order.DoesNotExist:
            raise Http404("Pedido não encontrado") from None

        return Response(OrderPublicSerializer(order).data)


class AccountAddressListView(AccountMixin, APIView):
    def get(self, request):
        customer = self.get_customer(request)
        addresses = CustomerAddressService.list_for_customer(customer=customer)
        return Response(CustomerAddressSerializer(addresses, many=True).data)

    def post(self, request):
        customer = self.get_customer(request)
        tenant = self.get_tenant()
        serializer = CustomerAddressWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        address = CustomerAddressService.create(
            tenant=tenant,
            customer=customer,
            data=serializer.validated_data,
        )
        return Response(CustomerAddressSerializer(address).data, status=status.HTTP_201_CREATED)


class AccountAddressDetailView(AccountMixin, APIView):
    def _get_address(self, customer, address_id):
        try:
            return CustomerAddress.objects.get(customer=customer, id=address_id)
        except CustomerAddress.DoesNotExist:
            raise Http404("Endereço não encontrado") from None

    def patch(self, request, address_id):
        customer = self.get_customer(request)
        address = self._get_address(customer, address_id)
        serializer = CustomerAddressWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        address = CustomerAddressService.update(address=address, data=serializer.validated_data)
        return Response(CustomerAddressSerializer(address).data)

    def delete(self, request, address_id):
        customer = self.get_customer(request)
        address = self._get_address(customer, address_id)
        CustomerAddressService.delete(address=address)
        return Response(status=status.HTTP_204_NO_CONTENT)
