import json
from datetime import date, timedelta

import pytest

from agent.db import crud
from agent.worker import processor
from agent.utils.time import utc_now, utc_now_iso


@pytest.fixture
async def account_a(db_ready):
    return await crud.create_account(
        name="Account A",
        fb_uid="fb-a",
        status="ACTIVE",
    )


@pytest.fixture
async def account_b(db_ready):
    return await crud.create_account(
        name="Account B",
        fb_uid="fb-b",
        status="ACTIVE",
    )


@pytest.mark.asyncio
async def test_claim_next_pending_task_skips_live_task_for_active_account(account_a, account_b, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)

    await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "same account live", "dryRun": False}),
        priority=10,
        enforce_safety=False,
    )
    await crud.create_task(
        account_id=account_b["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "other account live", "dryRun": False}),
        priority=5,
        enforce_safety=False,
    )

    claimed = await crud.claim_next_pending_task(excluded_live_account_ids={account_a["id"]})

    assert claimed["account_id"] == account_b["id"]
    assert claimed["status"] == "PROCESSING"


@pytest.mark.asyncio
async def test_claim_next_pending_task_allows_dry_run_for_active_account(account_a, account_b, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)

    await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "same account dry-run", "dryRun": True}),
        priority=10,
        enforce_safety=False,
    )
    await crud.create_task(
        account_id=account_b["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "other account live", "dryRun": False}),
        priority=5,
        enforce_safety=False,
    )

    claimed = await crud.claim_next_pending_task(excluded_live_account_ids={account_a["id"]})

    assert claimed["account_id"] == account_a["id"]
    assert json.loads(claimed["payload"])["dryRun"] is True


@pytest.mark.asyncio
async def test_live_account_lease_blocks_conflicting_node(account_a):
    first_task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "first", "dryRun": False}),
        enforce_safety=False,
    )
    second_task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "second", "dryRun": False}),
        enforce_safety=False,
    )

    lease = await crud.acquire_live_account_lease(account_a["id"], first_task["id"], "node-a", 900)
    blocked = await crud.acquire_live_account_lease(account_a["id"], second_task["id"], "node-b", 900)
    leases = await crud.list_active_live_account_leases()

    assert lease["account_id"] == account_a["id"]
    assert lease["task_id"] == first_task["id"]
    assert lease["node_id"] == "node-a"
    assert blocked is None
    assert leases == [lease]


@pytest.mark.asyncio
async def test_release_live_account_lease_requires_matching_task_and_node(account_a):
    task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "lease", "dryRun": False}),
        enforce_safety=False,
    )
    lease = await crud.acquire_live_account_lease(account_a["id"], task["id"], "node-a", 900)

    assert await crud.release_live_account_lease(account_a["id"], task["id"], "node-b") is False
    assert await crud.list_active_live_account_leases() == [lease]
    assert await crud.release_live_account_lease(account_a["id"], task["id"], "node-a") is True
    assert await crud.list_active_live_account_leases() == []


@pytest.mark.asyncio
async def test_expired_live_account_lease_can_be_reclaimed(account_a):
    first_task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "first", "dryRun": False}),
        enforce_safety=False,
    )
    second_task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "second", "dryRun": False}),
        enforce_safety=False,
    )
    await crud.acquire_live_account_lease(account_a["id"], first_task["id"], "node-a", 900)
    db = await crud.get_db()
    expired_at = (utc_now() - timedelta(seconds=1)).replace(microsecond=0).isoformat()
    await db.execute(
        "UPDATE live_account_lease SET expires_at = ?, heartbeat_at = ? WHERE account_id = ?",
        (expired_at, expired_at, account_a["id"]),
    )
    await db.commit()

    lease = await crud.acquire_live_account_lease(account_a["id"], second_task["id"], "node-b", 900)

    assert lease["account_id"] == account_a["id"]
    assert lease["task_id"] == second_task["id"]
    assert lease["node_id"] == "node-b"


@pytest.mark.asyncio
async def test_claim_next_pending_task_skips_db_leased_same_account_live_task(account_a, account_b, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)
    leased_task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "leased", "dryRun": False}),
        priority=10,
        enforce_safety=False,
    )
    await crud.create_task(
        account_id=account_b["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "other", "dryRun": False}),
        priority=5,
        enforce_safety=False,
    )
    await crud.acquire_live_account_lease(account_a["id"], leased_task["id"], "node-a", 900)

    claimed = await crud.claim_next_pending_task(node_id="node-b", live_lease_ttl_seconds=900)

    assert claimed["account_id"] == account_b["id"]
    assert (await crud.get_task(leased_task["id"]))["status"] == "PENDING"


@pytest.mark.asyncio
async def test_claim_next_pending_task_does_not_lease_dry_run_task(account_a, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)
    task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "dry", "dryRun": True}),
        priority=10,
        enforce_safety=False,
    )

    claimed = await crud.claim_next_pending_task(node_id="node-a", live_lease_ttl_seconds=900)

    assert claimed["id"] == task["id"]
    assert await crud.list_active_live_account_leases() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("dry_run_value", ["false", "0"])
