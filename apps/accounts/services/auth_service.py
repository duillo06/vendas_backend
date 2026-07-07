from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.domain.constants import ALL_PERMISSIONS, TOKEN_BLACKLIST_PREFIX
from apps.accounts.models import Employee, RolePermission


class AuthService:
    @staticmethod
    def login(*, email: str, password: str, subdomain: str | None = None) -> dict:
        employees = Employee.all_objects.filter(email=email, is_active=True).select_related(
            "tenant"
        )

        if subdomain:
            employees = employees.filter(tenant__subdomain=subdomain)

        matches = list(employees)
        if not matches:
            raise AuthenticationFailed("Credenciais inválidas")

        if len(matches) > 1:
            raise AuthenticationFailed("Informe o subdomínio da loja para entrar.")

        employee = matches[0]

        if not employee.check_password(password):
            raise AuthenticationFailed("Credenciais inválidas")

        employee.last_login_at = timezone.now()
        employee.save(update_fields=["last_login_at", "updated_at"])

        refresh = AuthService._build_refresh_token(employee)
        permissions = AuthService.get_permissions(employee)

        from apps.accounts.serializers.employee_serializers import EmployeeSerializer
        from apps.companies.serializers.company_serializers import CompanyMinimalSerializer

        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": EmployeeSerializer(
                employee,
                context={"permissions": permissions},
            ).data,
            "tenant": CompanyMinimalSerializer(employee.tenant).data,
        }

    @staticmethod
    def refresh(*, refresh_token: str) -> dict:
        try:
            token = RefreshToken(refresh_token)
        except TokenError as exc:
            raise AuthenticationFailed("Refresh token inválido") from exc

        if AuthService._is_blacklisted(str(token.get("jti", ""))):
            raise AuthenticationFailed("Refresh token inválido")

        employee_id = token.get("employee_id")
        if not employee_id:
            raise AuthenticationFailed("Refresh token inválido")

        try:
            employee = Employee.all_objects.select_related("tenant").get(
                id=employee_id,
                is_active=True,
            )
        except Employee.DoesNotExist:
            raise AuthenticationFailed("Refresh token inválido") from None

        new_refresh = AuthService._build_refresh_token(employee)
        return {
            "access": str(new_refresh.access_token),
            "refresh": str(new_refresh),
        }

    @staticmethod
    def logout(*, refresh_token: str) -> None:
        try:
            token = RefreshToken(refresh_token)
        except TokenError as exc:
            raise AuthenticationFailed("Refresh token inválido") from exc

        jti = str(token.get("jti", ""))
        if not jti:
            return

        ttl = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
        cache.set(f"{TOKEN_BLACKLIST_PREFIX}{jti}", "1", timeout=ttl)

    @staticmethod
    def get_permissions(employee: Employee) -> list[str]:
        if employee.is_owner:
            return list(ALL_PERMISSIONS)

        return sorted(
            RolePermission.objects.filter(
                role__employee_roles__employee=employee,
            )
            .values_list("permission", flat=True)
            .distinct()
        )

    @staticmethod
    def employee_has_permission(employee: Employee, permission: str) -> bool:
        if employee.is_owner:
            return True
        return permission in AuthService.get_permissions(employee)

    @staticmethod
    def _build_refresh_token(employee: Employee) -> RefreshToken:
        refresh = RefreshToken()
        refresh["employee_id"] = str(employee.id)
        refresh["tenant_id"] = str(employee.tenant_id)
        return refresh

    @staticmethod
    def _is_blacklisted(jti: str) -> bool:
        if not jti:
            return False
        return cache.get(f"{TOKEN_BLACKLIST_PREFIX}{jti}") is not None
