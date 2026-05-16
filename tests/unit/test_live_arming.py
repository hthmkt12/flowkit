import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from agent import main
from agent.api import tasks as tasks_api
from agent.db import crud
from agent.services.fb_client import FBClient
from agent.worker import processor


@pytest.fixture
async def test_account(db_ready, sample_account_data):
    return await crud.create_account(**sample_account_data)


@pytest.mark.asyncio
async def test_approve_task_rejects_live_task_without_matching_arm(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)

    task = await tasks_api.create_task(
        tasks_api.TaskCreate(
            account_id=test_account["id"],
            task_type="POST_TEXT",
            payload={"content": "must need explicit arm"},
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await tasks_api.approve_task(task["id"])

    stored_task = await crud.get_task(task["id"])
    payload = json.loads(stored_task["payload"] or "{}")

    assert exc_info.value.status_code == 409
    assert "live arm" in exc_info.value.detail.lower()
    assert payload["dryRun"] is True
    assert "_serverApproved" not in payload


@pytest.mark.asyncio
async def test_approve_task_allows_live_task_with_matching_arm(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)

    await crud.arm_live_actions(
        account_id=test_account["id"],
        task_types=["POST_TEXT"],
        ttl_seconds=300,
        created_by="unit-test",
    )
    task = await tasks_api.create_task(
        tasks_api.TaskCreate(
            account_id=test_account["id"],
            task_type="POST_TEXT",
            payload={"content": "armed live task"},
        )
    )

    approved_task = await tasks_api.approve_task(task["id"])
    payload = json.loads(approved_task["payload"] or "{}")

    assert payload["dryRun"] is False
    assert payload["_serverApproved"] is True
    assert payload["_liveArmId"]


@pytest.mark.asyncio
async def test_live_arm_requires_api_and_ws_auth(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)

    with pytest.raises(ValueError, match="API_AUTH_ENABLED"):
        await crud.arm_live_actions(
            account_id=test_account["id"],
            task_types=["POST_TEXT"],
            ttl_seconds=300,
            created_by="unit-test",
        )


@pytest.mark.asyncio
async def test_create_task_strips_client_supplied_live_arm_marker(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)

    task = await tasks_api.create_task(
        tasks_api.TaskCreate(
            account_id=test_account["id"],
            task_type="POST_TEXT",
            payload={
                "content": "hostile live arm marker",
                "_liveArmId": "client-supplied-arm",
            },
        )
    )

    payload = json.loads(task["payload"] or "{}")

    assert "_liveArmId" not in payload

    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", False, raising=False)

    with pytest.raises(ValueError, match="WS_AUTH_ENABLED"):
        await crud.arm_live_actions(
            account_id=test_account["id"],
            task_types=["POST_TEXT"],
            ttl_seconds=300,
            created_by="unit-test",
        )


@pytest.mark.asyncio
async def test_create_task_strips_all_client_supplied_server_owned_aliases(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)

    task = await tasks_api.create_task(
        tasks_api.TaskCreate(
            account_id=test_account["id"],
            task_type="POST_TEXT",
            payload={
                "content": "hostile server-owned aliases",
                "_quotaReserved": {"counter": "daily_posts"},
                "quotaReserved": {"counter": "daily_posts"},
                "_serverApproved": True,
                "serverApproved": True,
                "_liveArmId": "client-arm",
                "liveArmId": "client-arm",
                "live_arm_id": "client-arm",
                "approved": True,
            },
        )
    )

    payload = json.loads(task["payload"] or "{}")

    assert payload["dryRun"] is True
    assert payload["safetyReason"] == "approval_required"
    for field in (
        "_quotaReserved",
        "quotaReserved",
        "_serverApproved",
        "serverApproved",
        "_liveArmId",
        "liveArmId",
        "live_arm_id",
        "approved",
    ):
        assert field not in payload


@pytest.mark.asyncio
async def test_worker_dispatch_rejects_live_mutating_task_without_active_arm(db_ready, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)

    class FakeClient:
        async def post_text(self, **kwargs):
            raise AssertionError("live dispatch should fail before client call")

    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())

    worker = processor.WorkerController()
    result = await worker._dispatch(
        "POST_TEXT",
        {"content": "no active arm", "dryRun": False, "_serverApproved": True},
        {"id": "task-1", "task_type": "POST_TEXT", "account_id": "account-1"},
        fb_uid="fb-1",
    )

    assert result["error"] == "Live mutating task requires an active matching live arm"


@pytest.mark.asyncio
async def test_worker_dispatch_rejects_live_task_when_auth_disabled_after_approval(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    arm = await crud.arm_live_actions(
        account_id=test_account["id"],
        task_types=["POST_TEXT"],
        ttl_seconds=300,
        created_by="unit-test",
    )

    class FakeClient:
        async def post_text(self, **kwargs):
            raise AssertionError("live dispatch should fail before client call")

    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", False, raising=False)

    worker = processor.WorkerController()
    result = await worker._dispatch(
        "POST_TEXT",
        {"content": "auth drift", "dryRun": False, "_serverApproved": True, "_liveArmId": arm["id"]},
        {"id": "task-1", "task_type": "POST_TEXT", "account_id": test_account["id"]},
        fb_uid="fb-1",
    )

    assert result["error"] == "Live dispatch requires API_AUTH_ENABLED and WS_AUTH_ENABLED"


@pytest.mark.asyncio
async def test_rate_limit_does_not_reserve_quota_when_live_arm_is_missing(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)

    task = await crud.create_task(
        account_id=test_account["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "stale live", "dryRun": False, "_serverApproved": True}),
        enforce_safety=False,
    )

    allowed = await processor.WorkerController()._check_rate_limit(task)
    account = await crud.get_account(test_account["id"])

    assert allowed is False
    assert account["daily_posts"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("task_types", [["CHECK_LOGIN"], ["UNKNOWN_TASK"]])
async def test_live_arm_rejects_non_mutating_or_unknown_task_types(test_account, task_types, monkeypatch):
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)

    with pytest.raises(ValueError, match="Invalid live arm task_types"):
        await crud.arm_live_actions(
            account_id=test_account["id"],
            task_types=task_types,
            ttl_seconds=300,
            created_by="unit-test",
        )


@pytest.mark.asyncio
async def test_live_arm_rejects_excessive_ttl(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)

    with pytest.raises(ValueError, match="ttl_seconds must be <= 900"):
        await crud.arm_live_actions(
            account_id=test_account["id"],
            task_types=["POST_TEXT"],
            ttl_seconds=901,
            created_by="unit-test",
        )


@pytest.mark.asyncio
async def test_worker_dispatch_rejects_live_task_when_extension_guard_is_disabled(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    arm = await crud.arm_live_actions(
        account_id=test_account["id"],
        task_types=["POST_TEXT"],
        ttl_seconds=300,
        created_by="unit-test",
    )

    class FakeClient:
        def session_live_guard_enabled(self, fb_uid=None):
            return False

        async def post_text(self, **kwargs):
            raise AssertionError("live dispatch should fail before client call")

    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())

    worker = processor.WorkerController()
    result = await worker._dispatch(
        "POST_TEXT",
        {"content": "guard off", "dryRun": False, "_serverApproved": True, "_liveArmId": arm["id"]},
        {"id": "task-1", "task_type": "POST_TEXT", "account_id": test_account["id"]},
        fb_uid="fb-1",
    )

    assert result["error"] == "Extension live-action guard is disabled or unknown"


@pytest.mark.asyncio
async def test_worker_dispatch_accepts_specific_approved_arm_when_overlapping_arm_exists(test_account, monkeypatch):
    captured = {}
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    arm = await crud.arm_live_actions(
        account_id=test_account["id"],
        task_types=["POST_TEXT"],
        ttl_seconds=300,
        created_by="unit-test",
    )
    await crud.arm_live_actions(
        account_id=test_account["id"],
        task_types=["POST_TEXT"],
        ttl_seconds=600,
        created_by="unit-test-overlap",
    )

    class FakeClient:
        def session_live_guard_enabled(self, fb_uid=None):
            return True

        async def post_text(self, **kwargs):
            captured.update(kwargs)
            return {"success": True}

    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())

    result = await processor.WorkerController()._dispatch(
        "POST_TEXT",
        {"content": "arm A still valid", "dryRun": False, "_serverApproved": True, "_liveArmId": arm["id"]},
        {"id": "task-1", "task_type": "POST_TEXT", "account_id": test_account["id"]},
        fb_uid="fb-1",
    )

    assert result == {"success": True}
    assert captured["dry_run"] is False


@pytest.mark.asyncio
async def test_rate_limit_does_not_reserve_quota_when_extension_guard_disabled(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)
    arm = await crud.arm_live_actions(
        account_id=test_account["id"],
        task_types=["POST_TEXT"],
        ttl_seconds=300,
        created_by="unit-test",
    )

    class FakeClient:
        def session_live_guard_enabled(self, fb_uid=None):
            return False

    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())

    task = await crud.create_task(
        account_id=test_account["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "guard off", "dryRun": False, "_serverApproved": True, "_liveArmId": arm["id"]}),
        enforce_safety=False,
    )

    allowed = await processor.WorkerController()._check_rate_limit(task)
    account = await crud.get_account(test_account["id"])

    assert allowed is False
    assert account["daily_posts"] == 0


@pytest.mark.asyncio
async def test_status_reports_live_auth_and_active_arms(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    arm = await crud.arm_live_actions(
        account_id=test_account["id"],
        task_types=["POST_TEXT"],
        ttl_seconds=300,
        created_by="unit-test",
    )

    status = await main.get_status(None)

    assert status["safety_gate"]["api_auth_enabled"] is True
    assert status["safety_gate"]["ws_auth_enabled"] is True
    assert status["safety_gate"]["live_auth_ready"] is True
    assert status["safety_gate"]["active_live_arms"][0]["id"] == arm["id"]


@pytest.mark.asyncio
async def test_status_reports_worker_node_and_live_account_leases(test_account, monkeypatch):
    monkeypatch.setattr(main, "get_worker_controller", lambda: processor.WorkerController(node_id="node-status"))
    task = await crud.create_task(
        account_id=test_account["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "leased", "dryRun": False}),
        enforce_safety=False,
    )
    lease = await crud.acquire_live_account_lease(test_account["id"], task["id"], "node-status", 900)

    status = await main.get_status(None)

    assert status["worker"]["node_id"] == "node-status"
    assert status["worker"]["active_live_account_ids"] == []
    assert status["worker"]["live_account_leases"] == [lease]
    assert status["safety_gate"]["live_actions_enabled"] is False


@pytest.mark.asyncio
async def test_fb_client_records_extension_live_guard_state():
    ws = object()
    client = FBClient()
    client.set_extension(ws)

    await client.handle_message(
        ws,
        {
            "type": "extension_ready",
            "fb_uid": "fb-1",
            "loggedIn": True,
            "extensionLiveActionsEnabled": False,
        },
    )

    session = client.ws_stats["sessions"][0]
    assert session["fb_uid"] == "fb-1"
    assert session["logged_in"] is True
    assert session["extension_live_actions_enabled"] is False
    assert session["health"] == "online"


def test_live_arm_endpoint_requires_api_key_when_auth_enabled(monkeypatch):
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.services.auth.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_KEY", "test-key", raising=False)
    monkeypatch.setattr("agent.services.auth.API_KEY", "test-key", raising=False)

    response = TestClient(main.app).post(
        "/api/tasks/live-arm",
        json={"account_id": "account-1", "task_types": ["POST_TEXT"], "ttl_seconds": 300},
    )

    assert response.status_code == 401


def test_approve_endpoint_requires_api_key_when_auth_enabled(monkeypatch):
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.services.auth.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_KEY", "test-key", raising=False)
    monkeypatch.setattr("agent.services.auth.API_KEY", "test-key", raising=False)

    response = TestClient(main.app).post("/api/tasks/task-1/approve")

    assert response.status_code == 401
