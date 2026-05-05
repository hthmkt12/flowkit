"""Tests for delivering learned strategies to extension commands."""

import pytest

from agent.db import crud
from agent.services.fb_client import FBClient
from agent.worker import processor


@pytest.mark.asyncio
async def test_worker_passes_strategy_to_fb_client(monkeypatch):
    captured = {}

    class FakeClient:
        async def like_post(self, **kwargs):
            captured.update(kwargs)
            return {"success": True}

    monkeypatch.setattr(processor, "get_fb_client", lambda: FakeClient())

    strategy = {
        "selectors": {"likeBtn": 'div[aria-label="Like"]'},
        "wait_strategies": [{"step": "page_load", "wait_ms": 3500}],
        "workarounds": [{"error": "timeout", "fix": "retry"}],
    }

    worker = processor.WorkerController()
    result = await worker._dispatch(
        "LIKE_POST",
        {"postUrl": "https://facebook.com/post/1", "reaction": "LOVE"},
        {"id": "task-1", "task_type": "LIKE_POST"},
        fb_uid="fb-1",
        strategy=strategy,
    )

    assert result == {"success": True}
    assert captured["strategy"] == {
        "selectors": strategy["selectors"],
        "wait_strategies": strategy["wait_strategies"],
        "workarounds": strategy["workarounds"],
    }


@pytest.mark.asyncio
async def test_fb_client_sends_strategy_to_extension(monkeypatch):
    captured = {}
    client = FBClient()

    async def fake_send(method, params, fb_uid=None, timeout=120):
        captured["method"] = method
        captured["params"] = params
        captured["fb_uid"] = fb_uid
        captured["timeout"] = timeout
        return {"success": True}

    monkeypatch.setattr(client, "_send", fake_send)
    strategy = {"selectors": {"commentInput": 'div[role="textbox"]'}}

    result = await client.comment_post(
        post_url="https://facebook.com/post/1",
        comment="Nice post",
        fb_uid="fb-1",
        strategy=strategy,
    )

    assert result == {"success": True}
    assert captured["method"] == "comment_post"
    assert captured["fb_uid"] == "fb-1"
    assert captured["params"]["_strategy"] == strategy


@pytest.mark.asyncio
async def test_post_text_dispatch_sends_strategy_to_extension_params(monkeypatch):
    captured = {}
    client = FBClient()

    async def fake_send(method, params, fb_uid=None, timeout=120):
        captured["method"] = method
        captured["params"] = params
        captured["fb_uid"] = fb_uid
        captured["timeout"] = timeout
        return {"success": True}

    monkeypatch.setattr(client, "_send", fake_send)
    monkeypatch.setattr(processor, "get_fb_client", lambda: client)

    strategy = {
        "selectors": {"postBox": 'div[aria-label="Create a post"]'},
        "wait_strategies": [],
        "workarounds": [],
    }

    worker = processor.WorkerController()
    result = await worker._dispatch(
        "POST_TEXT",
        {"content": "hello", "targetType": "TIMELINE"},
        {"id": "task-1", "task_type": "POST_TEXT"},
        fb_uid="fb-1",
        strategy=strategy,
    )

    assert result == {"success": True}
    assert captured["method"] == "post_text"
    assert captured["fb_uid"] == "fb-1"
    assert captured["params"]["_strategy"] == strategy


@pytest.mark.asyncio
async def test_fb_client_sends_strategy_for_group_commands(monkeypatch):
    captured = {}
    client = FBClient()

    async def fake_send(method, params, fb_uid=None, timeout=120):
        captured["method"] = method
        captured["params"] = params
        captured["fb_uid"] = fb_uid
        return {"success": True}

    monkeypatch.setattr(client, "_send", fake_send)
    strategy = {"selectors": {"joinButton": 'div[aria-label="Join group"]'}}

    result = await client.join_group(
        group_url="https://facebook.com/groups/1",
        fb_uid="fb-1",
        strategy=strategy,
    )

    assert result == {"success": True}
    assert captured["method"] == "join_group"
    assert captured["fb_uid"] == "fb-1"
    assert captured["params"]["_strategy"] == strategy


