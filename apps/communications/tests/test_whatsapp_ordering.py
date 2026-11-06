import json

import pytest
from django.test import override_settings

from apps.catalog.services.seed_catalog import seed_demo_catalog
from apps.communications.domain.enums import ConnectionStatus
from apps.communications.infrastructure.providers.evolution.adapter import EvolutionWhatsAppAdapter
from apps.communications.models import CommunicationConnection
from apps.communications.ordering.service import OrderingService, national_phone
from apps.companies.services.onboarding_service import OnboardingService
from apps.companies.services.settings_service import SettingsService
from apps.orders.domain.enums import OrderSource
from apps.orders.models import Order


@pytest.fixture
def demo_store(db):
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


@pytest.fixture
def whatsapp(demo_store):
    return CommunicationConnection.all_objects.create(
        tenant=demo_store,
        status=ConnectionStatus.CONNECTED,
        ordering_enabled=True,
        phone_e164="5531999999999",
    )


def _pick(replies, prefix: str) -> str:
    reply = replies[-1]
    for item_id, _label in reply.buttons:
        if item_id.startswith(prefix):
            return item_id
    for item_id, _title, _desc in reply.rows:
        if item_id.startswith(prefix):
            return item_id
    raise AssertionError(f"sem opção {prefix}: {reply}")


@pytest.mark.django_db
def test_ordering_disabled_ignores_message(demo_store, whatsapp):
    whatsapp.ordering_enabled = False
    whatsapp.save(update_fields=["ordering_enabled"])
    replies = OrderingService.handle_inbound(
        connection=whatsapp,
        phone="5511987654321",
        message_id="m1",
        text="oi",
    )
    assert replies == []


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_whatsapp_pickup_creates_order(demo_store, whatsapp):
    phone = "5511987654321"
    replies = OrderingService.handle_inbound(
        connection=whatsapp,
        phone=phone,
        message_id="1",
        text="oi",
        push_name="Maria",
    )
    assert "não entendi" not in replies[-1].body.casefold()
    category = _pick(replies, "cat:")
    replies = OrderingService.handle_inbound(
        connection=whatsapp,
        phone=phone,
        message_id="2",
        selected_id=category,
    )
    product = _pick(replies, "prod:")
    replies = OrderingService.handle_inbound(
        connection=whatsapp,
        phone=phone,
        message_id="3",
        selected_id=product,
    )
    option = _pick(replies, "opt:")
    replies = OrderingService.handle_inbound(
        connection=whatsapp,
        phone=phone,
        message_id="4",
        selected_id=option,
    )
    replies = OrderingService.handle_inbound(
        connection=whatsapp,
        phone=phone,
        message_id="5",
        selected_id="qty:1",
    )
    replies = OrderingService.handle_inbound(
        connection=whatsapp,
        phone=phone,
        message_id="6",
        selected_id="cart:close",
    )
    replies = OrderingService.handle_inbound(
        connection=whatsapp,
        phone=phone,
        message_id="7",
        selected_id="how:pickup",
    )
    replies = OrderingService.handle_inbound(
        connection=whatsapp,
        phone=phone,
        message_id="8",
        selected_id="name:keep",
    )
    replies = OrderingService.handle_inbound(
        connection=whatsapp,
        phone=phone,
        message_id="9",
        selected_id="pay:pix",
    )
    replies = OrderingService.handle_inbound(
        connection=whatsapp,
        phone=phone,
        message_id="10",
        selected_id="ok",
    )

    assert "recebido" in replies[-1].body.lower()
    order = Order.all_objects.get(tenant=demo_store)
    assert order.source == OrderSource.WHATSAPP
    assert order.customer_phone


@pytest.mark.django_db
def test_duplicate_message_does_not_advance(demo_store, whatsapp):
    first = OrderingService.handle_inbound(
        connection=whatsapp,
        phone="5511987654321",
        message_id="same",
        text="oi",
    )
    second = OrderingService.handle_inbound(
        connection=whatsapp,
        phone="5511987654321",
        message_id="same",
        text="oi",
    )
    assert first
    assert second == []


@pytest.mark.django_db
def test_number_reply_opens_category(demo_store, whatsapp):
    replies = OrderingService.handle_inbound(
        connection=whatsapp,
        phone="5511987654321",
        message_id="n1",
        text="oi",
    )
    replies = OrderingService.handle_inbound(
        connection=whatsapp,
        phone="5511987654321",
        message_id="n2",
        text="1",
    )
    assert replies[-1].rows[0][0].startswith("prod:")


def test_national_phone_adds_missing_nine():
    assert national_phone("553398392280") == "33998392280"
    assert national_phone("5511997215521") == "11997215521"


def test_parse_inbound_ignores_own_messages():
    adapter = EvolutionWhatsAppAdapter()
    body = {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "5511987654321@s.whatsapp.net",
                "fromMe": False,
                "id": "ABC",
            },
            "pushName": "Maria",
            "message": {"conversation": "oi"},
        },
    }
    events = adapter.parse_webhook({}, json.dumps(body).encode())
    assert events[0].kind == "message_inbound"
    assert events[0].payload["phone"] == "5511987654321"
    assert events[0].payload["selected_id"] == ""

    body["data"]["key"]["fromMe"] = True
    events = adapter.parse_webhook({}, json.dumps(body).encode())
    assert events == []
