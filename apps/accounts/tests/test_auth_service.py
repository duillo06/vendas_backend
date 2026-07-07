import pytest
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.models import Employee
from apps.accounts.services.auth_service import AuthService
from apps.accounts.services.role_service import RoleService
from apps.companies.services.onboarding_service import OnboardingService


@pytest.fixture
def demo_with_owner(db):
    return OnboardingService.create_company(
        trade_name="Lanchonete Demo",
        subdomain="demo",
        email="contato@demo.com",
        owner_email="admin@demo.com",
        owner_password="demo1234",
    )


@pytest.mark.django_db
def test_role_service_creates_four_system_roles(demo_with_owner):
    roles = RoleService.create_system_roles(demo_with_owner)
    assert set(roles.keys()) == {"owner", "manager", "operator", "kitchen"}


@pytest.mark.django_db
def test_auth_login_success(demo_with_owner):
    result = AuthService.login(
        email="admin@demo.com",
        password="demo1234",
        subdomain="demo",
    )

    assert "access" in result
    assert "refresh" in result
    assert result["user"]["email"] == "admin@demo.com"
    assert result["user"]["is_owner"] is True
    assert "orders.view" in result["user"]["permissions"]
    assert result["tenant"]["subdomain"] == "demo"


@pytest.mark.django_db
def test_auth_login_invalid_password(demo_with_owner):
    with pytest.raises(AuthenticationFailed):
        AuthService.login(
            email="admin@demo.com",
            password="errada",
            subdomain="demo",
        )


@pytest.mark.django_db
def test_auth_refresh_returns_new_tokens(demo_with_owner):
    login = AuthService.login(
        email="admin@demo.com",
        password="demo1234",
        subdomain="demo",
    )

    refreshed = AuthService.refresh(refresh_token=login["refresh"])
    assert refreshed["access"]
    assert refreshed["refresh"]


@pytest.mark.django_db
def test_auth_logout_blacklists_refresh(demo_with_owner):
    login = AuthService.login(
        email="admin@demo.com",
        password="demo1234",
        subdomain="demo",
    )

    AuthService.logout(refresh_token=login["refresh"])

    with pytest.raises(AuthenticationFailed):
        AuthService.refresh(refresh_token=login["refresh"])


@pytest.mark.django_db
def test_inactive_employee_cannot_refresh(demo_with_owner):
    login = AuthService.login(
        email="admin@demo.com",
        password="demo1234",
        subdomain="demo",
    )

    employee = Employee.all_objects.get(email="admin@demo.com")
    employee.is_active = False
    employee.save()

    with pytest.raises(AuthenticationFailed):
        AuthService.refresh(refresh_token=login["refresh"])
