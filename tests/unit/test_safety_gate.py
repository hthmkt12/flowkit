"""Tests for Safety Gate v1 dry-run enforcement."""

import json
from datetime import date

import pytest
from fastapi import HTTPException

from agent.api import posts as posts_api
from agent.api import tasks as tasks_api
from agent.db import crud
from agent.services.fb_client import FBClient
from agent.services.scheduler import Scheduler
from agent.worker import processor


@pytest.fixture
async def test_account(db_ready, sample_account_data):
    return await crud.create_account(**sample_account_data)


@pytest.mark.asyncio
async def test_create_task_forces_mutating_task_to_dry_run(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)

    task = await tasks_api.create_task(
        tasks_api.TaskCreate(
            account_id=test_account["id"],
            task_type="POST_TEXT",
            payload={"content": "hello from safety test"},
        )
    )

    payload = json.loads(task["payload"] or "{}")
    assert payload["dryRun"] is True
    assert payload["safetyReason"] == "live_actions_disabled"


@pytest.mark.asyncio
async def test_create_task_does_not_add_dry_run_to_read_only_task(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)

    task = await tasks_api.create_task(
        tasks_api.TaskCreate(
            account_id=test_account["id"],
            task_type="CHECK_LOGIN",
            payload={},
        )
    )

    payload = json.loads(task["payload"] or "{}")
    assert "dryRun" not in payload
    assert "safetyReason" not in payload


@pytest.mark.asyncio
async def test_create_task_strips_client_supplied_quota_reservation(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)

    task = await tasks_api.create_task(
        tasks_api.TaskCreate(
            account_id=test_account["id"],
            task_type="POST_TEXT",
            payload={
                "content": "hostile reservation marker",
                "_quotaReserved": {"counter": "daily_posts", "units": 999},
            },
        )
    )

    payload = json.loads(task["payload"] or "{}")
    assert "_quotaReserved" not in payload


@pytest.mark.asyncio
async def test_create_task_strips_client_supplied_approval(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)

    task = await tasks_api.create_task(
        tasks_api.TaskCreate(
            account_id=test_account["id"],
            task_type="POST_TEXT",
            payload={
                "content": "hostile approval marker",
                "approved": True,
                "dryRun": False,
                "_serverApproved": True,
            },
        )
    )

    payload = json.loads(task["payload"] or "{}")
    assert "approved" not in payload
    assert "_serverApproved" not in payload
    assert payload["dryRun"] is True
    assert payload["safetyReason"] == "approval_required"


@pytest.mark.asyncio
async def test_approve_task_allows_live_dispatch_when_live_actions_enabled(test_account, monkeypatch):
    captured = {}

    class FakeClient:
        async def post_text(self, **kwargs):
            captured.update(kwargs)
            return {"success": True}

    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)
    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())

    task = await tasks_api.create_task(
        tasks_api.TaskCreate(
            account_id=test_account["id"],
            task_type="POST_TEXT",
            payload={"content": "server approved live task"},
        )
    )
    approved_task = await tasks_api.approve_task(task["id"])
    payload = json.loads(approved_task["payload"] or "{}")

    worker = processor.WorkerController()
    result = await worker._dispatch(
        "POST_TEXT",
        payload,
        {"id": task["id"], "task_type": "POST_TEXT"},
        fb_uid="fb-1",
    )

    assert result == {"success": True}
    assert captured["dry_run"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["COMPLETED", "FAILED", "CANCELLED", "PROCESSING"])
