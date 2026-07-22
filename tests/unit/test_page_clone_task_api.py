"""Page Clone API ingress must enforce the same bounded contract as the worker."""
import json

import pytest
from fastapi import HTTPException

from agent.api import tasks as tasks_api
from agent.db import crud


@pytest.fixture
async def page_clone_account(db_ready):
    return await crud.create_account("Page Clone API Account")


@pytest.mark.asyncio
async def test_page_clone_task_api_normalizes_and_bounds_request(page_clone_account):
    task = await tasks_api.create_task(
        tasks_api.TaskCreate(
            account_id=page_clone_account["id"],
            task_type="SCRAPE_PAGE_CLONE",
            payload={
                "sourceUrl": "https://m.facebook.com/acme/?ref=share",
                "maxPosts": 25,
                "candidateLimit": 8,
                "maxMediaPerPost": 10,
                "deadlineSeconds": 30,
            },
        )
    )

    assert task["task_type"] == "SCRAPE_PAGE_CLONE"
    assert json.loads(task["payload"]) == {
        "sourceUrl": "https://www.facebook.com/acme",
        "maxPosts": 25,
        "candidateLimit": 8,
        "maxMediaPerPost": 10,
        "deadlineSeconds": 30,
        "downloadMedia": False,
    }


@pytest.mark.asyncio
async def test_page_clone_task_api_rejects_over_limit_request(page_clone_account):
    with pytest.raises(HTTPException) as exc_info:
        await tasks_api.create_task(
            tasks_api.TaskCreate(
                account_id=page_clone_account["id"],
                task_type="SCRAPE_PAGE_CLONE",
                payload={"sourceUrl": "https://facebook.com/acme", "maxPosts": 26},
            )
        )

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_page_clone_task_api_rejects_unknown_or_unsafe_payload(page_clone_account):
    with pytest.raises(HTTPException) as exc_info:
        await tasks_api.create_task(
            tasks_api.TaskCreate(
                account_id=page_clone_account["id"],
                task_type="SCRAPE_PAGE_CLONE",
                payload={"sourceUrl": "https://example.com/not-facebook", "token": "nope"},
            )
        )

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_cancelling_page_clone_redacts_queued_source_url(page_clone_account):
    task = await tasks_api.create_task(
        tasks_api.TaskCreate(
            account_id=page_clone_account["id"],
            task_type="SCRAPE_PAGE_CLONE",
            payload={"sourceUrl": "https://facebook.com/acme"},
        )
    )

    cancelled = await crud.cancel_task(task["id"])
    payload = json.loads(cancelled["payload"])
    assert cancelled["status"] == "CANCELLED"
    assert payload["sourceRef"].startswith("sha256:")
    assert "sourceUrl" not in payload
