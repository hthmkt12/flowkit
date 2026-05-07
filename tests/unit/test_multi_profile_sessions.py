import json
import time
import asyncio

import pytest

from agent.api import accounts as accounts_api
from agent.db import crud
from agent.services.fb_client import FBClient
from agent.worker import processor


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(json.loads(message))


@pytest.mark.asyncio
async def test_extension_ready_records_profile_identity_and_heartbeat():
    ws = FakeWS()
    client = FBClient(stale_after_s=30)
    client.set_extension(ws)

    await client.handle_message(
        ws,
        {
            "type": "extension_ready",
            "fb_uid": "fb-1",
            "loggedIn": True,
            "extensionLiveActionsEnabled": False,
            "profileId": "profile-a",
            "profileName": "FBKit Profile A",
        },
    )

    session = client.ws_stats["sessions"][0]
    assert session["fb_uid"] == "fb-1"
    assert session["profile_id"] == "profile-a"
    assert session["profile_name"] == "FBKit Profile A"
    assert session["health"] == "online"
    assert session["stale"] is False
    assert session["last_seen_age_s"] == 0


@pytest.mark.asyncio
async def test_pong_refreshes_session_heartbeat_with_identity():
    ws = FakeWS()
    client = FBClient(stale_after_s=30)
    session = client.set_extension(ws, fb_uid="fb-1")
    session.last_seen_at = time.time() - 20

    await client.handle_message(ws, {"type": "pong", "fb_uid": "fb-1", "loggedIn": True})

    stats = client.ws_stats["sessions"][0]
    assert stats["last_seen_age_s"] == 0
    assert stats["health"] == "online"


@pytest.mark.asyncio
async def test_ping_refreshes_session_heartbeat_like_real_extension():
    ws = FakeWS()
    client = FBClient(stale_after_s=30)
    session = client.set_extension(ws, fb_uid="fb-1")
    session.last_seen_at = time.time() - 20

    await client.handle_message(ws, {"type": "ping", "fb_uid": "fb-1", "loggedIn": True})

    stats = client.ws_stats["sessions"][0]
    assert stats["last_seen_age_s"] == 0
    assert stats["health"] == "online"
    assert ws.sent == [{"type": "pong"}]


@pytest.mark.asyncio
async def test_identity_bound_ping_without_uid_does_not_refresh_heartbeat():
    ws = FakeWS()
    client = FBClient(stale_after_s=30)
    session = client.set_extension(ws, fb_uid="fb-1")
    session.last_seen_at = time.time() - 31

    await client.handle_message(ws, {"type": "ping"})

    stats = client.ws_stats["sessions"][0]
    assert stats["stale"] is True
    assert stats["health"] == "stale"


@pytest.mark.asyncio
async def test_ping_updates_session_identity_when_facebook_account_changes():
    ws = FakeWS()
    client = FBClient(stale_after_s=30)
    client.set_extension(ws, fb_uid="fb-old")

    await client.handle_message(ws, {"type": "ping", "fb_uid": "fb-new", "loggedIn": True})

    session = client.ws_stats["sessions"][0]
    assert session["fb_uid"] == "fb-new"
    assert client.get_session_for("fb-old") is None
    assert client.get_session_for("fb-new") is not None


@pytest.mark.asyncio
async def test_ping_clears_session_identity_when_facebook_logs_out():
    ws = FakeWS()
    client = FBClient(stale_after_s=30)
    client.set_extension(ws, fb_uid="fb-old")

    await client.handle_message(ws, {"type": "ping", "fb_uid": None, "loggedIn": False})

    session = client.ws_stats["sessions"][0]
    assert session["fb_uid"] is None
    assert session["logged_in"] is False
    assert client.get_session_for("fb-old") is None


def test_ws_stats_marks_stale_sessions():
    ws = FakeWS()
    client = FBClient(stale_after_s=30)
    session = client.set_extension(ws, fb_uid="fb-1")
    session.last_seen_at = time.time() - 31

    stats = client.ws_stats["sessions"][0]

    assert stats["stale"] is True
    assert stats["health"] == "stale"


@pytest.mark.asyncio
async def test_exact_routing_ignores_stale_target_session():
    stale_ws = FakeWS()
    fresh_ws = FakeWS()
    client = FBClient(stale_after_s=30)
    stale_session = client.set_extension(stale_ws, fb_uid="fb-stale")
    stale_session.last_seen_at = time.time() - 31
    client.set_extension(fresh_ws, fb_uid="fb-fresh")

    result = await client.post_text("dry run", fb_uid="fb-stale", dry_run=True)

    assert result == {"error": "Extension session is stale"}
    assert stale_ws.sent == []
    assert fresh_ws.sent == []


