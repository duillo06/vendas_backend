from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import EmailValidator
from django.db import models

from core.models.base import BaseModel
from core.models.tenant_model import TenantAwareModel


class Employee(TenantAwareModel):
    email = models.EmailField(max_length=254, validators=[EmailValidator()])
    password_hash = models.CharField(max_length=255)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_owner = models.BooleanField(default=False)
    last_login_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "employees"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "email"], name="uniq_employee_tenant_email"),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.email

    def set_password(self, raw_password: str) -> None:
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password_hash)

    @property
    def is_authenticated(self) -> bool:
        return True


class Role(TenantAwareModel):
    name = models.CharField(max_length=50)
    display_name = models.CharField(max_length=100)
    is_system = models.BooleanField(default=False)

    class Meta:
        db_table = "roles"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="uniq_role_tenant_name"),
        ]

    def __str__(self) -> str:
        return self.display_name


class RolePermission(BaseModel):
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="permissions",
    )
    permission = models.CharField(max_length=100)

    class Meta:
        db_table = "role_permissions"
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="uniq_role_permission"),
        ]


class EmployeeRole(BaseModel):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="employee_roles",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="employee_roles",
    )

    class Meta:
        db_table = "employee_roles"
        constraints = [
            models.UniqueConstraint(fields=["employee", "role"], name="uniq_employee_role"),
        ]
