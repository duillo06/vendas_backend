import pytest

from apps.communications.domain.catalog import SITUATION_CATALOG
from apps.communications.infrastructure.providers._fake.adapter import FakeWhatsAppAdapter
from apps.communications.infrastructure.providers.registry import register_provider
from apps.communications.services.connection_service import ConnectionService
from apps.communications.services.engine import CommunicationEngine, CommunicationEvent
from apps.communications.services.renderer import render, validate_body
from apps.communications.domain.exceptions import TemplateValidationError
from apps.communications.domain.enums import ConnectionStatus, DispatchStatus
from apps.communications.models import MessageDispatch


@pytest.fixture
def fake_provider():
    adapter = FakeWhatsAppAdapter()
    register_provider("fake", adapter)
    return adapter


@pytest.mark.django_db
def test_renderer_substitui_chips():
    body = "Olá {{cliente}}, pedido {{pedido}}"
    out = render(body, {"customer_name": "Maria", "order_number": "#1"})
    assert out == "Olá Maria, pedido #1"


@pytest.mark.django_db
def test_validate_body_rejeita_token_desconhecido():
    with pytest.raises(TemplateValidationError):
        validate_body("Oi {{hacker}}", ["cliente"])


@pytest.mark.django_db
def test_connect_and_send_with_fake(demo_company, fake_provider):
    conn = ConnectionService.start_whatsapp_connection(
        tenant=demo_company,
        mode="byo",
        base_url="http://evolution.local",
        api_key="ok",
        provider_key="fake",
    )
    assert conn.status == ConnectionStatus.AWAITING_QR
    fake_provider.simulate_connect()
    ConnectionService.refresh_session(connection=conn)
    conn.refresh_from_db()
    assert conn.status == ConnectionStatus.CONNECTED
    assert conn.phone_e164

    dispatch = CommunicationEngine.send_test(
        connection=conn,
        body="teste",
    )
    assert dispatch.status == DispatchStatus.SENT
    assert fake_provider.sent


@pytest.mark.django_db
def test_engine_skips_when_disabled(demo_company, fake_provider):
    conn = ConnectionService.start_whatsapp_connection(
        tenant=demo_company,
        mode="byo",
        base_url="http://evolution.local",
        api_key="ok",
        provider_key="fake",
    )
    fake_provider.simulate_connect()
    ConnectionService.refresh_session(connection=conn)

    from apps.communications.services.template_service import TemplateService

    TemplateService.bulk_set_enabled(
        tenant=demo_company,
        enabled_map={"order.confirmed": False},
    )
    ack = CommunicationEngine.handle(
        CommunicationEvent(
            tenant_id=str(demo_company.id),
            event_key="order.confirmed",
            payload={"customer_phone": "5531999999999", "customer_name": "A"},
            idempotency_key="t1",
        ),
    )
    assert ack.accepted is False
    assert ack.reason == "situation_disabled"
    assert MessageDispatch.all_objects.filter(tenant=demo_company).count() == 0


@pytest.mark.django_db
def test_situation_catalog_completo():
    assert "order.confirmed" in SITUATION_CATALOG
    assert len(SITUATION_CATALOG) == 7