@pytest.mark.asyncio
async def test_process_task_uses_url_specific_strategy(db_ready, monkeypatch):
    captured = {}

    class FakeSession:
        def record_action(self):
            pass

    class FakeNotifier:
        async def notify_task_completed(self, task):
            pass

    async def noop(*args, **kwargs):
        pass

    async def fake_dispatch(self, task_type, payload, task, fb_uid=None, strategy=None):
        captured["payload"] = payload
        captured["strategy"] = strategy
        return {"success": True}

    monkeypatch.setattr(processor, "action_delay", noop)
    monkeypatch.setattr(processor.event_bus, "emit", noop)
    monkeypatch.setattr(processor, "get_session_manager", lambda: FakeSession())
    monkeypatch.setattr(processor, "get_notifier", lambda: FakeNotifier())
    monkeypatch.setattr(processor.WorkerController, "_dispatch", fake_dispatch)

    account = await crud.create_account("Strategy Account", fb_uid="fb-1")
    post_url = "https://facebook.com/groups/1/posts/2"
    await crud.upsert_strategy(
        task_type="COMMENT_POST",
        url_pattern="*",
        selectors={"commentBox": "wildcard-selector"},
    )
    exact_strategy = await crud.upsert_strategy(
        task_type="COMMENT_POST",
        url_pattern=post_url,
        selectors={"commentBox": "exact-selector"},
    )
    task = await crud.create_task(
        account["id"],
        task_type="COMMENT_POST",
        payload='{"postUrl": "https://facebook.com/groups/1/posts/2", "comment": "Hi"}',
    )

    worker = processor.WorkerController()
    worker._active_count = 1
    await worker._process_task(task)

    assert captured["payload"]["postUrl"] == post_url
    assert captured["strategy"]["id"] == exact_strategy["id"]
    assert captured["strategy"]["selectors"]["commentBox"] == "exact-selector"


@pytest.mark.asyncio
async def test_process_task_uses_target_specific_strategy(db_ready, monkeypatch):
    captured = {}

    class FakeSession:
        def record_action(self):
            pass

    class FakeNotifier:
        async def notify_task_completed(self, task):
            pass

    async def noop(*args, **kwargs):
        pass

    async def fake_dispatch(self, task_type, payload, task, fb_uid=None, strategy=None):
        captured["payload"] = payload
        captured["strategy"] = strategy
        return {"success": True}

    monkeypatch.setattr(processor, "action_delay", noop)
    monkeypatch.setattr(processor.event_bus, "emit", noop)
    monkeypatch.setattr(processor, "get_session_manager", lambda: FakeSession())
    monkeypatch.setattr(processor, "get_notifier", lambda: FakeNotifier())
    monkeypatch.setattr(processor.WorkerController, "_dispatch", fake_dispatch)

    account = await crud.create_account("Target Strategy Account", fb_uid="fb-1")
    target_key = "GROUP:12345"
    await crud.upsert_strategy(
        task_type="POST_TEXT",
        url_pattern="*",
        selectors={"postBox": "wildcard-selector"},
    )
    target_strategy = await crud.upsert_strategy(
        task_type="POST_TEXT",
        url_pattern=target_key,
        selectors={"postBox": "target-selector"},
    )
    task = await crud.create_task(
        account["id"],
        task_type="POST_TEXT",
        payload='{"content": "Hello group", "targetType": "GROUP", "targetId": "12345"}',
    )

    worker = processor.WorkerController()
    worker._active_count = 1
    await worker._process_task(task)

    assert captured["payload"]["targetType"] == "GROUP"
    assert captured["payload"]["targetId"] == "12345"
    assert captured["strategy"]["id"] == target_strategy["id"]
    assert captured["strategy"]["selectors"]["postBox"] == "target-selector"


@pytest.mark.asyncio
async def test_process_task_prefers_url_strategy_over_target_strategy(db_ready, monkeypatch):
    captured = {}

    class FakeSession:
        def record_action(self):
            pass

    class FakeNotifier:
        async def notify_task_completed(self, task):
            pass

    async def noop(*args, **kwargs):
        pass

    async def fake_dispatch(self, task_type, payload, task, fb_uid=None, strategy=None):
        captured["strategy"] = strategy
        return {"success": True}

    monkeypatch.setattr(processor, "action_delay", noop)
    monkeypatch.setattr(processor.event_bus, "emit", noop)
    monkeypatch.setattr(processor, "get_session_manager", lambda: FakeSession())
    monkeypatch.setattr(processor, "get_notifier", lambda: FakeNotifier())
    monkeypatch.setattr(processor.WorkerController, "_dispatch", fake_dispatch)

    account = await crud.create_account("URL Priority Strategy Account", fb_uid="fb-1")
    post_url = "https://facebook.com/groups/12345/posts/67890"
    await crud.upsert_strategy(
        task_type="POST_TEXT",
        url_pattern="GROUP:12345",
        selectors={"postBox": "target-selector"},
    )
    url_strategy = await crud.upsert_strategy(
        task_type="POST_TEXT",
        url_pattern=post_url,
        selectors={"postBox": "url-selector"},
    )
    task = await crud.create_task(
        account["id"],
        task_type="POST_TEXT",
        payload=(
            '{"content": "Hello group", '
            '"postUrl": "https://facebook.com/groups/12345/posts/67890", '
            '"targetType": "GROUP", '
            '"targetId": "12345"}'
        ),
    )

    worker = processor.WorkerController()
    worker._active_count = 1
    await worker._process_task(task)

    assert captured["strategy"]["id"] == url_strategy["id"]
    assert captured["strategy"]["selectors"]["postBox"] == "url-selector"
