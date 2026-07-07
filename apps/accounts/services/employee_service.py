from django.core.exceptions import ValidationError

from apps.accounts.models import Employee, EmployeeRole, Role


class EmployeeService:
    @staticmethod
    def create_owner(
        company,
        *,
        email: str,
        password: str,
        first_name: str = "Dono",
        last_name: str = "Loja",
    ) -> Employee:
        if len(password) < 8:
            raise ValidationError("Senha precisa ter pelo menos 8 caracteres.")

        employee = Employee(
            tenant=company,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_owner=True,
            is_active=True,
        )
        employee.set_password(password)
        employee.save()

        owner_role = Role.all_objects.get(tenant=company, name="owner")
        EmployeeRole.objects.get_or_create(employee=employee, role=owner_role)

        return employee
