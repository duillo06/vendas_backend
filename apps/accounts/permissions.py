from rest_framework.permissions import BasePermission

from apps.accounts.principal import CustomerPrincipal, EmployeePrincipal


class IsEmployeeAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.user, EmployeePrincipal)


class IsCustomerAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.user, CustomerPrincipal)
