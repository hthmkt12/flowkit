import asyncio
import json

import pytest


class FakeCloudSocket:
    def __init__(self, incoming):
        self.incoming = list(incoming)
        self.sent = []

    async def send(self, message):
        self.sent.append(json.loads(message))

    async def recv(self):
        return json.dumps(self.incoming.pop(0))


@pytest.fixture
async def db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "zoopost_adapter_test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("LIVE_ACTIONS_ENABLED", "false")
    monkeypatch.setenv("DRY_RUN_DEFAULT", "true")
    monkeypatch.setenv("APPROVAL_REQUIRED", "true")

    import agent.config as config
    import agent.db.schema as schema_mod

    config.LIVE_ACTIONS_ENABLED = False
    config.DRY_RUN_DEFAULT = True
    config.APPROVAL_REQUIRED = True
    schema_mod._db = None
    schema_mod.DB_PATH = db_path
    await schema_mod.init_db()
    yield
    await schema_mod.close_db()


@pytest.mark.asyncio
async def test_dry_run_dispatch_creates_fbkit_task(db):
    from agent.db import crud
    from agent.services.zoopost_cloud_agent import handle_dispatch

    account = await crud.create_account("Page A", fb_uid="page-1")
    result = await handle_dispatch(
        {
            "dispatchId": "dispatch-1",
            "platform": "facebook",
            "channelType": "fanpage",
            "platformTaskType": "facebook.post_text",
            "expectedFbUid": "page-1",
            "content": {"body": "Xin chao ZooPost"},
        }
    )

    assert result["dispatchId"] == "dispatch-1"
    assert result["localTaskId"]
    task = await crud.get_task(result["localTaskId"])
    payload = json.loads(task["payload"])
    assert task["account_id"] == account["id"]
    assert task["task_type"] == "POST_TEXT"
    assert task["ref_id"] == "zoopost:dispatch-1"
    assert payload["dryRun"] is True
    assert payload["content"] == "Xin chao ZooPost"
    assert payload["expectedFbUid"] == "page-1"


@pytest.mark.asyncio
async def test_duplicate_dispatch_reuses_existing_local_task(db):
    from agent.db import crud
    from agent.services.zoopost_cloud_agent import handle_dispatch

    await crud.create_account("Page A", fb_uid="page-1")
    dispatch = {
        "dispatchId": "dispatch-dup",
        "platform": "facebook",
        "channelType": "fanpage",
        "platformTaskType": "facebook.post_text",
        "expectedFbUid": "page-1",
        "content": {"body": "One task"},
    }

    first = await handle_dispatch(dispatch)
    second = await handle_dispatch(dispatch)
    tasks = await crud.list_tasks()

    assert first["localTaskId"] == second["localTaskId"]
    assert second["duplicate"] is True
    assert len(tasks) == 1


@pytest.mark.asyncio
async def test_cloud_live_markers_are_stripped_and_forced_dry_run(db):
    from agent.db import crud
    from agent.services.zoopost_cloud_agent import handle_dispatch

    await crud.create_account("Page A", fb_uid="page-1")
    result = await handle_dispatch(
        {
            "dispatchId": "dispatch-live-marker",
            "platform": "facebook",
            "channelType": "fanpage",
            "platformTaskType": "facebook.post_text",
            "expectedFbUid": "page-1",
            "dryRun": False,
            "content": {"body": "Must stay safe"},
            "payload": {
                "_serverApproved": True,
                "_liveArmId": "cloud-arm",
                "_quotaReserved": {"counter": "daily_posts"},
                "approved": True,
                "liveArmId": "cloud-arm",
            },
        }
    )

    task = await crud.get_task(result["localTaskId"])
    payload = json.loads(task["payload"])
    assert payload["dryRun"] is True
    assert "_serverApproved" not in payload
    assert "_liveArmId" not in payload
    assert "_quotaReserved" not in payload
    assert "approved" not in payload
    assert "liveArmId" not in payload


@pytest.mark.asyncio
async def test_concurrent_duplicate_dispatch_creates_one_local_task(db):
    from agent.db import crud
    from agent.services.zoopost_cloud_agent import handle_dispatch

    await crud.create_account("Page A", fb_uid="page-1")
    dispatch = {
        "dispatchId": "dispatch-race",
        "platform": "facebook",
        "channelType": "fanpage",
        "platformTaskType": "facebook.post_text",
        "expectedFbUid": "page-1",
        "content": {"body": "One race task"},
    }

    first, second = await asyncio.gather(handle_dispatch(dispatch), handle_dispatch(dispatch))
    tasks = await crud.list_tasks()

    assert first["localTaskId"] == second["localTaskId"]
    assert len(tasks) == 1


