from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect

from agent.main import app


def test_health_returns_basic_readiness_without_api_auth():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_does_not_expose_extension_session_identity(monkeypatch):
    class FakeClient:
        ws_stats = {
            "connected": True,
            "sessions": [
                {
                    "fb_uid": "100004822807900",
                    "profile_id": "profile-secret",
                    "profile_name": "Private Facebook Profile",
                    "logged_in": True,
                }
            ],
        }

    monkeypatch.setattr("agent.main.get_fb_client", lambda: FakeClient())

    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "FBKit Agent",
        "version": "1.0.0",
        "worker": {"active_tasks": 0},
    }
    assert "100004822807900" not in response.text
    assert "profile-secret" not in response.text
    assert "Private Facebook Profile" not in response.text


def test_cors_allows_local_dashboard_origin_only():
    client = TestClient(app)

    allowed = client.options(
        "/api/status",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    blocked = client.options(
        "/api/status",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert "access-control-allow-origin" not in blocked.headers


@pytest.mark.parametrize("query_name", ["token", "api_key", "credential", "authorization"])
def test_dashboard_websocket_rejects_query_credentials_even_without_api_auth(query_name):
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/dashboard?{query_name}=secret"):
            pass
