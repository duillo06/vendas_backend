from django.db import transaction
from django.http import Http404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.orders.serializers.public_serializers import CheckoutSerializer, OrderPublicSerializer
from apps.orders.services.order_service import OrderService
from apps.orders.tasks import send_order_confirmation_email
from core.tenancy.context import TenantContext


class PublicOrderMixin:
    def get_tenant(self):
        tenant = TenantContext.get()
        if tenant is None:
            raise Http404("Estabelecimento não encontrado") from None
        return tenant


class CheckoutView(PublicOrderMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant = self.get_tenant()
        order = OrderService.create_from_checkout(tenant=tenant, data=serializer.validated_data)
        transaction.on_commit(lambda: send_order_confirmation_email.delay(str(order.id)))
        return Response(OrderPublicSerializer(order).data, status=status.HTTP_201_CREATED)


class PublicOrderDetailView(PublicOrderMixin, APIView):
    permission_classes = [AllowAny]

    def get(self, request, order_id):
        tenant = self.get_tenant()
        try:
            order = OrderService.get_public_order(tenant=tenant, order_id=order_id)
        except Order.DoesNotExist:
            raise Http404("Pedido não encontrado") from None

        return Response(OrderPublicSerializer(order).data)
