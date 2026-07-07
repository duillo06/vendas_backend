from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from apps.accounts.models import Employee
from apps.accounts.principal import EmployeePrincipal
from apps.accounts.services.auth_service import AuthService


class EmployeeJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        principal, validated_token = result
        from core.tenancy.context import TenantContext

        TenantContext.set(principal.employee.tenant)
        request.tenant = principal.employee.tenant
        return principal, validated_token

    def get_user(self, validated_token):
        employee_id = validated_token.get("employee_id")
        if not employee_id:
            raise InvalidToken("Token sem employee_id")

        jti = str(validated_token.get("jti", ""))
        if AuthService._is_blacklisted(jti):
            raise InvalidToken("Token revogado")

        try:
            employee = Employee.all_objects.select_related("tenant").get(
                id=employee_id,
                is_active=True,
            )
        except Employee.DoesNotExist:
            raise InvalidToken("Funcionário não encontrado") from None

        return EmployeePrincipal(employee=employee)
