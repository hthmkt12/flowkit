"""FBKit — Safety Gate v1.

Centralizes mutation classification and dry-run enforcement so API creation,
worker dispatch, and future task producers apply the same safety defaults.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from agent import config


SERVER_OWNED_PAYLOAD_FIELDS = {
    "_serverApproved",
    "serverApproved",
    "_liveArmId",
    "liveArmId",
    "live_arm_id",
    "_quotaReserved",
    "quotaReserved",
    "approved",
}

MUTATING_TASK_TYPES = {
    "POST_TEXT",
    "POST_IMAGE",
    "POST_VIDEO",
    "POST_LINK",
    "POST_STORY",
    "POST_REEL",
    "REUP_VIDEO",
    "SEND_MESSAGE",
    "SEND_BULK_MESSAGE",
    "LIKE_POST",
    "COMMENT_POST",
    "SHARE_POST",
    "ADD_FRIEND",
    "ACCEPT_FRIEND",
    "JOIN_GROUP",
    "LEAVE_GROUP",
    "FOLLOW_PAGE",
    "UNFOLLOW_PAGE",
}


def strip_server_owned_payload_fields(payload: dict) -> dict:
    for field in SERVER_OWNED_PAYLOAD_FIELDS:
        payload.pop(field, None)
    return payload


def is_mutating_task(task_type: str) -> bool:
    """Return True when a task can alter Facebook state or contact people."""
    return task_type.upper() in MUTATING_TASK_TYPES


def truthy(value: Any) -> bool:
    """Interpret booleans and common string flags safely."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def enforce_payload(task_type: str, payload: dict | None) -> dict:
    """Return a payload copy with Safety Gate defaults applied.

    Read-only tasks are returned unchanged. Mutating tasks are forced to
    dry-run when live actions are globally disabled, and otherwise follow the
    default dry-run / explicit approval policy.
    """
    safe_payload = deepcopy(payload or {})
    if not is_mutating_task(task_type):
        return safe_payload

    if not config.LIVE_ACTIONS_ENABLED:
        safe_payload["dryRun"] = True
        safe_payload.setdefault("safetyReason", "live_actions_disabled")
        return safe_payload

    if config.APPROVAL_REQUIRED and not truthy(safe_payload.get("_serverApproved")):
        safe_payload["dryRun"] = True
        safe_payload.setdefault("safetyReason", "approval_required")
        return safe_payload

    if "dryRun" not in safe_payload:
        safe_payload["dryRun"] = bool(config.DRY_RUN_DEFAULT)
        if safe_payload["dryRun"]:
            safe_payload.setdefault("safetyReason", "dry_run_default")

    return safe_payload


def dry_run_from_payload(payload: dict | None) -> bool:
    """Read dry-run intent from an already safety-enforced payload."""
    return truthy((payload or {}).get("dryRun"))
