from decimal import Decimal
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.catalog.models import Category, Product
from apps.companies.services.onboarding_service import OnboardingService
from apps.companies.services.settings_service import SettingsService
from apps.promotions.domain.enums import CampaignStatus, RecurrenceType
from apps.promotions.domain.exceptions import InvalidCampaignError
from apps.promotions.models import Campaign
from apps.promotions.services.campaign_resolver import CampaignResolver
from apps.promotions.services.campaign_service import CampaignService


@pytest.fixture
def demo_store(db):
    company = OnboardingService.create_company(
        trade_name="Lanchonete Promo",
        subdomain="promo",
        email="contato@promo.com",
        owner_email="admin@promo.com",
        owner_password="demo1234",
    )
    SettingsService.update(company, auto_close_outside_hours=False, is_open=True)
    return company


@pytest.fixture
def product(demo_store):
    cat = Category.all_objects.create(tenant=demo_store, name="Pizzas", slug="pizzas")
    return Product.all_objects.create(
        tenant=demo_store,
        category=cat,
        name="Pizza Calabresa",
        slug="pizza-calabresa",
        base_price=Decimal("70.00"),
    )


@pytest.mark.django_db
def test_create_campaign_rejects_price_not_lower(demo_store, product):
    with pytest.raises(InvalidCampaignError):
        CampaignService.create(
            tenant=demo_store,
            data={
                "product_id": product.id,
                "promo_price": "70.00",
            },
        )


@pytest.mark.django_db
def test_resolver_applies_once_campaign(demo_store, product):
    campaign = CampaignService.create(
        tenant=demo_store,
        data={
            "product_id": product.id,
            "promo_price": "59.00",
            "recurrence_type": RecurrenceType.ONCE,
            "starts_at": timezone.now() - timedelta(hours=1),
            "ends_at": timezone.now() + timedelta(days=1),
        },
    )
    offer = CampaignResolver.resolve_product(product)
    assert offer is not None
    assert offer.promo_price == Decimal("59.00")
    assert offer.save_amount == Decimal("11.00")
    assert offer.discount_percent == 16  # 11/70 ≈ 15.7 → 16
    assert CampaignResolver.effective_base_price(product) == Decimal("59.00")
    assert campaign.status == CampaignStatus.ACTIVE


@pytest.mark.django_db
def test_resolver_respects_weekdays(demo_store, product):
    # força um dia que não é hoje
    today = timezone.localtime().weekday()
    other = (today + 1) % 7
    CampaignService.create(
        tenant=demo_store,
        data={
            "product_id": product.id,
            "promo_price": "50.00",
            "recurrence_type": RecurrenceType.WEEKDAYS,
            "weekdays": [other],
            "starts_at": timezone.now() - timedelta(days=1),
        },
    )
    assert CampaignResolver.resolve_product(product) is None


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_checkout_charges_promo_price(api_client, demo_store, product):
    CampaignService.create(
        tenant=demo_store,
        data={
            "product_id": product.id,
            "promo_price": "59.00",
            "starts_at": timezone.now() - timedelta(hours=1),
        },
    )
    response = api_client.post(
        "/api/v1/public/orders/checkout/",
        {
            "customer_name": "Maria",
            "customer_phone": "(11) 98765-4321",
            "delivery_type": "pickup",
            "payment_method": "pix",
            "items": [{"product_id": str(product.id), "quantity": 1}],
        },
        format="json",
        HTTP_HOST="promo.localhost:8001",
    )
    assert response.status_code == 201, response.json()
    assert Decimal(str(response.json()["total"])) == Decimal("59.00")


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_public_offers_and_product_overlay(api_client, demo_store, product):
    CampaignService.create(
        tenant=demo_store,
        data={
            "product_id": product.id,
            "promo_price": "59.00",
            "show_on_home": True,
            "starts_at": timezone.now() - timedelta(hours=1),
        },
    )
    offers = api_client.get(
        "/api/v1/public/promotions/offers/",
        HTTP_HOST="promo.localhost:8001",
    )
    assert offers.status_code == 200
    body = offers.json()
    assert len(body) == 1
    assert body[0]["promo_price"] == 59.0
    assert body[0]["product_slug"] == "pizza-calabresa"

    detail = api_client.get(
        f"/api/v1/public/catalog/products/{product.slug}/",
        HTTP_HOST="promo.localhost:8001",
    )
    assert detail.status_code == 200
    data = detail.json()
    assert data["base_price"] == 59.0
    assert data["compare_price"] == 70.0
    assert data["promotion"]["discount_percent"] >= 15


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_admin_create_campaign(api_client, demo_store, product):
    login = api_client.post(
        "/api/v1/auth/login/",
        {"email": "admin@promo.com", "password": "demo1234", "subdomain": "promo"},
        format="json",
        HTTP_HOST="promo.localhost:8001",
    )
    assert login.status_code == 200, login.json()
    token = login.json()["access"]
    response = api_client.post(
        "/api/v1/admin/campaigns/",
        {
            "commercial_goal": "increase_sales",
            "product_id": str(product.id),
            "promo_price": "55.00",
            "recurrence_type": "once",
            "show_on_home": True,
        },
        format="json",
        HTTP_HOST="promo.localhost:8001",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert response.status_code == 201, response.json()
    assert response.json()["promo_price"] == 55.0
    assert Campaign.all_objects.filter(tenant=demo_store).count() == 1