async def test_claim_next_pending_task_leases_string_false_live_task(account_a, monkeypatch, dry_run_value):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)
    task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "live", "dryRun": dry_run_value}),
        priority=10,
        enforce_safety=False,
    )

    claimed = await crud.claim_next_pending_task(node_id="node-a", live_lease_ttl_seconds=900)
    leases = await crud.list_active_live_account_leases()

    assert claimed["id"] == task["id"]
    assert leases[0]["account_id"] == account_a["id"]
    assert leases[0]["task_id"] == task["id"]


@pytest.mark.asyncio
async def test_claim_next_pending_task_does_not_lease_string_true_dry_run_task(account_a, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)
    task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "dry", "dryRun": "true"}),
        priority=10,
        enforce_safety=False,
    )

    claimed = await crud.claim_next_pending_task(node_id="node-a", live_lease_ttl_seconds=900)

    assert claimed["id"] == task["id"]
    assert await crud.list_active_live_account_leases() == []


@pytest.mark.asyncio
async def test_process_local_exclusion_blocks_string_false_live_task(account_a, account_b, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)
    blocked_task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "blocked", "dryRun": "false"}),
        priority=10,
        enforce_safety=False,
    )
    await crud.create_task(
        account_id=account_b["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "other", "dryRun": False}),
        priority=5,
        enforce_safety=False,
    )

    claimed = await crud.claim_next_pending_task(excluded_live_account_ids={account_a["id"]})

    assert claimed["account_id"] == account_b["id"]
    assert (await crud.get_task(blocked_task["id"]))["status"] == "PENDING"


@pytest.mark.asyncio
async def test_worker_releases_live_account_lease_when_preflight_fails(account_a, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)

    task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "no arm", "dryRun": False, "_serverApproved": True}),
        enforce_safety=False,
    )
    claimed = await crud.claim_next_pending_task(node_id="node-a", live_lease_ttl_seconds=900)
    worker = processor.WorkerController(node_id="node-a")

    assert await worker._check_rate_limit(claimed) is False
    await worker._handle_preflight_failure(claimed)

    stored = await crud.get_task(task["id"])
    assert stored["status"] == "FAILED"
    assert stored["error_message"] == "Live mutating task requires an active matching live arm"
    assert await crud.list_active_live_account_leases() == []


@pytest.mark.asyncio
async def test_worker_releases_live_account_lease_when_predispatch_raises(account_a, monkeypatch):
    task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "raise", "dryRun": False}),
        enforce_safety=False,
    )
    claimed = await crud.claim_next_pending_task(node_id="node-a", live_lease_ttl_seconds=900)
    worker = processor.WorkerController(node_id="node-a")

    async def raise_preflight(task):
        raise RuntimeError("preflight exploded")

    monkeypatch.setattr(worker, "_check_rate_limit", raise_preflight)

    assert await worker._prepare_claimed_task(claimed) is None
    stored = await crud.get_task(task["id"])

    assert stored["status"] == "FAILED"
    assert stored["error_message"] == "preflight exploded"
    assert await crud.list_active_live_account_leases() == []


@pytest.mark.asyncio
async def test_process_task_cleanup_covers_setup_exceptions(account_a, monkeypatch):
    task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "setup", "dryRun": False}),
        enforce_safety=False,
    )
    lease = await crud.acquire_live_account_lease(account_a["id"], task["id"], "node-a", 900)
    worker = processor.WorkerController(node_id="node-a")
    worker._active_count = 1
    worker._active_live_account_ids.add(account_a["id"])

    async def raise_strategy(task_type, strategy_url):
        raise RuntimeError("strategy lookup exploded")

    monkeypatch.setattr(processor.crud, "get_strategy", raise_strategy)

    await worker._process_task(task, live_account_id=account_a["id"], live_lease=lease)
    stored = await crud.get_task(task["id"])

    assert stored["status"] == "PENDING"
    assert stored["error_message"] == "strategy lookup exploded"
    assert worker.active_count == 0
    assert account_a["id"] not in worker.active_live_account_ids
    assert await crud.list_active_live_account_leases() == []


@pytest.mark.asyncio
async def test_worker_releases_live_account_lease_after_processing(account_a, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)

    class FakeClient:
        def session_live_guard_enabled(self, fb_uid=None):
            return True

    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())
    monkeypatch.setattr(processor, "action_delay", lambda: None)
    arm = await crud.arm_live_actions(account_a["id"], ["POST_TEXT"], 300, created_by="unit-test")
    task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "live", "dryRun": False, "_serverApproved": True, "_liveArmId": arm["id"]}),
        enforce_safety=False,
    )
    lease = await crud.acquire_live_account_lease(account_a["id"], task["id"], "node-a", 900)
    worker = processor.WorkerController(node_id="node-a")

    async def fake_dispatch(*args, **kwargs):
        return {"success": True}

    monkeypatch.setattr(worker, "_dispatch", fake_dispatch)

    await worker._process_task(task, live_account_id=account_a["id"], live_lease=lease)

    assert await crud.list_active_live_account_leases() == []


