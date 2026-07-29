from django.core.management.base import BaseCommand, CommandError

from apps.locations.models import City, State
from apps.locations.services import LocationCatalogService


class Command(BaseCommand):
    help = "Carrega estados e cidades pela API oficial do IBGE"

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="Consulta o IBGE apenas se o catálogo estiver vazio",
        )

    def handle(self, *args, **options):
        if options["if_empty"] and State.objects.exists() and City.objects.exists():
            self.stdout.write("Catálogo de localidades já carregado.")
            return

        self.stdout.write("Consultando estados e cidades no IBGE...")
        try:
            state_count, city_count = LocationCatalogService.sync_from_ibge()
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Catálogo carregado: {state_count} estados e {city_count} cidades."
            )
        )
