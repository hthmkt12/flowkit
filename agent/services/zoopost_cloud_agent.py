"""ZooPost cloud dispatch adapter for local FBKit tasks."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse

import aiosqlite
import websockets

from agent import config
from agent.db import crud
from agent.services.fb_client import get_fb_client
from agent.services.safety_gate import strip_server_owned_payload_fields

DISPATCH_REF_PREFIX = "zoopost:"
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
logger = logging.getLogger(__name__)


@dataclass
class GatewayConnectionState:
    connection_id: str
    next_hello_sequence: int = 1


@dataclass
class GatewaySession:
    session_id: str
    session_generation: int
    connection_id: str
    sequence: int = 1

    def next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence


async def run_gateway_loop():
    if not config.ZOOPOST_CLOUD_API_URL or not config.ZOOPOST_AGENT_CREDENTIAL:
        return
    state = GatewayConnectionState(connection_id=_gateway_connection_id(), next_hello_sequence=_initial_gateway_sequence())
    while True:
        try:
            await _run_gateway_session(state)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("ZooPost gateway loop disconnected")
            await asyncio.sleep(config.ZOOPOST_GATEWAY_POLL_INTERVAL)



async def _run_gateway_session(state: GatewayConnectionState):
    ws_url = _gateway_ws_url(config.ZOOPOST_CLOUD_API_URL)
    async with websockets.connect(ws_url) as websocket:
        hello_sequence = state.next_hello_sequence
        state.next_hello_sequence = hello_sequence + 1
        session = await open_gateway_session(
            websocket,
            config.ZOOPOST_AGENT_CREDENTIAL,
            state.connection_id,
            _connected_profiles(),
            sequence=hello_sequence,
            live_guard_enabled=False,
        )
        _sync_gateway_sequence(state, session)
        logger.info("ZooPost gateway connected")
        pending_dispatches: dict[str, str] = {}
        while True:
            try:
                await heartbeat_gateway_session(websocket, session, _connected_profiles(), live_guard_enabled=False)
            finally:
                _sync_gateway_sequence(state, session)
            try:
                await _report_terminal_results(websocket, session, pending_dispatches)
            finally:
                _sync_gateway_sequence(state, session)
            try:
                await _report_recovered_terminal_results(websocket, session)
            finally:
                _sync_gateway_sequence(state, session)
            try:
                results = await poll_gateway_dispatches(websocket, session, limit=config.ZOOPOST_GATEWAY_DISPATCH_LIMIT)
            finally:
                _sync_gateway_sequence(state, session)
            for result in results:
                dispatch_id = result.get("dispatchId")
                task_id = result.get("localTaskId")
                if isinstance(dispatch_id, str) and isinstance(task_id, str):
                    pending_dispatches[dispatch_id] = task_id
            try:
                await _report_terminal_results(websocket, session, pending_dispatches)
            finally:
                _sync_gateway_sequence(state, session)
            try:
                await _report_recovered_terminal_results(websocket, session)
            finally:
                _sync_gateway_sequence(state, session)
            await asyncio.sleep(config.ZOOPOST_GATEWAY_POLL_INTERVAL)

def _sync_gateway_sequence(state: GatewayConnectionState, session: GatewaySession):
    state.next_hello_sequence = max(state.next_hello_sequence, session.sequence + 1)


async def _report_terminal_results(websocket, session: GatewaySession, pending_dispatches: dict[str, str]):
    for dispatch_id, task_id in list(pending_dispatches.items()):
        task = await crud.get_task(task_id)
        if task and task.get("status") in TERMINAL_STATUS_MAP:
            if not _task_result_reported(task):
                await send_gateway_task_result(websocket, session, dispatch_id, task)
                await _mark_task_result_reported(task)
            pending_dispatches.pop(dispatch_id, None)


async def _report_recovered_terminal_results(websocket, session: GatewaySession):
    for task in await crud.list_terminal_zoopost_tasks(limit=config.ZOOPOST_GATEWAY_DISPATCH_LIMIT):
        if _task_result_reported(task):
            continue
        dispatch_id = _dispatch_id_from_ref(task.get("ref_id"))
        if dispatch_id:
            await send_gateway_task_result(websocket, session, dispatch_id, task)
            await _mark_task_result_reported(task)


async def _mark_task_result_reported(task: dict[str, Any]):
    result = _task_result(task)
    result["zoopostResultReported"] = True
    await crud.update_task(task["id"], result=json.dumps(result))


def _task_result_reported(task: dict[str, Any]) -> bool:
    return _task_result(task).get("zoopostResultReported") is True


def _dispatch_id_from_ref(ref_id: Any) -> str | None:
    if not isinstance(ref_id, str) or not ref_id.startswith(DISPATCH_REF_PREFIX):
        return None
    dispatch_id = ref_id[len(DISPATCH_REF_PREFIX):]
    return dispatch_id or None


def _gateway_connection_id() -> str:
    if config.ZOOPOST_AGENT_INSTALLATION_ID:
        return f"fbkit-installation-{config.ZOOPOST_AGENT_INSTALLATION_ID}"
    return f"fbkit-{config.FBKIT_NODE_ID}"


def _initial_gateway_sequence() -> int:
    return time.time_ns() // 1000


def _connected_profiles() -> list[dict[str, Any]]:
    profiles = []
    for session in get_fb_client().ws_stats.get("sessions", []):
        if session.get("logged_in") and session.get("fb_uid"):
            profiles.append({"platform": "facebook", "channel_type": "profile", "external_id": str(session["fb_uid"])})
    return profiles


def _gateway_ws_url(cloud_api_url: str) -> str:
    parsed = urlparse(cloud_api_url.rstrip("/"))
    if parsed.scheme in {"https", "wss"}:
        scheme = "wss"
    elif parsed.scheme in {"http", "ws"} and _is_loopback_host(parsed.hostname):
        scheme = "ws"
    else:
        raise ValueError("ZooPost cloud gateway requires https/wss unless using localhost")
    return urlunparse((scheme, parsed.netloc, "/agent-gateway/ws", "", "", ""))


def _is_loopback_host(hostname: str | None) -> bool:
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(hostname or "").is_loopback
    except ValueError:
        return False


async def open_gateway_session(
    websocket,
    credential: str,
    connection_id: str,
    connected_profiles: list[dict[str, Any]],
    *,
    capabilities: list[dict[str, Any]] | None = None,
    sequence: int = 1,
    live_guard_enabled: bool = False,
) -> GatewaySession:
    await _send_json(
        websocket,
        {
            "type": "agent_hello",
            "messageId": _message_id("hello"),
            "timestamp": _timestamp(),
            "sequence": sequence,
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
        sequence=sequence,
    )


async def heartbeat_gateway_session(
    websocket,
    session: GatewaySession,
    connected_profiles: list[dict[str, Any]],
    *,
    live_guard_enabled: bool = False,
):
    await _send_json(
        websocket,
        {
            "type": "agent_heartbeat",
            "messageId": _message_id("heartbeat"),
            "sessionId": session.session_id,
            "timestamp": _timestamp(),
            "sequence": session.next_sequence(),
            "capabilities": DEFAULT_CAPABILITIES,
            "connectedProfiles": connected_profiles,
            "liveGuardEnabled": live_guard_enabled,
        },
    )
    ack = await _receive_json(websocket)
    if ack.get("type") != "agent_heartbeat_ack":
        raise ValueError("cloud gateway rejected heartbeat")


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
    channel_type = dispatch.get("channelType")
    if channel_type not in CHANNEL_TYPES:
        raise ValueError("unsupported facebook channel type")
    if _has_live_intent(dispatch) and channel_type != "fanpage":
        raise ValueError("cloud live intent is fanpage-only")

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
    if _has_live_intent(dispatch):
        payload["zoopostLiveIntent"] = True
        payload["localApprovalRequired"] = True
    if media:
        payload["zoopostMediaRefs"] = media
    if dispatch.get("target"):
        payload["target"] = dispatch["target"]
    return payload


def _has_live_intent(dispatch: dict[str, Any]) -> bool:
    payload = dispatch.get("payload")
    return dispatch.get("dryRun") is False or (isinstance(payload, dict) and payload.get("dryRun") is False)


def _optional_field(data: dict[str, Any], field: str, default: Any) -> Any:
    value = data.get(field, default)
    return default if value is None else value


def _strip_server_fields(payload: dict[str, Any]) -> dict[str, Any]:
    return strip_server_owned_payload_fields(payload)


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
    return json.loads(await asyncio.wait_for(websocket.recv(), timeout=config.ZOOPOST_GATEWAY_ACK_TIMEOUT))


def _message_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


def _timestamp() -> int:
    return int(time.time())