@pytest.mark.parametrize(
    "media",
    [
        {"path": "C:/Users/me/Pictures/a.png"},
        ["C:/Users/me/Pictures/a.png"],
        [{"path": "C:/Users/me/Pictures/a.png"}],
        [{"localPath": "C:/Users/me/Pictures/a.png"}],
        [{"file_path": "C:/Users/me/Pictures/a.png"}],
    ],
)
@pytest.mark.asyncio
async def test_cloud_filesystem_paths_are_rejected(db, media):
    from agent.db import crud
    from agent.services.zoopost_cloud_agent import handle_dispatch

    await crud.create_account("Page A", fb_uid="page-1")

    with pytest.raises(ValueError, match="opaque local media refs"):
        await handle_dispatch(
            {
                "dispatchId": "dispatch-path",
                "platform": "facebook",
                "channelType": "fanpage",
                "platformTaskType": "facebook.post_image",
                "expectedFbUid": "page-1",
                "content": {"body": "Bad media"},
                "media": media,
            }
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"mediaPaths": ["C:/Users/me/Pictures/a.png"]},
        {"mediaPath": "C:/Users/me/Pictures/a.png"},
        {"nested": {"filePath": "C:/Users/me/Pictures/a.png"}},
        {"items": [{"local_path": "C:/Users/me/Pictures/a.png"}]},
    ],
)
@pytest.mark.asyncio
async def test_payload_media_paths_are_rejected(db, payload):
    from agent.db import crud
    from agent.services.zoopost_cloud_agent import handle_dispatch

    await crud.create_account("Page A", fb_uid="page-1")

    with pytest.raises(ValueError, match="opaque local media refs"):
        await handle_dispatch(
            {
                "dispatchId": "dispatch-payload-path",
                "platform": "facebook",
                "channelType": "fanpage",
                "platformTaskType": "facebook.post_image",
                "expectedFbUid": "page-1",
                "content": {"body": "Bad payload media"},
                "payload": payload,
            }
        )


@pytest.mark.asyncio
async def test_opaque_media_refs_are_kept_as_non_executable_metadata(db):
    from agent.db import crud
    from agent.services.zoopost_cloud_agent import handle_dispatch

    await crud.create_account("Page A", fb_uid="page-1")
    result = await handle_dispatch(
        {
            "dispatchId": "dispatch-media-ref",
            "platform": "facebook",
            "channelType": "fanpage",
            "platformTaskType": "facebook.post_image",
            "expectedFbUid": "page-1",
            "content": {"body": "Media ref"},
            "media": [{"ref": "local-media-token"}],
        }
    )

    task = await crud.get_task(result["localTaskId"])
    payload = json.loads(task["payload"])
    assert payload["zoopostMediaRefs"] == [{"ref": "local-media-token"}]
    assert "mediaPaths" not in payload


@pytest.mark.asyncio
async def test_result_message_maps_fbkit_task_status(db):
    from agent.db import crud
    from agent.services.zoopost_cloud_agent import build_dispatch_result, handle_dispatch

    await crud.create_account("Page A", fb_uid="page-1")
    result = await handle_dispatch(
        {
            "dispatchId": "dispatch-result",
            "platform": "facebook",
            "channelType": "fanpage",
            "platformTaskType": "facebook.post_text",
            "expectedFbUid": "page-1",
            "content": {"body": "Result"},
        }
    )
    task = await crud.update_task(result["localTaskId"], status="COMPLETED", result=json.dumps({"externalPostId": "dry-run-post"}))

    message = build_dispatch_result("dispatch-result", task)

    assert message["type"] == "agent_dispatch_result"
    assert message["dispatchId"] == "dispatch-result"
    assert message["resultStatus"] == "posted"
    assert message["externalPostId"] == "dry-run-post"


@pytest.mark.asyncio
async def test_result_message_requires_terminal_task_status(db):
    from agent.db import crud
    from agent.services.zoopost_cloud_agent import build_dispatch_result, handle_dispatch

    await crud.create_account("Page A", fb_uid="page-1")
    result = await handle_dispatch(
        {
            "dispatchId": "dispatch-pending-result",
            "platform": "facebook",
            "channelType": "fanpage",
            "platformTaskType": "facebook.post_text",
            "expectedFbUid": "page-1",
            "content": {"body": "Pending"},
        }
    )
    task = await crud.get_task(result["localTaskId"])

    with pytest.raises(ValueError, match="terminal dispatch result"):
        build_dispatch_result("dispatch-pending-result", task)


