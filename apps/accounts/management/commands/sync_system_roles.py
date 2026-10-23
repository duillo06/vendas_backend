from django.core.management.base import BaseCommand

from apps.accounts.services.role_service import RoleService
from apps.companies.models import Company


class Command(BaseCommand):
    help = "Sincroniza permissões dos roles de sistema (owner, manager…) em todos os tenants"

    def handle(self, *args, **options):
        count = 0
        for company in Company.objects.all():
            RoleService.create_system_roles(company)
            count += 1
            self.stdout.write(f"  ok · {company.subdomain}")
        self.stdout.write(self.style.SUCCESS(f"Roles sincronizados em {count} empresa(s)"))
