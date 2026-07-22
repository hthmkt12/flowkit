"""FBKit — Safety Gate v1.

Centralizes mutation classification and dry-run enforcement so API creation,
worker dispatch, and future task producers apply the same safety defaults.
"""

from __future__ import annotations

from copy import deepcopy
import re
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

    if safe_payload.get("targetType") == "GROUP":
        group_url = safe_payload.get("groupUrl")
        if not group_url or not isinstance(group_url, str) or not group_url.strip():
            target_id = safe_payload.get("targetId")
            if target_id:
                safe_payload["groupUrl"] = f"https://facebook.com/groups/{target_id}"
            else:
                raise ValueError("group targetType requires a non-empty groupUrl or targetId")
    elif safe_payload.get("targetType") == "PAGE":
        target_id = safe_payload.get("targetId")
        if not isinstance(target_id, str) or not target_id.strip():
            raise ValueError("page targetType requires a non-empty targetId")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", target_id.strip()):
            raise ValueError("page targetType targetId must be a Facebook page id or slug")
    elif safe_payload.get("targetType") == "POST":
        post_url = safe_payload.get("postUrl")
        if not post_url or not isinstance(post_url, str) or not post_url.strip():
            raise ValueError("post targetType requires a non-empty postUrl")
    elif safe_payload.get("targetType") == "LEAD":
        profile_url = safe_payload.get("profileUrl")
        if not profile_url or not isinstance(profile_url, str) or not profile_url.strip():
            raise ValueError("lead targetType requires a non-empty profileUrl")

    if not config.LIVE_ACTIONS_ENABLED:
        safe_payload["dryRun"] = True
        safe_payload.setdefault("safetyReason", "live_actions_disabled")
        return safe_payload

    local_approval = truthy(safe_payload.get("localApprovalRequired", True))
    if config.APPROVAL_REQUIRED and local_approval and not truthy(safe_payload.get("_serverApproved")):
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
