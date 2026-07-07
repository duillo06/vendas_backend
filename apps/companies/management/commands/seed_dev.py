from django.core.management.base import BaseCommand

from apps.accounts.models import Employee
from apps.accounts.services.employee_service import EmployeeService
from apps.accounts.services.role_service import RoleService
from apps.companies.models import Company
from apps.companies.services.onboarding_service import OnboardingService


class Command(BaseCommand):
    help = "Cria o tenant demo pra desenvolvimento local"

    def handle(self, *args, **options):
        company = Company.objects.filter(subdomain="demo").first()

        if company is None:
            company = OnboardingService.create_company(
                trade_name="Lanchonete Demo",
                subdomain="demo",
                email="contato@demo.com",
                phone="(11) 99999-0000",
                owner_email="admin@demo.com",
                owner_password="demo1234",
                owner_first_name="Admin",
                owner_last_name="Demo",
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Tenant demo criado: {company.trade_name} ({company.subdomain})"
                )
            )
            return

        RoleService.create_system_roles(company)

        if not Employee.all_objects.filter(tenant=company, email="admin@demo.com").exists():
            EmployeeService.create_owner(
                company,
                email="admin@demo.com",
                password="demo1234",
                first_name="Admin",
                last_name="Demo",
            )
            self.stdout.write(self.style.SUCCESS("Owner admin@demo.com criado no tenant demo."))
            return

        self.stdout.write(self.style.WARNING("Tenant demo já existe, pulando."))
