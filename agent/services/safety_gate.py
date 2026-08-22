"""FBKit — Safety Gate v1.

Centralizes mutation classification and dry-run enforcement so API creation,
worker dispatch, and future task producers apply the same safety defaults.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
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


@dataclass(frozen=True)
class LocalLiveReadiness:
    """Read-only S4 readiness result for one local live-dispatch snapshot.

    This is intentionally separate from :func:`enforce_payload`: evaluating
    readiness never changes payloads, flags, leases, sessions, or task state.
    Callers must re-evaluate the snapshot immediately before any future live
    dispatch and treat any failed condition as a hard stop.
    """

    satisfied: bool
    reasons: list[str] = field(default_factory=list)


def _parse_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def evaluate_local_live_conditions(
    *,
    account_id: str,
    task_type: str,
    account: dict | None,
    live_arm: dict | None,
    live_lease: dict | None,
    extension_session: dict | None,
    now: datetime | None = None,
) -> LocalLiveReadiness:
    """Evaluate the S4 local live guard without mutating runtime state.

    The snapshot must contain the server/local facts already known to the
    caller. Missing or malformed state fails closed. This function does not
    enable live actions and does not alter the existing dry-run path.
    """
    result = LocalLiveReadiness(satisfied=True)
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    if not config.LIVE_ACTIONS_ENABLED:
        result.reasons.append("live_actions_disabled")
    if not config.API_AUTH_ENABLED:
        result.reasons.append("api_auth_disabled")
    if not config.WS_AUTH_ENABLED:
        result.reasons.append("ws_auth_disabled")

    if not live_arm:
        result.reasons.append("active_live_arm_missing")
    else:
        if live_arm.get("revoked_at"):
            result.reasons.append("live_arm_revoked")
        arm_expires_at = _parse_utc(live_arm.get("expires_at"))
        if arm_expires_at is None or arm_expires_at <= current:
            result.reasons.append("live_arm_expired_or_invalid")
        arm_account_id = live_arm.get("account_id")
        if not arm_account_id or arm_account_id != account_id:
            result.reasons.append("live_arm_account_mismatch")
        allowed_types = {str(value).upper() for value in (live_arm.get("task_types") or [])}
        if task_type.upper() not in allowed_types:
            result.reasons.append("live_arm_task_type_not_allowed")

    account_fb_uid = (account or {}).get("fb_uid")
    if not account_fb_uid:
        result.reasons.append("account_fb_uid_missing")

    session_fb_uid = (extension_session or {}).get("fb_uid")
    if not session_fb_uid or not account_fb_uid or session_fb_uid != account_fb_uid:
        result.reasons.append("extension_account_identity_mismatch")

    if not live_lease:
        result.reasons.append("live_account_lease_missing")
    else:
        if live_lease.get("account_id") != account_id:
            result.reasons.append("live_account_lease_account_mismatch")
        lease_expires_at = _parse_utc(live_lease.get("expires_at"))
        if lease_expires_at is None or lease_expires_at <= current:
            result.reasons.append("live_account_lease_expired_or_invalid")

    if not extension_session:
        result.reasons.append("extension_session_missing")
    else:
        if extension_session.get("stale") is True:
            result.reasons.append("extension_session_stale")
        if extension_session.get("logged_in") is not True:
            result.reasons.append("extension_session_not_logged_in")
        if extension_session.get("checkpoint_warning") or extension_session.get("login_warning"):
            result.reasons.append("checkpoint_or_login_warning")
        if extension_session.get("extension_live_actions_enabled") is not True:
            result.reasons.append("extension_live_action_guard_disabled")

    if result.reasons:
        return LocalLiveReadiness(satisfied=False, reasons=result.reasons)
    return result


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


@dataclass(frozen=True)
class LiveAbortResult:
    """Read-only S5 abort decision for an already-live-intended task."""

    abort: bool
    reasons: list[str] = field(default_factory=list)


def evaluate_live_abort_conditions(
    *,
    account_id: str,
    expected_fb_uid: str | None,
    extension_session: dict | None,
    expected_target_url: str | None = None,
    current_url: str | None = None,
    selector_confident: bool | None = None,
    duplicate_content_risk: bool | None = None,
    post_may_have_succeeded: bool = False,
    now: datetime | None = None,
    heartbeat_max_age_s: int = 60,
) -> LiveAbortResult:
    """Fail-closed S5 abort checks for a live-only execution snapshot.

    ``None`` means the safety fact is unknown, not safe. This prevents a
    caller from accidentally treating missing browser/duplicate evidence as
    permission to continue a live mutation.
    """
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    reasons: list[str] = []

    if not account_id:
        reasons.append("account_identity_missing")

    if not expected_fb_uid:
        reasons.append("expected_fb_uid_missing")

    if not extension_session:
        reasons.append("extension_session_missing")
    else:
        session_fb_uid = extension_session.get("fb_uid")
        if not session_fb_uid or session_fb_uid != expected_fb_uid:
            reasons.append("unexpected_facebook_account")
        if extension_session.get("logged_in") is not True:
            reasons.append("facebook_login_warning")
        if extension_session.get("stale") is True:
            reasons.append("stale_extension_session")
        last_seen = extension_session.get("last_seen_at")
        if last_seen is None:
            age_s = extension_session.get("last_seen_age_s")
            if age_s is None or float(age_s) > heartbeat_max_age_s:
                reasons.append("missing_live_guard_heartbeat")
        else:
            parsed_last_seen = _parse_utc(last_seen)
            if parsed_last_seen is None or (current - parsed_last_seen).total_seconds() > heartbeat_max_age_s:
                reasons.append("missing_live_guard_heartbeat")
        if extension_session.get("checkpoint_warning") or extension_session.get("login_warning"):
            reasons.append("facebook_checkpoint_or_login_warning")
        if extension_session.get("extension_live_actions_enabled") is not True:
            reasons.append("extension_live_action_guard_disabled")

    if expected_target_url:
        if not current_url or current_url.rstrip("/") != expected_target_url.rstrip("/"):
            reasons.append("unexpected_page_or_target")

    if selector_confident is not True:
        reasons.append("selector_uncertainty")

    if duplicate_content_risk is not False:
        reasons.append("duplicate_content_risk_unknown_or_present")

    if post_may_have_succeeded:
        reasons.append("post_may_have_succeeded_no_retry")

    return LiveAbortResult(abort=bool(reasons), reasons=reasons)


def dry_run_from_payload(payload: dict | None) -> bool:
    """Read dry-run intent from an already safety-enforced payload."""
    return truthy((payload or {}).get("dryRun"))
