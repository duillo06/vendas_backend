from django.core.management.base import BaseCommand

from apps.catalog.services.seed_catalog import seed_demo_catalog
from apps.companies.models import Company
from apps.companies.services.onboarding_service import OnboardingService


class Command(BaseCommand):
    help = "Cria um tenant real para go-live (onboarding de cliente)"

    def add_arguments(self, parser):
        parser.add_argument("--trade-name", required=True, help="Nome fantasia da loja")
        parser.add_argument("--subdomain", required=True, help="Subdomínio (ex: pizzaria-joao)")
        parser.add_argument("--email", required=True, help="E-mail de contato da empresa")
        parser.add_argument("--phone", default="", help="Telefone de contato")
        parser.add_argument(
            "--owner-email",
            required=True,
            help="E-mail do dono (login no backoffice)",
        )
        parser.add_argument(
            "--owner-password",
            required=True,
            help="Senha inicial do dono",
        )
        parser.add_argument(
            "--owner-first-name",
            default="Dono",
            help="Primeiro nome do dono",
        )
        parser.add_argument(
            "--owner-last-name",
            default="Loja",
            help="Sobrenome do dono",
        )
        parser.add_argument(
            "--seed-catalog",
            action="store_true",
            help="Popula cardápio demo (útil para staging)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Permite recriar seed de catálogo se o tenant já existir",
        )

    def handle(self, *args, **options):
        subdomain = options["subdomain"].strip().lower()
        created = False

        company = Company.objects.filter(subdomain=subdomain).first()
        if company:
            self.stdout.write(
                self.style.WARNING(
                    f"Tenant '{subdomain}' já existe ({company.trade_name}). "
                    "Nenhuma alteração de cadastro foi feita."
                )
            )
        else:
            created = True
            company = OnboardingService.create_company(
                trade_name=options["trade_name"],
                subdomain=subdomain,
                email=options["email"],
                phone=options["phone"] or None,
                owner_email=options["owner_email"],
                owner_password=options["owner_password"],
                owner_first_name=options["owner_first_name"],
                owner_last_name=options["owner_last_name"],
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Tenant criado: {company.trade_name} → https://{subdomain}.foodservice.app"
                )
            )

        if options["seed_catalog"]:
            seed_demo_catalog(company)
            self.stdout.write(self.style.SUCCESS("Cardápio demo aplicado ao tenant."))
        elif created:
            self.stdout.write(
                "Cadastre categorias, produtos e opções pelo backoffice antes do go-live."
            )

        self.stdout.write("")
        self.stdout.write("Credenciais do dono:")
        self.stdout.write("  Backoffice: https://admin.foodservice.app")
        self.stdout.write(f"  Subdomínio: {subdomain}")
        self.stdout.write(f"  E-mail:     {options['owner_email']}")
        self.stdout.write("  Senha:      (informada no comando)")
        self.stdout.write("")
        self.stdout.write(f"Storefront: https://{subdomain}.foodservice.app")
