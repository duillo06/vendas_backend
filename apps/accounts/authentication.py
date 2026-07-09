from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from apps.accounts.models import Employee
from apps.accounts.principal import CustomerPrincipal, EmployeePrincipal
from apps.accounts.services.auth_service import AuthService
from apps.accounts.services.customer_auth_service import CustomerAuthService
from apps.customers.models import Customer


class EmployeeJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        principal, validated_token = result
        if not isinstance(principal, EmployeePrincipal):
            raise InvalidToken("Token inválido para funcionário")

        from core.tenancy.context import TenantContext

        TenantContext.set(principal.employee.tenant)
        request.tenant = principal.employee.tenant
        return principal, validated_token

    def get_user(self, validated_token):
        if validated_token.get("type") == "customer":
            raise InvalidToken("Token inválido para funcionário")

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


class CustomerJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        principal, validated_token = result
        if not isinstance(principal, CustomerPrincipal):
            raise InvalidToken("Token inválido para consumidor")

        from core.tenancy.context import TenantContext

        TenantContext.set(principal.customer.tenant)
        request.tenant = principal.customer.tenant
        return principal, validated_token

    def get_user(self, validated_token):
        if validated_token.get("type") != "customer":
            raise InvalidToken("Token inválido para consumidor")

        customer_id = validated_token.get("customer_id")
        if not customer_id:
            raise InvalidToken("Token sem customer_id")

        jti = str(validated_token.get("jti", ""))
        if CustomerAuthService._is_blacklisted(jti):
            raise InvalidToken("Token revogado")

        try:
            customer = Customer.all_objects.select_related("tenant").get(
                id=customer_id,
                is_active=True,
                deleted_at__isnull=True,
            )
        except Customer.DoesNotExist:
            raise InvalidToken("Cliente não encontrado") from None

        return CustomerPrincipal(customer=customer)
