from fastapi.testclient import TestClient

from app import app


def test_preflight_desde_la_app_web():
    client = TestClient(app)
    response = client.options(
        "/api/verify-sample",
        headers={"Origin": "http://localhost:8081", "Access-Control-Request-Method": "POST"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] in {"*", "http://localhost:8081"}
