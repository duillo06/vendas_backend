from dataclasses import dataclass

from apps.accounts.models import Employee


@dataclass
class EmployeePrincipal:
    """Envelope pro DRF — request.user.employee"""

    employee: Employee

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def pk(self):
        return self.employee.pk

    def __str__(self) -> str:
        return self.employee.email