@pytest.mark.asyncio
async def test_gateway_poll_processes_dispatch_batch(db):
    from agent.db import crud
    from agent.services.zoopost_cloud_agent import open_gateway_session, poll_gateway_dispatches

    await crud.create_account("Page A", fb_uid="page-1")
    socket = FakeCloudSocket(
        [
            {"type": "agent_hello_ack", "sessionId": "session-1", "sessionGeneration": 1, "connectionId": "conn-1"},
            {
                "type": "agent_dispatch_batch",
                "messageId": "poll-2",
                "dispatches": [
                    {
                        "type": "dispatch_publish_target",
                        "dispatchId": "dispatch-gateway",
                        "platform": "facebook",
                        "channelType": "fanpage",
                        "platformTaskType": "facebook.post_text",
                        "expectedFbUid": "page-1",
                        "content": {"body": "Gateway post"},
                        "dryRun": True,
                    }
                ],
            },
        ]
    )

    session = await open_gateway_session(socket, "credential", "conn-1", [{"platform": "facebook", "channel_type": "fanpage", "external_id": "page-1"}])
    results = await poll_gateway_dispatches(socket, session, limit=5)
    task = await crud.get_task(results[0]["localTaskId"])

    assert socket.sent[0]["type"] == "agent_hello"
    assert socket.sent[1]["type"] == "agent_dispatch_poll"
    assert socket.sent[1]["sessionId"] == "session-1"
    assert socket.sent[1]["limit"] == 5
    assert task["ref_id"] == "zoopost:dispatch-gateway"


@pytest.mark.asyncio
async def test_gateway_poll_caps_cloud_dispatch_batch_to_requested_limit(db):
    from agent.db import crud
    from agent.services.zoopost_cloud_agent import open_gateway_session, poll_gateway_dispatches

    await crud.create_account("Page A", fb_uid="page-1")
    socket = FakeCloudSocket(
        [
            {"type": "agent_hello_ack", "sessionId": "session-1", "sessionGeneration": 1, "connectionId": "conn-1"},
            {
                "type": "agent_dispatch_batch",
                "messageId": "poll-2",
                "dispatches": [
                    {
                        "type": "dispatch_publish_target",
                        "dispatchId": "dispatch-limit-a",
                        "platform": "facebook",
                        "channelType": "fanpage",
                        "platformTaskType": "facebook.post_text",
                        "expectedFbUid": "page-1",
                        "content": {"body": "First"},
                        "dryRun": True,
                    },
                    {
                        "type": "dispatch_publish_target",
                        "dispatchId": "dispatch-limit-b",
                        "platform": "facebook",
                        "channelType": "fanpage",
                        "platformTaskType": "facebook.post_text",
                        "expectedFbUid": "page-1",
                        "content": {"body": "Second"},
                        "dryRun": True,
                    },
                ],
            },
        ]
    )

    session = await open_gateway_session(socket, "credential", "conn-1", [])
    results = await poll_gateway_dispatches(socket, session, limit=1)
    tasks = await crud.list_tasks()

    assert [result["dispatchId"] for result in results] == ["dispatch-limit-a"]
    assert len(tasks) == 1
    assert tasks[0]["ref_id"] == "zoopost:dispatch-limit-a"

@pytest.mark.asyncio
async def test_gateway_poll_reports_local_dispatch_failure(db):
    from agent.services.zoopost_cloud_agent import open_gateway_session, poll_gateway_dispatches

    socket = FakeCloudSocket(
        [
            {"type": "agent_hello_ack", "sessionId": "session-1", "sessionGeneration": 1, "connectionId": "conn-1"},
            {
                "type": "agent_dispatch_batch",
                "messageId": "poll-2",
                "dispatches": [
                    {
                        "type": "dispatch_publish_target",
                        "dispatchId": "dispatch-missing-account",
                        "platform": "facebook",
                        "channelType": "fanpage",
                        "platformTaskType": "facebook.post_text",
                        "expectedFbUid": "missing-page",
                        "content": {"body": "No local account"},
                        "dryRun": True,
                    }
                ],
            },
            {"type": "agent_dispatch_result_ack", "messageId": "result-3", "targetId": "target-1"},
        ]
    )

    session = await open_gateway_session(socket, "credential", "conn-1", [])
    results = await poll_gateway_dispatches(socket, session)
    failure_message = socket.sent[2]

    assert results[0]["dispatchId"] == "dispatch-missing-account"
    assert results[0]["failed"] is True
    assert failure_message["type"] == "agent_dispatch_result"
    assert failure_message["dispatchId"] == "dispatch-missing-account"
    assert failure_message["resultStatus"] == "failed"
    assert failure_message["errorCode"] == "local_dispatch_validation_failed"
    assert "expected facebook identity" in failure_message["errorMessage"]


@pytest.mark.asyncio
async def test_gateway_hello_preserves_explicit_empty_capabilities(db):
    from agent.services.zoopost_cloud_agent import open_gateway_session

    socket = FakeCloudSocket(
        [{"type": "agent_hello_ack", "sessionId": "session-1", "sessionGeneration": 1, "connectionId": "conn-1"}]
    )

    await open_gateway_session(socket, "credential", "conn-1", [], capabilities=[])

    assert socket.sent[0]["capabilities"] == []


