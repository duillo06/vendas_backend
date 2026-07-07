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
