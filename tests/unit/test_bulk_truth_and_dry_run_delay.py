"""Truthful bulk message results and dry-run delay skip."""
import json

import pytest

from agent.worker import processor


def _bulk_payload(recipients, dry_run):
    return {
        "content": "bulk body",
        "recipients": recipients,
        "dryRun": dry_run,
    }


@pytest.mark.asyncio
async def test_bulk_all_recipients_fail_returns_failure(monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)

    class FakeClient:
        async def send_message(self, **kwargs):
            return {"success": False, "error": "blocked"}

    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())

    worker = processor.WorkerController()
    result = await worker._dispatch(
        "SEND_BULK_MESSAGE",
        _bulk_payload([{"name": "A"}, {"name": "B"}], dry_run=True),
        {"id": "t1", "task_type": "SEND_BULK_MESSAGE", "account_id": "a1"},
        fb_uid="fb-1",
    )

    assert result["success"] is False
    assert result["sent"] == 0
    assert result["failed"] == 2
    assert "failed" in result["message"].lower()


@pytest.mark.asyncio
async def test_bulk_partial_success_returns_success_with_structured_result(monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", True, raising=False)

    class FakeClient:
        async def send_message(self, **kwargs):
            name = kwargs.get("recipient_name")
            return {"success": True} if name == "A" else {"success": False, "error": "x"}

    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())

    result = await processor.WorkerController()._dispatch(
        "SEND_BULK_MESSAGE",
        _bulk_payload([{"name": "A"}, {"name": "B"}], dry_run=True),
        {"id": "t1", "task_type": "SEND_BULK_MESSAGE", "account_id": "a1"},
        fb_uid="fb-1",
    )

    assert result["success"] is True
    assert result["sent"] == 1
    assert result["failed"] == 1


@pytest.mark.asyncio
async def test_bulk_all_success_returns_success(monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)

    class FakeClient:
        async def send_message(self, **kwargs):
            return {"success": True}

    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())

    result = await processor.WorkerController()._dispatch(
        "SEND_BULK_MESSAGE",
        _bulk_payload([{"name": "A"}, {"name": "B"}], dry_run=True),
        {"id": "t1", "task_type": "SEND_BULK_MESSAGE", "account_id": "a1"},
        fb_uid="fb-1",
    )

    assert result["success"] is True
    assert result["sent"] == 2
    assert result["failed"] == 0


@pytest.mark.asyncio
async def test_bulk_dry_run_never_calls_long_delay(monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)

    long_delay_calls = []

    class FakeClient:
        async def send_message(self, **kwargs):
            return {"success": True}

    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())
    monkeypatch.setattr(
        "agent.worker.processor.long_delay",
        lambda: (_ for _ in ()).throw(AssertionError("long_delay must not run in dry-run bulk")),
    )
    # Track via async helper that records instead of sleeping.
    async def _spy_long_delay():
        long_delay_calls.append(1)

    monkeypatch.setattr("agent.worker.processor.long_delay", _spy_long_delay)

    result = await processor.WorkerController()._dispatch(
        "SEND_BULK_MESSAGE",
        _bulk_payload([{"name": "A"}, {"name": "B"}, {"name": "C"}], dry_run=True),
        {"id": "t1", "task_type": "SEND_BULK_MESSAGE", "account_id": "a1"},
        fb_uid="fb-1",
    )

    assert result["success"] is True
    assert long_delay_calls == [], "long_delay must not run in dry-run bulk"


@pytest.mark.asyncio
async def test_bulk_live_path_still_uses_long_delay(db_ready, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.API_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.WS_AUTH_ENABLED", True, raising=False)
    monkeypatch.setattr("agent.config.DRY_RUN_DEFAULT", False, raising=False)

    from agent.db import crud
    account = await crud.create_account(name="Bulk Live", fb_uid="fb-live")
    arm = await crud.arm_live_actions(account["id"], ["SEND_BULK_MESSAGE"], 300, "test")

    long_delay_calls = []

    class FakeClient:
        def session_live_guard_enabled(self, fb_uid=None):
            return True

        async def send_message(self, **kwargs):
            return {"success": True}

    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())

    async def _spy_long_delay():
        long_delay_calls.append(1)

    monkeypatch.setattr("agent.worker.processor.long_delay", _spy_long_delay)

    result = await processor.WorkerController()._dispatch(
        "SEND_BULK_MESSAGE",
        {
            "content": "live bulk",
            "recipients": [{"name": "A"}, {"name": "B"}],
            "dryRun": False,
            "_serverApproved": True,
            "_liveArmId": arm["id"],
        },
        {"id": "t1", "task_type": "SEND_BULK_MESSAGE", "account_id": account["id"]},
        fb_uid="fb-live",
    )

    assert result["success"] is True
    # Live bulk applies human delay after each recipient.
    assert long_delay_calls == [1, 1]
