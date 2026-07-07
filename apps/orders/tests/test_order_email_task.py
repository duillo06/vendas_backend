import pytest
from django.core import mail

from apps.companies.services.onboarding_service import OnboardingService
from apps.customers.models import Customer
from apps.orders.models import Order
from apps.orders.tasks import send_order_confirmation_email


@pytest.mark.django_db
def test_send_order_confirmation_email_skips_without_customer_email():
    company = OnboardingService.create_company(
        trade_name="Pizza Test",
        subdomain="pizza-email",
        email="loja@test.com",
        owner_email="dono@test.com",
        owner_password="senha1234",
    )
    customer = Customer.objects.create(
        tenant=company,
        first_name="João",
        last_name="Silva",
        phone="11999990000",
        email=None,
    )
    order = Order.objects.create(
        tenant=company,
        customer=customer,
        order_number="#0001",
        delivery_type="pickup",
        subtotal="30.00",
        total="30.00",
        customer_name="João Silva",
        customer_phone="11999990000",
    )

    send_order_confirmation_email(str(order.id))

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_send_order_confirmation_email_sends_when_customer_has_email():
    company = OnboardingService.create_company(
        trade_name="Pizza Test",
        subdomain="pizza-email2",
        email="loja2@test.com",
        owner_email="dono2@test.com",
        owner_password="senha1234",
    )
    customer = Customer.objects.create(
        tenant=company,
        first_name="Maria",
        last_name="Souza",
        phone="11988880000",
        email="maria@example.com",
    )
    order = Order.objects.create(
        tenant=company,
        customer=customer,
        order_number="#0002",
        delivery_type="pickup",
        subtotal="45.00",
        total="45.00",
        customer_name="Maria Souza",
        customer_phone="11988880000",
    )

    send_order_confirmation_email(str(order.id))

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["maria@example.com"]
    assert "#0002" in mail.outbox[0].subject
