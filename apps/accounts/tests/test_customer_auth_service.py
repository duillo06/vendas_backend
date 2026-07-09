import pytest
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.services.customer_auth_service import CustomerAuthService
from apps.customers.models import Customer


@pytest.mark.django_db
def test_customer_register_and_login(demo_company):
    result = CustomerAuthService.register(
        tenant=demo_company,
        phone="(11) 98888-7777",
        password="senha1234",
        first_name="Maria",
        last_name="Santos",
    )

    assert result["customer"]["phone"] == "(11) 98888-7777"
    assert result["access"]

    login = CustomerAuthService.login(
        tenant=demo_company,
        phone="(11) 98888-7777",
        password="senha1234",
    )
    assert login["customer"]["full_name"] == "Maria Santos"


@pytest.mark.django_db
def test_customer_register_links_existing_guest(demo_company):
    Customer.objects.create(
        tenant=demo_company,
        phone="(11) 97777-6666",
        first_name="João",
        last_name="",
    )

    result = CustomerAuthService.register(
        tenant=demo_company,
        phone="(11) 97777-6666",
        password="senha1234",
        first_name="João",
    )

    customer = Customer.objects.get(tenant=demo_company, phone="(11) 97777-6666")
    assert customer.password_hash
    assert result["customer"]["has_account"] is True


@pytest.mark.django_db
def test_customer_login_invalid_password(demo_company):
    CustomerAuthService.register(
        tenant=demo_company,
        phone="(11) 96666-5555",
        password="senha1234",
        first_name="Ana",
    )

    with pytest.raises(AuthenticationFailed):
        CustomerAuthService.login(
            tenant=demo_company,
            phone="(11) 96666-5555",
            password="errada",
        )
