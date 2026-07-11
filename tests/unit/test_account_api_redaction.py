"""Account API redaction tests.

The HTTP boundary must never return decrypted cookies/session material.
All account-producing routes (list/create/get/update + extension-status)
use typed allowlisted response models so secret fields cannot leak even
if the internal repository still decrypts them.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import ASGITransport

from agent import main
from agent.db import crud
from agent.services.fb_client import FBClient, ExtensionSession

# Fields that must NEVER appear in any account HTTP response body.
FORBIDDEN_FIELDS = {
    "cookies_data",
    "session_data",
    "cookies",
    "session",
    "cookie",
    "token",
}


def _iter_secret_strings(obj: Any):
    """Yield every string value anywhere in obj (recursive)."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_secret_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_secret_strings(v)
    elif isinstance(obj, str):
        yield obj


def _assert_no_secret(payload: Any, canaries: set[str]) -> None:
    for field in FORBIDDEN_FIELDS:
        assert field not in payload, f"forbidden field '{field}' present in {payload}"
    # Recursive scan: no canary secret value may survive anywhere.
    for value in _iter_secret_strings(payload):
        assert value not in canaries, f"canary secret leaked in response: {value}"


@pytest.fixture
async def api_client(monkeypatch):
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.services.auth.API_AUTH_ENABLED", False, raising=False)
    transport = ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def account_with_secrets(db_ready, sample_account_data):
    canaries = {
        "cookies_data": "CANARY-COOKIES-1234567890",
        "session_data": "CANARY-SESSION-SESSIONKEY-abcdef",
    }
    acc = await crud.create_account(
        name=sample_account_data["name"],
        fb_uid=sample_account_data["fb_uid"],
        email=sample_account_data["email"],
        cookies_data=canaries["cookies_data"],
        session_data=canaries["session_data"],
    )
    return acc, canaries


@pytest.mark.asyncio
async def test_list_accounts_does_not_leak_secrets(api_client, account_with_secrets):
    _acc, canaries = account_with_secrets

    response = await api_client.get("/api/accounts")

    assert response.status_code == 200
    _assert_no_secret(response.json(), canaries)


@pytest.mark.asyncio
async def test_get_account_does_not_leak_secrets(api_client, account_with_secrets):
    acc, canaries = account_with_secrets

    response = await api_client.get(f"/api/accounts/{acc['id']}")

    assert response.status_code == 200
    _assert_no_secret(response.json(), canaries)


@pytest.mark.asyncio
async def test_create_account_does_not_leak_secrets(api_client, db_ready):
    response = await api_client.post(
        "/api/accounts",
        json={"name": "Create Canary", "fb_uid": "canary-uid", "email": "canary@example.com"},
    )

    assert response.status_code == 200
    body = response.json()
    for field in FORBIDDEN_FIELDS:
        assert field not in body


@pytest.mark.asyncio
async def test_update_account_does_not_leak_secrets(api_client, account_with_secrets):
    acc, canaries = account_with_secrets

    response = await api_client.patch(
        f"/api/accounts/{acc['id']}",
        json={"status": "PAUSED"},
    )

    assert response.status_code == 200
    _assert_no_secret(response.json(), canaries)


@pytest.mark.asyncio
async def test_extension_status_does_not_leak_session_secrets(api_client, account_with_secrets, monkeypatch):
    acc, canaries = account_with_secrets

    real_client = FBClient()
    monkeypatch.setattr("agent.api.accounts.get_fb_client", lambda: real_client)
    ws = object()
    session = ExtensionSession(
        ws=ws,
        fb_uid=acc["fb_uid"],
        logged_in=True,
        extension_live_actions_enabled=False,
        profile_id="CANARY-PROFILE-ID",
        profile_name="CANARY-PROFILE-NAME",
    )
    real_client._sessions[ws] = session

    response = await api_client.get("/api/accounts/extension-status")

    assert response.status_code == 200
    _assert_no_secret(response.json(), canaries)


@pytest.mark.asyncio
async def test_internal_account_lookup_still_decrypts_secrets(account_with_secrets):
    """Internal CRUD repository must still decrypt secrets at the boundary."""
    acc, canaries = account_with_secrets

    row = await crud.get_account(acc["id"])

    assert row is not None
    assert row["cookies_data"] == canaries["cookies_data"]
    assert row["session_data"] == canaries["session_data"]
