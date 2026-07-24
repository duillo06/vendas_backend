from django.core.management.base import BaseCommand

from apps.catalog.services.seed_demo_pizzaria import seed_demo_pizzaria
from apps.companies.models import Company
from apps.companies.services.onboarding_service import OnboardingService


class Command(BaseCommand):
    help = "Enche o tenant com cardápio de pizzaria (pizzas + bebidas) + fotos"

    def add_arguments(self, parser):
        parser.add_argument(
            "--subdomain",
            default="demo",
            help="Subdomínio do tenant (padrão: demo)",
        )
        parser.add_argument(
            "--skip-images",
            action="store_true",
            help="Só cria categorias/produtos, sem baixar fotos",
        )

    def handle(self, *args, **options):
        subdomain = options["subdomain"]
        company = Company.objects.filter(subdomain=subdomain).first()

        if company is None:
            self.stdout.write(f"Tenant '{subdomain}' não existe — criando…")
            company = OnboardingService.create_company(
                trade_name="Pizzaria Demo",
                subdomain=subdomain,
                email="contato@pizzaria.com",
                phone="(11) 98888-0000",
                owner_email="admin@demo.com",
                owner_password="demo1234",
                owner_first_name="Admin",
                owner_last_name="Demo",
            )
        else:
            # alinhando o nome se ainda for o tenant genérico
            if company.trade_name in {"Lanchonete Demo", "Demo"}:
                company.trade_name = "Pizzaria Demo"
                company.save(update_fields=["trade_name", "updated_at"])

        self.stdout.write(
            self.style.NOTICE(f"Seed pizzaria em {company.trade_name} ({subdomain})…")
        )
        if not options["skip_images"]:
            self.stdout.write("Baixando fotos da internet (pode levar 1–2 min)…")

        stats = seed_demo_pizzaria(
            company,
            skip_images=options["skip_images"],
            log=lambda msg: self.stdout.write(msg),
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Ok — {stats['categories']} categorias, "
                f"{stats['products']} produtos, {stats['images']} fotos novas. "
                f"Login: admin@demo.com / demo1234"
            )
        )
