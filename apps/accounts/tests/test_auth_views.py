import pytest


@pytest.mark.django_db
def test_login_endpoint(api_client, demo_with_owner):
    response = api_client.post(
        "/api/v1/auth/login/",
        {"email": "admin@demo.com", "password": "demo1234", "subdomain": "demo"},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "admin@demo.com"


@pytest.mark.django_db
def test_admin_me_requires_token(api_client):
    response = api_client.get("/api/v1/admin/me/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_admin_me_with_token(api_client, demo_with_owner):
    login = api_client.post(
        "/api/v1/auth/login/",
        {"email": "admin@demo.com", "password": "demo1234", "subdomain": "demo"},
        format="json",
    ).json()

    response = api_client.get(
        "/api/v1/admin/me/",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "admin@demo.com"
    assert response.json()["tenant"]["subdomain"] == "demo"
    assert "preferences" in response.json()
    assert "dashboard" in response.json()["preferences"]
    assert "widget_order" in response.json()["preferences"]["dashboard"]


@pytest.mark.django_db
def test_preferences_patch_dashboard_order(api_client, demo_with_owner):
    login = api_client.post(
        "/api/v1/auth/login/",
        {"email": "admin@demo.com", "password": "demo1234", "subdomain": "demo"},
        format="json",
    ).json()

    response = api_client.patch(
        "/api/v1/auth/me/preferences/",
        {
            "dashboard": {
                "widget_order": ["top_products", "sales", "customers"],
                "hidden_widgets": ["slow_products"],
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dashboard"]["widget_order"][0] == "top_products"
    assert "sales" in body["dashboard"]["widget_order"]
    assert "slow_products" in body["dashboard"]["hidden_widgets"]

    again = api_client.get(
        "/api/v1/auth/me/preferences/",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
    )
    assert again.status_code == 200
    assert again.json()["dashboard"]["widget_order"][0] == "top_products"


@pytest.mark.django_db
def test_change_password_success(api_client, demo_with_owner):
    login = api_client.post(
        "/api/v1/auth/login/",
        {"email": "admin@demo.com", "password": "demo1234", "subdomain": "demo"},
        format="json",
    ).json()

    response = api_client.post(
        "/api/v1/auth/change-password/",
        {
            "current_password": "demo1234",
            "new_password": "novaSenha99",
            "confirm_password": "novaSenha99",
        },
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
    )
    assert response.status_code == 200

    old = api_client.post(
        "/api/v1/auth/login/",
        {"email": "admin@demo.com", "password": "demo1234", "subdomain": "demo"},
        format="json",
    )
    assert old.status_code != 200

    new = api_client.post(
        "/api/v1/auth/login/",
        {"email": "admin@demo.com", "password": "novaSenha99", "subdomain": "demo"},
        format="json",
    )
    assert new.status_code == 200


@pytest.mark.django_db
def test_change_password_wrong_current(api_client, demo_with_owner):
    login = api_client.post(
        "/api/v1/auth/login/",
        {"email": "admin@demo.com", "password": "demo1234", "subdomain": "demo"},
        format="json",
    ).json()

    response = api_client.post(
        "/api/v1/auth/change-password/",
        {
            "current_password": "errada",
            "new_password": "novaSenha99",
            "confirm_password": "novaSenha99",
        },
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_change_password_requires_auth(api_client):
    response = api_client.post(
        "/api/v1/auth/change-password/",
        {
            "current_password": "demo1234",
            "new_password": "novaSenha99",
            "confirm_password": "novaSenha99",
        },
        format="json",
    )
    assert response.status_code == 401