@pytest.mark.asyncio
async def test_account_queue_summary_reports_queue_and_quota(account_a, monkeypatch):
    monkeypatch.setattr("agent.config.RATE_LIMIT_POSTS_PER_DAY", 20, raising=False)
    await crud.update_account(
        account_a["id"],
        daily_posts=20,
        daily_messages=3,
        daily_reset_at=date.today().isoformat(),
    )
    await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "queued"}),
    )

    summary = await crud.get_account_queue_summary(account_a["id"])

    assert summary["account_id"] == account_a["id"]
    assert summary["queue"]["PENDING"] == 1
    assert summary["quota"]["daily_posts"] == {"used": 20, "limit": 20}
    assert "quota_exhausted:daily_posts" in summary["blocked_reasons"]


@pytest.mark.asyncio
async def test_rate_limit_records_live_readiness_failure_reason(account_a, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)
    task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "no live arm", "dryRun": False, "_serverApproved": True}),
        enforce_safety=False,
    )

    worker = processor.WorkerController()

    assert await worker._check_rate_limit(task) is False
    assert worker.last_rate_limit_error == "Live mutating task requires an active matching live arm"


@pytest.mark.asyncio
async def test_worker_marks_and_clears_active_live_account(account_a, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    arm = await crud.arm_live_actions(
        account_id=account_a["id"],
        task_types=["POST_TEXT"],
        ttl_seconds=300,
        created_by="unit-test",
    )
    task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "live", "dryRun": False, "_serverApproved": True, "_liveArmId": arm["id"]}),
        enforce_safety=False,
    )
    worker = processor.WorkerController()

    live_account_id = worker._mark_live_account_if_needed(task)
    assert live_account_id == account_a["id"]
    assert account_a["id"] in worker.active_live_account_ids

    worker._clear_live_account(live_account_id)
    assert account_a["id"] not in worker.active_live_account_ids


@pytest.mark.asyncio
async def test_worker_persists_live_readiness_failure_reason(account_a, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)
    task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "no arm", "dryRun": False, "_serverApproved": True}),
        enforce_safety=False,
    )
    worker = processor.WorkerController()

    assert await worker._check_rate_limit(task) is False
    await worker._fail_task_for_rate_limit(task)
    stored = await crud.get_task(task["id"])

    assert stored["status"] == "FAILED"
    assert stored["error_message"] == "Live mutating task requires an active matching live arm"


@pytest.mark.asyncio
async def test_rate_limit_requires_fb_uid_before_quota_reservation(account_a, monkeypatch):
    account_without_uid = await crud.create_account(name="No UID")
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)
    arm = await crud.arm_live_actions(
        account_id=account_without_uid["id"],
        task_types=["POST_TEXT"],
        ttl_seconds=300,
        created_by="unit-test",
    )
    task = await crud.create_task(
        account_id=account_without_uid["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "no uid", "dryRun": False, "_serverApproved": True, "_liveArmId": arm["id"]}),
        enforce_safety=False,
    )
    worker = processor.WorkerController()

    assert await worker._check_rate_limit(task) is False
    assert worker.last_rate_limit_error == "Live mutating task requires account fb_uid for exact routing"
    account = await crud.get_account(account_without_uid["id"])
    assert account["daily_posts"] == 0


@pytest.mark.asyncio
async def test_quota_reservation_marker_is_date_scoped(account_a, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.APPROVAL_REQUIRED", True, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)

    class FakeClient:
        def session_live_guard_enabled(self, fb_uid=None):
            return True

    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())
    arm = await crud.arm_live_actions(
        account_id=account_a["id"],
        task_types=["POST_TEXT"],
        ttl_seconds=300,
        created_by="unit-test",
    )
    task = await crud.create_task(
        account_id=account_a["id"],
        task_type="POST_TEXT",
        payload=json.dumps({"content": "reserve", "dryRun": False, "_serverApproved": True, "_liveArmId": arm["id"]}),
        enforce_safety=False,
    )

    assert await processor.WorkerController()._check_rate_limit(task) is True
    stored = await crud.get_task(task["id"])
    reservation = json.loads(stored["payload"])["_quotaReserved"]

    assert reservation["date"] == date.today().isoformat()


@pytest.mark.asyncio
async def test_account_queue_summary_treats_stale_daily_counters_as_zero(account_a, monkeypatch):
    monkeypatch.setattr("agent.config.RATE_LIMIT_POSTS_PER_DAY", 20, raising=False)
    await crud.update_account(
        account_a["id"],
        daily_posts=20,
        daily_reset_at="2000-01-01",
    )

    summary = await crud.get_account_queue_summary(account_a["id"])

    assert summary["quota"]["daily_posts"] == {"used": 0, "limit": 20}
    assert "quota_exhausted:daily_posts" not in summary["blocked_reasons"]