async def test_approve_task_rejects_non_pending_status(test_account, status, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    task = await crud.create_task(
        account_id=test_account["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "should not approve"}),
    )
    await crud.update_task(task["id"], status=status)

    with pytest.raises(HTTPException) as exc_info:
        await tasks_api.approve_task(task["id"])

    assert exc_info.value.status_code == 409
    assert "Only PENDING tasks can be approved" in exc_info.value.detail


@pytest.mark.asyncio
async def test_approve_task_rechecks_pending_status_atomically(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    task = await crud.create_task(
        account_id=test_account["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "approval race"}),
    )
    approve_pending_task = crud.approve_pending_task

    async def claim_before_update(task_id, payload):
        await crud.update_task(task_id, status="PROCESSING")
        return await approve_pending_task(task_id, payload)

    monkeypatch.setattr(tasks_api.crud, "approve_pending_task", claim_before_update, raising=False)

    with pytest.raises(HTTPException) as exc_info:
        await tasks_api.approve_task(task["id"])

    stored_task = await crud.get_task(task["id"])
    payload = json.loads(stored_task["payload"] or "{}")

    assert exc_info.value.status_code == 409
    assert "_serverApproved" not in payload


@pytest.mark.asyncio
async def test_approve_task_logs_activity_for_audit(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    task = await crud.create_task(
        account_id=test_account["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "audit approval"}),
    )

    await tasks_api.approve_task(task["id"])

    activities = await crud.list_activities(account_id=test_account["id"])
    assert any(
        activity["action"] == "APPROVE_TASK"
        and task["id"][:8] in (activity["detail"] or "")
        for activity in activities
    )


@pytest.mark.asyncio
async def test_approve_task_rejects_malformed_payload(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    task = await crud.create_task(
        account_id=test_account["id"],
        task_type="POST_TEXT",
        payload="{not-json",
    )

    with pytest.raises(HTTPException) as exc_info:
        await tasks_api.approve_task(task["id"])

    assert exc_info.value.status_code == 400
    assert "Task payload is not valid JSON" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_post_auto_queue_forces_post_link_to_dry_run(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)

    await posts_api.create_post(
        posts_api.PostCreate(
            account_id=test_account["id"],
            post_type="LINK",
            content="Link via posts API",
            auto_queue=True,
        )
    )

    tasks = await crud.list_tasks(account_id=test_account["id"], task_type="POST_LINK")
    payload = json.loads(tasks[0]["payload"] or "{}")

    assert payload["dryRun"] is True
    assert payload["safetyReason"] == "live_actions_disabled"


@pytest.mark.asyncio
async def test_scheduler_enqueue_post_forces_mutating_task_to_dry_run(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)

    post = await crud.create_post(
        account_id=test_account["id"],
        post_type="TEXT",
        content="Scheduled post must stay dry-run",
        status="SCHEDULED",
        scheduled_at="2026-01-01T00:00:00",
    )

    await Scheduler()._enqueue_post(post)

    tasks = await crud.list_tasks(account_id=test_account["id"], task_type="POST_TEXT")
    payload = json.loads(tasks[0]["payload"] or "{}")

    assert payload["dryRun"] is True
    assert payload["safetyReason"] == "live_actions_disabled"


@pytest.mark.asyncio
async def test_scheduler_enqueue_post_is_idempotent(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    post = await crud.create_post(
        account_id=test_account["id"],
        post_type="TEXT",
        content="Enqueue once only",
        status="SCHEDULED",
        scheduled_at="2026-01-01T00:00:00",
    )

    scheduler = Scheduler()
    await scheduler._enqueue_post(post)
    await scheduler._enqueue_post(post)

    tasks = await crud.list_tasks(account_id=test_account["id"], task_type="POST_TEXT")
    assert len(tasks) == 1


@pytest.mark.asyncio
async def test_create_reup_post_forces_task_to_dry_run(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)

    result = await posts_api.create_reup_post(
        posts_api.ReupVideoCreate(
            account_id=test_account["id"],
            source_url="https://example.com/video.mp4",
            content="Dry-run reup only",
        )
    )

    payload = json.loads(result["task"]["payload"] or "{}")

    assert payload["dryRun"] is True
    assert payload["safetyReason"] == "live_actions_disabled"


@pytest.mark.asyncio
async def test_worker_dispatch_forces_mutating_task_to_dry_run(monkeypatch):
    captured = {}

    class FakeClient:
        async def post_text(self, **kwargs):
            captured.update(kwargs)
            return {"success": True}

    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())

    worker = processor.WorkerController()
    result = await worker._dispatch(
        "POST_TEXT",
        {"content": "must not publish"},
        {"id": "task-1", "task_type": "POST_TEXT"},
        fb_uid="fb-1",
    )

    assert result == {"success": True}
    assert captured["dry_run"] is True


@pytest.mark.asyncio
async def test_process_task_does_not_increment_daily_counter_for_dry_run(test_account, monkeypatch):
    class FakeClient:
        async def post_text(self, **kwargs):
            return {"success": True, "dryRun": kwargs["dry_run"]}

    async def no_delay():
        return None

    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())
    monkeypatch.setattr(processor, "action_delay", no_delay)

    task = await crud.create_task(
        account_id=test_account["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "dry-run counter test"}),
    )

    worker = processor.WorkerController()
    await worker._process_task(task)

    account = await crud.get_account(test_account["id"])
    stored_task = await crud.get_task(task["id"])

    assert stored_task["status"] == "COMPLETED"
    assert account["daily_posts"] == 0


@pytest.mark.asyncio
async def test_process_task_uses_server_dry_run_state_for_counter(test_account, monkeypatch):
    class FakeClient:
        async def post_text(self, **kwargs):
            return {"success": True}

    async def no_delay():
        return None

    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())
    monkeypatch.setattr(processor, "action_delay", no_delay)

    task = await crud.create_task(
        account_id=test_account["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "non-echoing dry-run result"}),
    )

    worker = processor.WorkerController()
    await worker._process_task(task)

    account = await crud.get_account(test_account["id"])
    assert account["daily_posts"] == 0


@pytest.mark.asyncio
async def test_claim_next_pending_task_only_claims_once(test_account):
    await crud.create_task(
        account_id=test_account["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "claim once"}),
    )

    first = await crud.claim_next_pending_task()
    second = await crud.claim_next_pending_task()

    assert first is not None
    assert first["status"] == "PROCESSING"
    assert second is None


@pytest.mark.asyncio
async def test_rate_limit_allows_forced_dry_run_when_limit_exceeded(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.config.RATE_LIMIT_POSTS_PER_DAY", 0, raising=False)

    worker = processor.WorkerController()
    allowed = await worker._check_rate_limit({
        "account_id": test_account["id"],
        "task_type": "POST_TEXT",
        "payload": json.dumps({"content": "dry-run over quota"}),
    })

    assert allowed is True


@pytest.mark.asyncio
async def test_rate_limit_reserves_bulk_message_quota_per_recipient(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)
    monkeypatch.setattr("agent.config.RATE_LIMIT_MESSAGES_PER_DAY", 50, raising=False)
    await crud.update_account(
        test_account["id"],
        daily_messages=48,
        daily_reset_at=date.today().isoformat(),
    )

    worker = processor.WorkerController()
    allowed = await worker._check_rate_limit({
        "account_id": test_account["id"],
        "task_type": "SEND_BULK_MESSAGE",
        "payload": json.dumps({
            "content": "quota reserve",
            "recipients": [{"name": "A"}, {"name": "B"}],
        }),
    })

    account = await crud.get_account(test_account["id"])
    assert allowed is True
    assert account["daily_messages"] == 50


@pytest.mark.asyncio
async def test_rate_limit_rejects_bulk_message_when_recipient_count_exceeds_remaining_quota(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)
    monkeypatch.setattr("agent.config.RATE_LIMIT_MESSAGES_PER_DAY", 50, raising=False)
    await crud.update_account(
        test_account["id"],
        daily_messages=48,
        daily_reset_at=date.today().isoformat(),
    )

    worker = processor.WorkerController()
    allowed = await worker._check_rate_limit({
        "account_id": test_account["id"],
        "task_type": "SEND_BULK_MESSAGE",
        "payload": json.dumps({
            "content": "too many recipients",
            "recipients": [{"name": "A"}, {"name": "B"}, {"name": "C"}],
        }),
    })

    account = await crud.get_account(test_account["id"])
    assert allowed is False
    assert account["daily_messages"] == 48


@pytest.mark.asyncio
async def test_rate_limit_does_not_reserve_quota_twice_for_same_task(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)
    monkeypatch.setattr("agent.config.RATE_LIMIT_POSTS_PER_DAY", 20, raising=False)
    await crud.update_account(
        test_account["id"],
        daily_posts=5,
        daily_reset_at=date.today().isoformat(),
    )
    task = await crud.create_task(
        account_id=test_account["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "reserve once"}),
    )

    worker = processor.WorkerController()
    assert await worker._check_rate_limit(task) is True
    task_after_first_check = await crud.get_task(task["id"])
    assert await worker._check_rate_limit(task_after_first_check) is True

    account = await crud.get_account(test_account["id"])
    assert account["daily_posts"] == 6


@pytest.mark.asyncio
async def test_rate_limit_rejects_malformed_bulk_recipients_without_reserving_quota(test_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)
    monkeypatch.setattr("agent.config.RATE_LIMIT_MESSAGES_PER_DAY", 50, raising=False)
    await crud.update_account(
        test_account["id"],
        daily_messages=10,
        daily_reset_at=date.today().isoformat(),
    )

    worker = processor.WorkerController()
    allowed = await worker._check_rate_limit({
        "account_id": test_account["id"],
        "task_type": "SEND_BULK_MESSAGE",
        "payload": json.dumps({
            "content": "bad recipients",
            "recipients": "not-a-list",
        }),
    })

    account = await crud.get_account(test_account["id"])
    assert allowed is False
    assert account["daily_messages"] == 10


@pytest.mark.asyncio
async def test_worker_dispatch_dry_run_reup_video_does_not_download(monkeypatch):
    download_called = False

    async def fake_download_video(source_url, task_id):
        nonlocal download_called
        download_called = True
        return {"local_path": "downloaded.mp4", "title": "Downloaded"}

    class FakeClient:
        async def post_with_media(self, **kwargs):
            return {"success": True}

    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())
    monkeypatch.setattr("agent.services.downloader.download_video", fake_download_video)

    worker = processor.WorkerController()
    result = await worker._dispatch(
        "REUP_VIDEO",
        {"sourceUrl": "https://example.com/video.mp4", "content": "dry-run reup"},
        {"id": "task-1", "task_type": "REUP_VIDEO"},
        fb_uid="fb-1",
    )

    assert result["success"] is True
    assert result["dryRun"] is True
    assert download_called is False


@pytest.mark.asyncio
async def test_worker_dispatch_routes_post_link_as_dry_run_text_post(monkeypatch):
    captured = {}

    class FakeClient:
        async def post_text(self, **kwargs):
            captured.update(kwargs)
            return {"success": True}

    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())

    worker = processor.WorkerController()
    result = await worker._dispatch(
        "POST_LINK",
        {
            "content": "Read this before publishing",
            "linkUrl": "https://example.com/article",
            "targetType": "TIMELINE",
        },
        {"id": "task-1", "task_type": "POST_LINK"},
        fb_uid="fb-1",
    )

    assert result == {"success": True}
    assert captured["dry_run"] is True
    assert captured["content"] == "Read this before publishing\nhttps://example.com/article"


@pytest.mark.asyncio
async def test_worker_dispatch_allows_server_approved_live_task(monkeypatch):
    captured = {}

    class FakeClient:
        async def post_text(self, **kwargs):
            captured.update(kwargs)
            return {"success": True}

    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())

    worker = processor.WorkerController()
    result = await worker._dispatch(
        "POST_TEXT",
        {"content": "approved live", "_serverApproved": True, "dryRun": False},
        {"id": "task-1", "task_type": "POST_TEXT"},
        fb_uid="fb-1",
    )

    assert result == {"success": True}
    assert captured["dry_run"] is False


@pytest.mark.asyncio
async def test_worker_dispatch_never_adds_dry_run_to_check_login(monkeypatch):
    captured = {}

    class FakeClient:
        async def check_login(self, **kwargs):
            captured.update(kwargs)
            return {"success": True}

    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())

    worker = processor.WorkerController()
    result = await worker._dispatch(
        "CHECK_LOGIN",
        {},
        {"id": "task-1", "task_type": "CHECK_LOGIN"},
        fb_uid="fb-1",
    )

    assert result == {"success": True}
    assert captured == {"fb_uid": "fb-1"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("task_type", "payload", "client_method", "expected_key"),
    [
        ("ADD_FRIEND", {"profileUrl": "https://facebook.com/profile.php?id=1"}, "add_friend", "profile_url"),
        ("ACCEPT_FRIEND", {"requestUrl": "https://facebook.com/friends/requests"}, "accept_friend", "request_url"),
        ("JOIN_GROUP", {"groupUrl": "https://facebook.com/groups/1"}, "join_group", "group_url"),
        ("LEAVE_GROUP", {"groupUrl": "https://facebook.com/groups/1"}, "leave_group", "group_url"),
        ("FOLLOW_PAGE", {"pageUrl": "https://facebook.com/example"}, "follow_page", "page_url"),
        ("UNFOLLOW_PAGE", {"pageUrl": "https://facebook.com/example"}, "unfollow_page", "page_url"),
    ],
)
async def test_worker_dispatch_forces_relationship_group_page_actions_to_dry_run(
    task_type,
    payload,
    client_method,
    expected_key,
    monkeypatch,
):
    captured = {}

    class FakeClient:
        async def add_friend(self, **kwargs):
            captured.update(kwargs)
            return {"success": True}

        async def accept_friend(self, **kwargs):
            captured.update(kwargs)
            return {"success": True}

        async def join_group(self, **kwargs):
            captured.update(kwargs)
            return {"success": True}

        async def leave_group(self, **kwargs):
            captured.update(kwargs)
            return {"success": True}

        async def follow_page(self, **kwargs):
            captured.update(kwargs)
            return {"success": True}

        async def unfollow_page(self, **kwargs):
            captured.update(kwargs)
            return {"success": True}

    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())

    worker = processor.WorkerController()
    result = await worker._dispatch(
        task_type,
        payload,
        {"id": "task-1", "task_type": task_type},
        fb_uid="fb-1",
    )

    assert result == {"success": True}
    assert captured["dry_run"] is True
    assert expected_key in captured


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "args", "expected_method", "expected_url_key"),
    [
        ("add_friend", ("https://facebook.com/profile.php?id=1",), "add_friend", "profileUrl"),
        ("accept_friend", ("https://facebook.com/friends/requests",), "accept_friend", "requestUrl"),
        ("join_group", ("https://facebook.com/groups/1",), "join_group", "groupUrl"),
        ("leave_group", ("https://facebook.com/groups/1",), "leave_group", "groupUrl"),
        ("follow_page", ("https://facebook.com/example",), "follow_page", "pageUrl"),
        ("unfollow_page", ("https://facebook.com/example",), "unfollow_page", "pageUrl"),
    ],
)
async def test_fb_client_sends_dry_run_to_relationship_group_page_actions(
    method_name,
    args,
    expected_method,
    expected_url_key,
    monkeypatch,
):
    captured = {}
    client = FBClient()

    async def fake_send(method, params, fb_uid=None, timeout=120):
        captured.update({
            "method": method,
            "params": params,
            "fb_uid": fb_uid,
            "timeout": timeout,
        })
        return {"success": True}

    monkeypatch.setattr(client, "_send", fake_send)

    result = await getattr(client, method_name)(*args, fb_uid="fb-1", dry_run=True)

    assert result == {"success": True}
    assert captured["method"] == expected_method
    assert captured["fb_uid"] == "fb-1"
    assert captured["params"]["dryRun"] is True
    assert captured["params"][expected_url_key] == args[0]
