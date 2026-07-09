from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers.customer_auth_serializers import (
    CustomerLoginSerializer,
    CustomerLogoutSerializer,
    CustomerRefreshSerializer,
    CustomerRegisterSerializer,
)
from apps.accounts.services.customer_auth_service import CustomerAuthService
from core.tenancy.context import TenantContext


class CustomerAuthMixin:
    def get_tenant(self):
        tenant = TenantContext.get()
        if tenant is None:
            from django.http import Http404

            raise Http404("Estabelecimento não encontrado") from None
        return tenant


class CustomerRegisterView(CustomerAuthMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = CustomerAuthService.register(tenant=self.get_tenant(), **serializer.validated_data)
        return Response(result, status=status.HTTP_201_CREATED)


class CustomerLoginView(CustomerAuthMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomerLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = CustomerAuthService.login(tenant=self.get_tenant(), **serializer.validated_data)
        return Response(result, status=status.HTTP_200_OK)


class CustomerRefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomerRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = CustomerAuthService.refresh(refresh_token=serializer.validated_data["refresh"])
        return Response(result, status=status.HTTP_200_OK)


class CustomerLogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomerLogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        CustomerAuthService.logout(refresh_token=serializer.validated_data["refresh"])
        return Response(status=status.HTTP_204_NO_CONTENT)
