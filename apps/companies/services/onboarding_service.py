from django.db import transaction

from apps.accounts.services.employee_service import EmployeeService
from apps.accounts.services.role_service import RoleService
from apps.companies.domain.validators import validate_subdomain
from apps.companies.models import BusinessHours, Company, CompanySettings
from apps.companies.services.business_hours_service import BusinessHoursService


class OnboardingService:
    @staticmethod
    @transaction.atomic
    def create_company(
        *,
        trade_name: str,
        subdomain: str,
        email: str,
        legal_name: str | None = None,
        phone: str | None = None,
        document: str | None = None,
        owner_email: str | None = None,
        owner_password: str | None = None,
        owner_first_name: str = "Dono",
        owner_last_name: str = "Loja",
    ) -> Company:
        validate_subdomain(subdomain)

        slug = subdomain
        company = Company.objects.create(
            subdomain=subdomain,
            slug=slug,
            legal_name=legal_name or trade_name,
            trade_name=trade_name,
            email=email,
            phone=phone,
            document=document,
        )

        # settings + 7 dias de horário
        CompanySettings.objects.create(
            tenant=company,
            setup={
                "status": "pending",
                "segment": None,
                "steps": [],
                "completed_at": None,
                "dismissed_at": None,
            },
        )
        BusinessHoursService.create_defaults(company)
        RoleService.create_system_roles(company)

        if owner_email and owner_password:
            EmployeeService.create_owner(
                company,
                email=owner_email,
                password=owner_password,
                first_name=owner_first_name,
                last_name=owner_last_name,
            )

        return company

    @staticmethod
    def setup_defaults(company: Company) -> None:
        # útil se criar company sem passar pelo create_company
        if not CompanySettings.all_objects.filter(tenant=company).exists():
            CompanySettings.objects.create(tenant=company)

        if BusinessHours.all_objects.filter(tenant=company).count() < 7:
            BusinessHoursService.create_defaults(company)
