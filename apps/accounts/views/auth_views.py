from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import EmployeeJWTAuthentication
from apps.accounts.permissions import IsEmployeeAuthenticated
from apps.accounts.principal import EmployeePrincipal
from apps.accounts.serializers.employee_serializers import (
    ChangePasswordSerializer,
    EmployeeSerializer,
    LoginSerializer,
    LogoutSerializer,
    RefreshSerializer,
)
from apps.accounts.services.auth_service import AuthService
from core.throttling import AuthLoginThrottle


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthLoginThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subdomain = serializer.validated_data.get("subdomain") or None
        if subdomain == "":
            subdomain = None

        result = AuthService.login(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            subdomain=subdomain,
        )
        return Response(result, status=status.HTTP_200_OK)


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = AuthService.refresh(refresh_token=serializer.validated_data["refresh"])
        return Response(result, status=status.HTTP_200_OK)


class LogoutView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        access_jti = None
        if request.auth is not None:
            access_jti = str(request.auth.get("jti", "") or "") or None

        AuthService.logout(
            refresh_token=serializer.validated_data["refresh"],
            access_jti=access_jti,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def get(self, request):
        principal: EmployeePrincipal = request.user
        employee = principal.employee
        permissions = AuthService.get_permissions(employee)

        from apps.companies.serializers.company_serializers import CompanyMinimalSerializer

        return Response(
            {
                "user": EmployeeSerializer(
                    employee,
                    context={"permissions": permissions},
                ).data,
                "tenant": CompanyMinimalSerializer(employee.tenant).data,
            }
        )


class ChangePasswordView(APIView):
    authentication_classes = [EmployeeJWTAuthentication]
    permission_classes = [IsEmployeeAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        principal: EmployeePrincipal = request.user
        AuthService.change_password(
            employee=principal.employee,
            current_password=serializer.validated_data["current_password"],
            new_password=serializer.validated_data["new_password"],
        )
        return Response({"detail": "Senha atualizada"}, status=status.HTTP_200_OK)
