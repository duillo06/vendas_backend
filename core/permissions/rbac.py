from rest_framework.permissions import BasePermission

from apps.accounts.principal import EmployeePrincipal
from apps.accounts.services.auth_service import AuthService


class HasPermission(BasePermission):
    def __init__(self, permission: str):
        self.permission = permission

    def has_permission(self, request, view):
        principal = request.user
        if not isinstance(principal, EmployeePrincipal):
            return False
        return AuthService.employee_has_permission(principal.employee, self.permission)


def require_permission(permission: str) -> type[HasPermission]:
    class _Permission(HasPermission):
        def __init__(self):
            super().__init__(permission)

    _Permission.__name__ = f"Require{permission.replace('.', '_').title()}"
    return _Permission
