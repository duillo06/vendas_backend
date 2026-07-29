import pytest

from apps.companies.services.onboarding_service import OnboardingService
from apps.companies.services.settings_service import SettingsService
from apps.locations.models import City, State
from apps.locations.services import LocationCatalogService


@pytest.fixture
def sao_paulo(db):
    state = State.objects.create(id=35, name="São Paulo", acronym="SP")
    city = City.objects.create(
        id=3550308,
        state=state,
        name="São Paulo",
        normalized_name="sao paulo",
    )
    return state, city


@pytest.mark.django_db
def test_public_locations_filter_cities_by_state(api_client, sao_paulo):
    state, city = sao_paulo

    states_response = api_client.get("/api/v1/public/locations/states/")
    cities_response = api_client.get(
        "/api/v1/public/locations/cities/",
        {"state_id": state.id},
    )

    assert states_response.status_code == 200
    assert states_response.json() == [
        {"id": state.id, "name": "São Paulo", "acronym": "SP"}
    ]
    assert cities_response.status_code == 200
    assert cities_response.json() == [
        {
            "id": city.id,
            "name": "São Paulo",
            "state_id": state.id,
            "state": "SP",
        }
    ]


@pytest.mark.django_db
def test_settings_uses_canonical_city_name_and_state(sao_paulo):
    state, city = sao_paulo
    company = OnboardingService.create_company(
        trade_name="Lanchonete Demo",
        subdomain="demo-localidades",
        email="contato@demo.com",
        owner_email="admin@demo.com",
        owner_password="demo1234",
    )

    settings = SettingsService.update(
        company,
        delivery_city_id=city.id,
        delivery_state_id=state.id,
        delivery_city="nome digitado errado",
        delivery_state="XX",
    )

    assert settings.delivery_city_ref_id == city.id
    assert settings.delivery_city == city.name
    assert settings.delivery_state == state.acronym


@pytest.mark.django_db
def test_sync_from_ibge_upserts_official_catalog(monkeypatch):
    def fake_fetch(path):
        if path.startswith("estados?"):
            return [{"id": 35, "nome": "São Paulo", "sigla": "SP"}]
        return [{"id": 3550308, "nome": "São Paulo"}]

    monkeypatch.setattr(LocationCatalogService, "_fetch", staticmethod(fake_fetch))

    state_count, city_count = LocationCatalogService.sync_from_ibge()

    assert (state_count, city_count) == (1, 1)
    assert State.objects.get(id=35).acronym == "SP"
    assert City.objects.get(id=3550308).normalized_name == "sao paulo"