@pytest.mark.asyncio
async def test_multi_profile_exact_routing_uses_matching_fresh_session():
    ws_a = FakeWS()
    ws_b = FakeWS()
    client = FBClient(stale_after_s=30)
    client.set_extension(ws_a, fb_uid="fb-a")
    client.set_extension(ws_b, fb_uid="fb-b")

    send_task = asyncio.create_task(client.post_text("dry run", fb_uid="fb-b", dry_run=True))
    await asyncio.sleep(0)
    request = ws_b.sent[0]
    await client.handle_message(ws_b, {"id": request["id"], "success": True, "dryRun": True})
    result = await send_task

    assert result == {"id": request["id"], "success": True, "dryRun": True}
    assert ws_a.sent == []
    assert ws_b.sent[0]["method"] == "post_text"


@pytest.mark.asyncio
async def test_exact_routing_prefers_fresh_duplicate_fb_uid_session():
    stale_ws = FakeWS()
    fresh_ws = FakeWS()
    client = FBClient(stale_after_s=30)
    stale_session = client.set_extension(stale_ws, fb_uid="fb-dup")
    stale_session.last_seen_at = time.time() - 31
    client.set_extension(fresh_ws, fb_uid="fb-dup")

    send_task = asyncio.create_task(client.post_text("dry run", fb_uid="fb-dup", dry_run=True))
    await asyncio.sleep(0)
    request = fresh_ws.sent[0]
    await client.handle_message(fresh_ws, {"id": request["id"], "success": True, "dryRun": True})
    result = await send_task

    assert result["success"] is True
    assert stale_ws.sent == []
    assert fresh_ws.sent[0]["method"] == "post_text"


@pytest.mark.asyncio
async def test_extension_status_excludes_stale_session_from_online_accounts(db_ready, monkeypatch):
    account = await crud.create_account(name="Profile Account", fb_uid="fb-1")
    stale_ws = FakeWS()
    client = FBClient(stale_after_s=30)
    session = client.set_extension(stale_ws, fb_uid="fb-1")
    session.last_seen_at = time.time() - 31
    monkeypatch.setattr(accounts_api, "get_fb_client", lambda: client)

    status = await accounts_api.get_extension_status()

    assert status["accounts"] == [
        {
            "id": account["id"],
            "fb_uid": "fb-1",
            "extension_online": False,
            "extension_health": "stale",
            "last_seen_age_s": 31,
            "profile_id": None,
            "profile_name": None,
            "extension_live_actions_enabled": None,
        }
    ]


@pytest.mark.asyncio
async def test_extension_status_uses_least_stale_duplicate_session_metadata(db_ready, monkeypatch):
    account = await crud.create_account(name="Duplicate Stale Account", fb_uid="fb-dup")
    newer_ws = FakeWS()
    older_ws = FakeWS()
    client = FBClient(stale_after_s=30)
    newer_session = client.set_extension(newer_ws, fb_uid="fb-dup")
    newer_session.profile_id = "newer-profile"
    newer_session.profile_name = "Newer Profile"
    newer_session.last_seen_at = time.time() - 45
    older_session = client.set_extension(older_ws, fb_uid="fb-dup")
    older_session.profile_id = "older-profile"
    older_session.profile_name = "Older Profile"
    older_session.last_seen_at = time.time() - 90
    monkeypatch.setattr(accounts_api, "get_fb_client", lambda: client)

    status = await accounts_api.get_extension_status()

    assert status["accounts"] == [
        {
            "id": account["id"],
            "fb_uid": "fb-dup",
            "extension_online": False,
            "extension_health": "stale",
            "last_seen_age_s": 45,
            "profile_id": "newer-profile",
            "profile_name": "Newer Profile",
            "extension_live_actions_enabled": None,
        }
    ]


@pytest.mark.asyncio
async def test_worker_waits_when_only_extension_sessions_are_stale(monkeypatch):
    class FakeSessionManager:
        def should_take_break(self):
            return False

    worker = processor.WorkerController()
    client = FBClient(stale_after_s=30)
    stale_session = client.set_extension(FakeWS(), fb_uid="fb-1")
    stale_session.last_seen_at = time.time() - 31
    claim_calls = []

    async def fake_claim_next_pending_task(active_live_account_ids):
        claim_calls.append(active_live_account_ids)
        return None

    async def fake_sleep(duration):
        worker._shutdown = True

    monkeypatch.setattr(processor, "get_fb_client", lambda: client)
    monkeypatch.setattr(processor, "get_session_manager", lambda: FakeSessionManager())
    monkeypatch.setattr(processor.crud, "claim_next_pending_task", fake_claim_next_pending_task)
    monkeypatch.setattr(processor.asyncio, "sleep", fake_sleep)

    await worker.start()

    assert claim_calls == []
