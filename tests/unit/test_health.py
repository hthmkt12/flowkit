from fastapi.testclient import TestClient

from agent.main import app


def test_health_returns_basic_readiness_without_api_auth():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
