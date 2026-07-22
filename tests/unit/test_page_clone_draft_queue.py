"""Reviewed Page Clone drafts queue through the existing guarded post pipeline."""
import asyncio
import json

import pytest

from agent.api import posts as posts_api
from agent.db import crud


@pytest.fixture
async def draft_account(db_ready):
    return await crud.create_account("Draft Queue Account")


@pytest.mark.asyncio
async def test_queue_page_clone_draft_uses_dry_run_post_task(draft_account, monkeypatch):
    monkeypatch.setattr("agent.config.LIVE_ACTIONS_ENABLED", False, raising=False)
    draft = await crud.create_post(
        draft_account["id"],
        post_type="TEXT",
        content="Reviewed clone content",
        target_type="PAGE",
        target_id="destination-page",
        status="DRAFT",
    )

    queued = await posts_api.queue_post(draft["id"])

    assert queued["post"]["status"] == "SCHEDULED"
    assert queued["task"]["task_type"] == "POST_TEXT"
    assert queued["task"]["ref_id"] == draft["id"]
    payload = json.loads(queued["task"]["payload"])
    assert payload["targetType"] == "PAGE"
    assert payload["targetId"] == "destination-page"
    assert payload["dryRun"] is True

    with pytest.raises(Exception) as exc_info:
        await posts_api.queue_post(draft["id"])
    assert getattr(exc_info.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_queue_rejects_non_draft_post(draft_account):
    post = await crud.create_post(draft_account["id"], content="already queued", status="SCHEDULED")

    with pytest.raises(Exception) as exc_info:
        await posts_api.queue_post(post["id"])

    assert getattr(exc_info.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_concurrent_queue_attempts_create_only_one_task(draft_account):
    draft = await crud.create_post(
        draft_account["id"], content="one queue only", status="DRAFT"
    )

    results = await asyncio.gather(
        posts_api.queue_post(draft["id"]),
        posts_api.queue_post(draft["id"]),
        return_exceptions=True,
    )

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, Exception) for result in results) == 1
    tasks = await crud.list_tasks(account_id=draft_account["id"])
    assert len(tasks) == 1
