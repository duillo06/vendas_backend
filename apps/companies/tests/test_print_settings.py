import pytest

from apps.catalog.services.seed_catalog import seed_demo_catalog
from apps.companies.domain.print_settings import DEFAULT_PRINT_SETTINGS, normalize_print_settings
from apps.companies.services.onboarding_service import OnboardingService
from apps.companies.services.settings_service import SettingsService


def test_normalize_print_settings_defaults():
    assert normalize_print_settings(None) == DEFAULT_PRINT_SETTINGS
    assert normalize_print_settings({})["paper_width"] == "80"


def test_normalize_print_settings_sanitizes():
    result = normalize_print_settings(
        {
            "paper_width": "58",
            "font_size": "large",
            "show_prices": False,
            "copies": 2,
            "footer_text": "x" * 200,
            "verse_text": "  " + ("y" * 300) + "  ",
        }
    )
    assert result["paper_width"] == "58"
    assert result["font_size"] == "large"
    assert result["show_prices"] is False
    assert result["copies"] == 2
    assert len(result["footer_text"]) == 120
    assert len(result["verse_text"]) == 280
    assert result["verse_text"].startswith("y")


def test_normalize_print_settings_empty_verse():
    result = normalize_print_settings({"verse_text": "   "})
    assert result["verse_text"] == ""
    assert result["footer_text"] == "Obrigado!"


@pytest.fixture
def demo_admin(db):
    company = OnboardingService.create_company(
        trade_name="Lanchonete Demo",
        subdomain="demo",
        email="contato@demo.com",
        owner_email="admin@demo.com",
        owner_password="demo1234",
    )
    seed_demo_catalog(company)
    SettingsService.update(company, auto_close_outside_hours=False, is_open=True)
    return company


@pytest.mark.django_db
def test_admin_settings_patch_print_settings(api_client, demo_admin):
    login = api_client.post(
        "/api/v1/auth/login/",
        {"email": "admin@demo.com", "password": "demo1234", "subdomain": "demo"},
        format="json",
    ).json()

    response = api_client.patch(
        "/api/v1/admin/settings/",
        {
            "settings": {
                "print_settings": {
                    "paper_width": "58",
                    "copies": 2,
                    "show_prices": False,
                    "footer_text": "Bom apetite",
                }
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
    )
    assert response.status_code == 200
    print_settings = response.json()["settings"]["print_settings"]
    assert print_settings["paper_width"] == "58"
    assert print_settings["copies"] == 2
    assert print_settings["show_prices"] is False
    assert print_settings["footer_text"] == "Bom apetite"
    assert print_settings["show_payment"] is True
