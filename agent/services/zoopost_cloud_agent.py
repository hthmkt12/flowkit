"""ZooPost cloud dispatch adapter for local FBKit tasks."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

import aiosqlite

from agent.db import crud

DISPATCH_REF_PREFIX = "zoopost:"
SERVER_OWNED_FIELDS = {
    "_serverApproved",
    "serverApproved",
    "_liveArmId",
    "liveArmId",
    "live_arm_id",
    "_quotaReserved",
    "quotaReserved",
    "approved",
}
MEDIA_PATH_FIELDS = {"path", "local_path", "localPath", "mediaPath", "mediaPaths", "filePath", "file_path"}
TASK_TYPE_MAP = {
    "facebook.post_text": "POST_TEXT",
    "facebook.post_image": "POST_IMAGE",
    "facebook.post_video": "POST_VIDEO",
    "facebook.post_link": "POST_LINK",
    "facebook.reup_video": "REUP_VIDEO",
}
CHANNEL_TYPES = {"fanpage", "profile", "group"}
DEFAULT_CAPABILITIES = [{"name": "publish-dry-run"}]
TERMINAL_STATUS_MAP = {
    "COMPLETED": "posted",
    "FAILED": "failed",
    "CANCELLED": "failed",
}


@dataclass
class GatewaySession:
    session_id: str
    session_generation: int
    connection_id: str
    sequence: int = 1

    def next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence


async def open_gateway_session(
    websocket,
    credential: str,
    connection_id: str,
    connected_profiles: list[dict[str, Any]],
    *,
    capabilities: list[dict[str, Any]] | None = None,
    live_guard_enabled: bool = False,
) -> GatewaySession:
    await _send_json(
        websocket,
        {
            "type": "agent_hello",
            "messageId": _message_id("hello"),
            "timestamp": _timestamp(),
            "sequence": 1,
            "credential": credential,
            "connectionId": connection_id,
            "capabilities": DEFAULT_CAPABILITIES if capabilities is None else capabilities,
            "connectedProfiles": connected_profiles,
            "liveGuardEnabled": live_guard_enabled,
        },
    )
    ack = await _receive_json(websocket)
    if ack.get("type") != "agent_hello_ack":
        raise ValueError("cloud gateway rejected hello")
    return GatewaySession(
        session_id=ack["sessionId"],
        session_generation=ack["sessionGeneration"],
        connection_id=ack["connectionId"],
    )


async def poll_gateway_dispatches(websocket, session: GatewaySession, *, limit: int = 10) -> list[dict[str, Any]]:
    await _send_json(
        websocket,
        {
            "type": "agent_dispatch_poll",
            "messageId": _message_id("poll"),
            "sessionId": session.session_id,
            "timestamp": _timestamp(),
            "sequence": session.next_sequence(),
            "limit": limit,
        },
    )
    batch = await _receive_json(websocket)
    if batch.get("type") != "agent_dispatch_batch":
        raise ValueError("cloud gateway did not return dispatch batch")
    results = []
    dispatches = batch.get("dispatches", [])
    if not isinstance(dispatches, list):
        raise ValueError("cloud gateway dispatch batch must be a list")
    for dispatch in dispatches[:limit]:
        dispatch_id = dispatch.get("dispatchId")
        try:
            if dispatch.get("type") != "dispatch_publish_target":
                raise ValueError("unsupported cloud dispatch message")
            results.append(await handle_dispatch(dispatch))
        except ValueError as exc:
            if not isinstance(dispatch_id, str) or not dispatch_id.strip():
                raise
            await _send_gateway_dispatch_failure(websocket, session, dispatch_id, exc)
            results.append({"dispatchId": dispatch_id, "failed": True, "error": str(exc)})
    return results


async def send_gateway_task_result(websocket, session: GatewaySession, dispatch_id: str, task: dict[str, Any]) -> dict[str, Any]:
    message = build_dispatch_result(dispatch_id, task)
    message.update(
        {
            "messageId": _message_id("result"),
            "sessionId": session.session_id,
            "timestamp": _timestamp(),
            "sequence": session.next_sequence(),
        }
    )
    await _send_json(websocket, message)
    ack = await _receive_json(websocket)
    if ack.get("type") != "agent_dispatch_result_ack":
        raise ValueError("cloud gateway rejected dispatch result")
    return ack


async def _send_gateway_dispatch_failure(websocket, session: GatewaySession, dispatch_id: str, error: Exception) -> dict[str, Any]:
    await _send_json(
        websocket,
        {
            "type": "agent_dispatch_result",
            "messageId": _message_id("result"),
            "sessionId": session.session_id,
            "timestamp": _timestamp(),
            "sequence": session.next_sequence(),
            "dispatchId": dispatch_id,
            "resultStatus": "failed",
            "errorCode": "local_dispatch_validation_failed",
            "errorMessage": str(error)[:1000],
        },
    )
    ack = await _receive_json(websocket)
    if ack.get("type") != "agent_dispatch_result_ack":
        raise ValueError("cloud gateway rejected dispatch result")
    return ack


async def handle_dispatch(dispatch: dict[str, Any]) -> dict[str, Any]:
    dispatch_id = _required_text(dispatch, "dispatchId")
    dispatch_ref = _dispatch_ref(dispatch_id)
    existing_task = await crud.get_task_by_ref_id(dispatch_ref)
    if existing_task:
        return {"dispatchId": dispatch_id, "localTaskId": existing_task["id"], "duplicate": True}

    if dispatch.get("platform") != "facebook":
        raise ValueError("only facebook dispatch is supported")
    if dispatch.get("channelType") not in CHANNEL_TYPES:
        raise ValueError("unsupported facebook channel type")

    task_type = TASK_TYPE_MAP.get(_required_text(dispatch, "platformTaskType"))
    if not task_type:
        raise ValueError("unsupported facebook task type")

    expected_fb_uid = _required_text(dispatch, "expectedFbUid")
    account = await _get_account_by_fb_uid(expected_fb_uid)
    if not account:
        raise ValueError("expected facebook identity is not available locally")

    payload = _build_task_payload(dispatch, expected_fb_uid)
    try:
        task = await crud.create_task(
            account["id"],
            task_type,
            payload=payload,
            ref_id=dispatch_ref,
        )
    except aiosqlite.IntegrityError:
        await crud.rollback()
        task = await crud.get_task_by_ref_id(dispatch_ref)
        if task:
            return {"dispatchId": dispatch_id, "localTaskId": task["id"], "duplicate": True}
        raise
    return {"dispatchId": dispatch_id, "localTaskId": task["id"], "duplicate": False}


async def _get_account_by_fb_uid(expected_fb_uid: str) -> dict[str, Any] | None:
    for account in await crud.list_accounts():
        if account.get("fb_uid") == expected_fb_uid:
            return account
    return None


def _build_task_payload(dispatch: dict[str, Any], expected_fb_uid: str) -> dict[str, Any]:
    raw_payload = _optional_field(dispatch, "payload", {})
    if not isinstance(raw_payload, dict):
        raise ValueError("cloud dispatch payload must be an object")
    payload = _strip_server_fields(dict(raw_payload))
    content = _optional_field(dispatch, "content", {})
    if not isinstance(content, dict):
        raise ValueError("cloud dispatch content must be an object")
    body = content.get("body", "")
    if not isinstance(body, str):
        raise ValueError("cloud dispatch content body must be text")
    media = _optional_field(dispatch, "media", [])
    _reject_worker_media_payload(payload)
    _reject_filesystem_media_paths(media)

    payload.update(
        {
            "dryRun": True,
            "content": body,
            "expectedFbUid": expected_fb_uid,
        }
    )
    if media:
        payload["zoopostMediaRefs"] = media
    if dispatch.get("target"):
        payload["target"] = dispatch["target"]
    return payload


def _optional_field(data: dict[str, Any], field: str, default: Any) -> Any:
    value = data.get(field, default)
    return default if value is None else value


def _strip_server_fields(payload: dict[str, Any]) -> dict[str, Any]:
    for field in SERVER_OWNED_FIELDS:
        payload.pop(field, None)
    return payload


def _reject_worker_media_payload(value: Any):
    if isinstance(value, dict):
        if MEDIA_PATH_FIELDS & set(value):
            raise ValueError("cloud dispatch media must use opaque local media refs")
        for nested in value.values():
            _reject_worker_media_payload(nested)
    elif isinstance(value, list):
        for item in value:
            _reject_worker_media_payload(item)


def _reject_filesystem_media_paths(media: Any):
    if media is None:
        return
    if not isinstance(media, list):
        raise ValueError("cloud dispatch media must use opaque local media refs")
    for item in media:
        if isinstance(item, str):
            raise ValueError("cloud dispatch media must use opaque local media refs")
        if not isinstance(item, dict):
            raise ValueError("cloud dispatch media must use opaque local media refs")
        if MEDIA_PATH_FIELDS & set(item):
            raise ValueError("cloud dispatch media must use opaque local media refs")
        if not any(isinstance(item.get(field), str) and item[field].strip() for field in ("ref", "id", "localRef")):
            raise ValueError("cloud dispatch media must use opaque local media refs")


def _required_text(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing {field}")
    return value


def _dispatch_ref(dispatch_id: str) -> str:
    return f"{DISPATCH_REF_PREFIX}{dispatch_id}"


def build_dispatch_result(dispatch_id: str, task: dict[str, Any]) -> dict[str, Any]:
    task_status = task.get("status")
    if task_status not in TERMINAL_STATUS_MAP:
        raise ValueError("task has no terminal dispatch result")
    message = {
        "type": "agent_dispatch_result",
        "dispatchId": dispatch_id,
        "resultStatus": TERMINAL_STATUS_MAP[task_status],
    }
    result = _task_result(task)
    if result.get("externalPostId"):
        message["externalPostId"] = result["externalPostId"]
    if result.get("externalPostUrl"):
        message["externalPostUrl"] = result["externalPostUrl"]
    if task.get("error_message"):
        message["errorMessage"] = task["error_message"]
    return message


def _task_result(task: dict[str, Any]) -> dict[str, Any]:
    try:
        result = json.loads(task.get("result") or "{}")
    except json.JSONDecodeError:
        return {}
    return result if isinstance(result, dict) else {}


async def _send_json(websocket, payload: dict[str, Any]):
    await websocket.send(json.dumps(payload, separators=(",", ":")))


async def _receive_json(websocket) -> dict[str, Any]:
    return json.loads(await websocket.recv())


def _message_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


def _timestamp() -> int:
    return int(time.time())
