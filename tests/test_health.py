def test_health_check_returns_ok(api_client):
    response = api_client.get("/api/v1/health/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "version" in response.json()
    assert "timestamp" in response.json()
