import pytest

from agent.worker import processor


@pytest.mark.asyncio
async def test_page_clone_dispatches_as_read_only_with_bounded_contract(monkeypatch):
    seen = {}

    class FakeClient:
        def page_clone_session_ready(self, fb_uid):
            return True

        async def scrape_page_clone(self, **kwargs):
            seen.update(kwargs)
            return {"success": True, "data": {"posts": []}}

    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())
    result = await processor.WorkerController()._dispatch(
        "SCRAPE_PAGE_CLONE",
        {"sourceUrl": "https://www.facebook.com/acme", "maxPosts": 25},
        {"id": "t1", "task_type": "SCRAPE_PAGE_CLONE", "account_id": "a1"},
        fb_uid="fb-1",
    )

    assert result["success"] is True
    assert seen == {
        "source_url": "https://www.facebook.com/acme",
        "max_posts": 25,
        "max_media_per_post": 10,
        "deadline_seconds": 30,
        "fb_uid": "fb-1",
        "strategy": None,
    }


@pytest.mark.asyncio
async def test_page_clone_rejects_invalid_source_before_extension_dispatch(monkeypatch):
    class UnexpectedClient:
        async def scrape_page_clone(self, **kwargs):
            raise AssertionError("invalid source reached extension")

    monkeypatch.setattr(processor, "get_fb_client", lambda: UnexpectedClient())
    result = await processor.WorkerController()._dispatch(
        "SCRAPE_PAGE_CLONE",
        {"sourceUrl": "https://example.com/not-facebook"},
        {"id": "t2", "task_type": "SCRAPE_PAGE_CLONE", "account_id": "a1"},
        fb_uid="fb-1",
    )
    assert "Facebook host" in result["error"]


@pytest.mark.asyncio
async def test_page_clone_requires_an_exact_logged_in_account_session(monkeypatch):
    class UnexpectedClient:
        def page_clone_session_ready(self, fb_uid):
            return False

        async def scrape_page_clone(self, **kwargs):
            raise AssertionError("unbound page clone reached extension")

    monkeypatch.setattr(processor, "get_fb_client", lambda: UnexpectedClient())
    result = await processor.WorkerController()._dispatch(
        "SCRAPE_PAGE_CLONE",
        {"sourceUrl": "https://facebook.com/acme"},
        {"id": "t-session", "task_type": "SCRAPE_PAGE_CLONE", "account_id": "a1"},
        fb_uid=None,
    )
    assert result["code"] == "PAGE_CLONE_SESSION_UNAVAILABLE"


@pytest.mark.asyncio
async def test_page_clone_propagates_bounded_media_and_deadline(monkeypatch):
    seen = {}

    class FakeClient:
        def page_clone_session_ready(self, fb_uid):
            return True

        async def scrape_page_clone(self, **kwargs):
            seen.update(kwargs)
            return {"success": True}

    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())
    await processor.WorkerController()._dispatch(
        "SCRAPE_PAGE_CLONE",
        {
            "sourceUrl": "https://facebook.com/acme",
            "maxPosts": 2,
            "maxMediaPerPost": 3,
            "deadlineSeconds": 5,
        },
        {"id": "t3", "task_type": "SCRAPE_PAGE_CLONE", "account_id": "a1"},
        fb_uid="fb-1",
    )

    assert seen["max_posts"] == 2
    assert seen["max_media_per_post"] == 3
    assert seen["deadline_seconds"] == 5


@pytest.mark.asyncio
async def test_page_clone_cancellation_check_preserves_cancelled_state(monkeypatch):
    async def cancelled_task(task_id):
        return {"id": task_id, "status": "CANCELLED"}

    monkeypatch.setattr(processor.crud, "get_task", cancelled_task)
    assert await processor._task_is_cancelled("t-cancelled") is True


@pytest.mark.asyncio
async def test_page_clone_opt_in_media_cache_runs_before_evidence_redaction(monkeypatch):
    class FakeClient:
        def page_clone_session_ready(self, fb_uid):
            return True

        async def scrape_page_clone(self, **kwargs):
            return {"success": True, "data": {"posts": []}}

    cached = {}

    async def fake_cache(result, task_id):
        cached["task_id"] = task_id
        result["data"]["cached"] = True
        return result

    from agent.services import page_clone_media

    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())
    monkeypatch.setattr(page_clone_media, "cache_page_clone_media", fake_cache)
    result = await processor.WorkerController()._dispatch(
        "SCRAPE_PAGE_CLONE",
        {"sourceUrl": "https://facebook.com/acme", "downloadMedia": True},
        {"id": "task-cache", "task_type": "SCRAPE_PAGE_CLONE", "account_id": "a1"},
        fb_uid="fb-1",
    )

    assert cached["task_id"] == "task-cache"
    assert result["data"]["cached"] is True


def test_task_schema_allows_page_clone_without_mutation_arm():
    from pathlib import Path

    schema = (Path(__file__).parents[2] / "agent" / "db" / "schema.py").read_text()
    assert "'SCRAPE_PAGE_CLONE'" in schema


def test_page_clone_result_is_redacted_before_persistence():
    persisted = processor._persistable_result(
        "SCRAPE_PAGE_CLONE",
        {
            "success": True,
            "data": {
                "source_url": "https://www.facebook.com/acme",
                "profile": {"id": "123", "name": "Acme"},
                "posts": [],
                "access_token": "must-not-persist",
            },
        },
    )
    assert "source_url" not in str(persisted)
    assert "must-not-persist" not in str(persisted)
    assert persisted["data"]["source_ref"].startswith("sha256:")
