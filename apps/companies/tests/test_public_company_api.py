import pytest
from django.test import override_settings


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=["*"])
def test_public_company(api_client, demo_company):
    response = api_client.get(
        "/api/v1/public/company/",
        HTTP_HOST="demo.localhost:8001",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trade_name"] == demo_company.trade_name
    assert body["slug"] == demo_company.slug
    assert "is_open" in body
    assert "settings" in body
    assert len(body["business_hours"]) == 7
