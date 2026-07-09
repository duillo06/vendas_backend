from dataclasses import dataclass

from apps.accounts.models import Employee
from apps.customers.models import Customer


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


@dataclass
class CustomerPrincipal:
    """Envelope pro DRF — request.user.customer"""

    customer: Customer

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def pk(self):
        return self.customer.pk

    def __str__(self) -> str:
        return self.customer.full_name or self.customer.phone
