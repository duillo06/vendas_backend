import json
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.locations.models import City, State

IBGE_BASE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades"
IBGE_USER_AGENT = "FoodService/1.0"
IBGE_TIMEOUT_SECONDS = 30


def normalize_location_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", (value or "").strip().lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.split())


class LocationCatalogService:
    @staticmethod
    def list_states():
        return State.objects.all().order_by("name")

    @staticmethod
    def list_cities(*, state_id: int | None = None, state_acronym: str = ""):
        cities = City.objects.select_related("state")
        if state_id is not None:
            return cities.filter(state_id=state_id).order_by("name")
        if state_acronym:
            return cities.filter(state__acronym=state_acronym.strip().upper()).order_by("name")
        return cities.none()

    @staticmethod
    def get_city(*, city_id: int, state_id: int | None = None) -> City:
        try:
            city = City.objects.select_related("state").get(id=city_id)
        except City.DoesNotExist:
            raise ValidationError("Escolha uma cidade válida") from None

        if state_id is not None and city.state_id != state_id:
            raise ValidationError("A cidade não pertence ao estado escolhido")
        return city

    @staticmethod
    def find_city(*, city_name: str, state_acronym: str) -> City | None:
        return (
            City.objects.select_related("state")
            .filter(
                state__acronym=state_acronym.strip().upper(),
                normalized_name=normalize_location_name(city_name),
            )
            .first()
        )

    @staticmethod
    def _fetch(path: str) -> list[dict]:
        request = Request(
            f"{IBGE_BASE_URL}/{path}",
            headers={"User-Agent": IBGE_USER_AGENT, "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=IBGE_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise ValidationError(f"Não foi possível consultar o IBGE: {exc}") from exc

    @staticmethod
    def _backfill_references(cities: list[City]) -> None:
        # liga os textos antigos ao catálogo depois do primeiro seed
        from apps.companies.models import CompanySettings
        from apps.customers.models import CustomerAddress

        city_by_name = {
            (city.state.acronym, city.normalized_name): city
            for city in City.objects.select_related("state").filter(id__in=[row.id for row in cities])
        }

        settings_to_update = []
        for settings in CompanySettings.all_objects.filter(
            delivery_city_ref__isnull=True,
        ).exclude(delivery_city=""):
            city = city_by_name.get(
                (
                    settings.delivery_state.strip().upper(),
                    normalize_location_name(settings.delivery_city),
                )
            )
            if city:
                settings.delivery_city_ref = city
                settings.delivery_city = city.name
                settings.delivery_state = city.state.acronym
                settings_to_update.append(settings)
        if settings_to_update:
            CompanySettings.all_objects.bulk_update(
                settings_to_update,
                ["delivery_city_ref", "delivery_city", "delivery_state"],
            )

        addresses_to_update = []
        for address in CustomerAddress.all_objects.filter(city_ref__isnull=True):
            city = city_by_name.get(
                (
                    address.state.strip().upper(),
                    normalize_location_name(address.city),
                )
            )
            if city:
                address.city_ref = city
                address.city = city.name
                address.state = city.state.acronym
                addresses_to_update.append(address)
        if addresses_to_update:
            CustomerAddress.all_objects.bulk_update(
                addresses_to_update,
                ["city_ref", "city", "state"],
            )

    @staticmethod
    def sync_from_ibge() -> tuple[int, int]:
        states_payload = LocationCatalogService._fetch("estados?orderBy=nome")
        states = [
            State(
                id=int(item["id"]),
                name=item["nome"].strip(),
                acronym=item["sigla"].strip().upper(),
            )
            for item in states_payload
        ]
        cities: list[City] = []
        for state in states:
            payload = LocationCatalogService._fetch(
                f"estados/{state.id}/municipios?orderBy=nome"
            )
            cities.extend(
                City(
                    id=int(item["id"]),
                    state_id=state.id,
                    name=item["nome"].strip(),
                    normalized_name=normalize_location_name(item["nome"]),
                )
                for item in payload
            )

        # só abre transação depois de terminar as consultas externas
        with transaction.atomic():
            State.objects.bulk_create(
                states,
                update_conflicts=True,
                update_fields=["name", "acronym"],
                unique_fields=["id"],
            )
            City.objects.bulk_create(
                cities,
                update_conflicts=True,
                update_fields=["state", "name", "normalized_name"],
                unique_fields=["id"],
            )
            LocationCatalogService._backfill_references(cities)
        return len(states), len(cities)