@pytest.mark.asyncio
async def test_gateway_poll_reports_malformed_dispatch_content(db):
    from agent.db import crud
    from agent.services.zoopost_cloud_agent import open_gateway_session, poll_gateway_dispatches

    await crud.create_account("Page A", fb_uid="page-1")
    socket = FakeCloudSocket(
        [
            {"type": "agent_hello_ack", "sessionId": "session-1", "sessionGeneration": 1, "connectionId": "conn-1"},
            {
                "type": "agent_dispatch_batch",
                "messageId": "poll-2",
                "dispatches": [
                    {
                        "type": "dispatch_publish_target",
                        "dispatchId": "dispatch-bad-content",
                        "platform": "facebook",
                        "channelType": "fanpage",
                        "platformTaskType": "facebook.post_text",
                        "expectedFbUid": "page-1",
                        "content": ["not", "an", "object"],
                        "dryRun": True,
                    }
                ],
            },
            {"type": "agent_dispatch_result_ack", "messageId": "result-3", "targetId": "target-1"},
        ]
    )

    session = await open_gateway_session(socket, "credential", "conn-1", [])
    results = await poll_gateway_dispatches(socket, session)
    failure_message = socket.sent[2]

    assert results[0]["dispatchId"] == "dispatch-bad-content"
    assert results[0]["failed"] is True
    assert failure_message["resultStatus"] == "failed"
    assert failure_message["errorCode"] == "local_dispatch_validation_failed"
    assert "content" in failure_message["errorMessage"]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("payload", [], "payload"),
        ("content", "", "content"),
        ("media", "", "media"),
        ("content", {"body": ["not", "text"]}, "body"),
    ],
)
@pytest.mark.asyncio
async def test_gateway_poll_reports_malformed_falsy_dispatch_fields(db, field, value, message):
    from agent.db import crud
    from agent.services.zoopost_cloud_agent import open_gateway_session, poll_gateway_dispatches

    await crud.create_account("Page A", fb_uid="page-1")
    dispatch = {
        "type": "dispatch_publish_target",
        "dispatchId": f"dispatch-bad-{field}",
        "platform": "facebook",
        "channelType": "fanpage",
        "platformTaskType": "facebook.post_text",
        "expectedFbUid": "page-1",
        "content": {"body": "Valid body"},
        "dryRun": True,
    }
    dispatch[field] = value
    socket = FakeCloudSocket(
        [
            {"type": "agent_hello_ack", "sessionId": "session-1", "sessionGeneration": 1, "connectionId": "conn-1"},
            {"type": "agent_dispatch_batch", "messageId": "poll-2", "dispatches": [dispatch]},
            {"type": "agent_dispatch_result_ack", "messageId": "result-3", "targetId": "target-1"},
        ]
    )

    session = await open_gateway_session(socket, "credential", "conn-1", [])
    results = await poll_gateway_dispatches(socket, session)
    failure_message = socket.sent[2]

    assert results[0]["failed"] is True
    assert failure_message["resultStatus"] == "failed"
    assert failure_message["errorCode"] == "local_dispatch_validation_failed"
    assert message in failure_message["errorMessage"]


@pytest.mark.asyncio
async def test_gateway_result_message_matches_cloud_contract(db):
    from agent.db import crud
    from agent.services.zoopost_cloud_agent import open_gateway_session, send_gateway_task_result

    account = await crud.create_account("Page A", fb_uid="page-1")
    task = await crud.create_task(
        account["id"],
        "POST_TEXT",
        payload={"dryRun": True, "content": "Done"},
        ref_id="zoopost:dispatch-result-send",
    )
    task = await crud.update_task(task["id"], status="COMPLETED", result=json.dumps({"externalPostId": "post-1"}))
    socket = FakeCloudSocket(
        [
            {"type": "agent_hello_ack", "sessionId": "session-1", "sessionGeneration": 1, "connectionId": "conn-1"},
            {"type": "agent_dispatch_result_ack", "messageId": "result-2", "targetId": "target-1"},
        ]
    )

    session = await open_gateway_session(socket, "credential", "conn-1", [])
    ack = await send_gateway_task_result(socket, session, "dispatch-result-send", task)
    result_message = socket.sent[1]

    assert ack["type"] == "agent_dispatch_result_ack"
    assert result_message["type"] == "agent_dispatch_result"
    assert result_message["sessionId"] == "session-1"
    assert result_message["dispatchId"] == "dispatch-result-send"
    assert result_message["resultStatus"] == "posted"
    assert result_message["externalPostId"] == "post-1"
    assert "localTaskId" not in result_message
