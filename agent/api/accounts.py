"""FBKit — Account API routes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from agent.db import crud
from agent.services.fb_client import get_fb_client

router = APIRouter(prefix="/accounts", tags=["accounts"])


# ─── Public response models (allowlisted; no secret material) ───────
# These typed DTOs are the only shape the HTTP boundary may return.
# Decrypted cookies/session live only in the internal CRUD repository.

class AccountPublic(BaseModel):
    """Allowlisted account fields. No cookies_data/session_data."""
    id: str
    name: str
    fb_uid: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    profile_url: Optional[str] = None
    avatar_url: Optional[str] = None
    notes: Optional[str] = None
    cookies_valid: Optional[int] = None
    last_active: Optional[str] = None
    daily_posts: Optional[int] = None
    daily_messages: Optional[int] = None
    daily_likes: Optional[int] = None
    daily_comments: Optional[int] = None
    daily_friends: Optional[int] = None
    daily_reset_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ExtensionSessionPublic(BaseModel):
    """Allowlisted extension telemetry. No cookies/session blobs."""
    fb_uid: Optional[str] = None
    logged_in: bool = False
    extension_live_actions_enabled: Optional[bool] = None
    profile_id: Optional[str] = None
    profile_name: Optional[str] = None
    uptime_s: Optional[int] = None
    last_seen_age_s: Optional[int] = None
    stale: Optional[bool] = None
    health: Optional[str] = None


class ExtensionStatusAccountPublic(BaseModel):
    id: str
    fb_uid: Optional[str] = None
    extension_online: bool = False
    extension_health: Optional[str] = None
    last_seen_age_s: Optional[int] = None
    profile_id: Optional[str] = None
    profile_name: Optional[str] = None
    extension_live_actions_enabled: Optional[bool] = None


class ExtensionStatusPublic(BaseModel):
    sessions: list[ExtensionSessionPublic] = []
    accounts: list[ExtensionStatusAccountPublic] = []
    total_sessions: int = 0


def _select_best_session_by_uid(sessions: list[dict], include_stale: bool) -> dict:
    candidates = [
        session
        for session in sessions
        if session.get("fb_uid") and (include_stale or not session.get("stale"))
    ]
    best_by_uid = {}
    for session in sorted(candidates, key=lambda s: s.get("last_seen_age_s") or 0):
        best_by_uid.setdefault(session["fb_uid"], session)
    return best_by_uid


class AccountCreate(BaseModel):
    name: str
    fb_uid: Optional[str] = None
    email: Optional[str] = None
    profile_url: Optional[str] = None
    notes: Optional[str] = None


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    fb_uid: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    profile_url: Optional[str] = None
    avatar_url: Optional[str] = None
    cookies_valid: Optional[bool] = None
    notes: Optional[str] = None


@router.get("", response_model=list[AccountPublic])
async def list_accounts(status: str = None):
    return await crud.list_accounts(status=status)


@router.get("/activity")
async def list_all_activities(limit: int = 100):
    """All activity logs across all accounts."""
    return await crud.list_activities(limit=limit)


@router.get("/extension-status", response_model=ExtensionStatusPublic)
async def get_extension_status():
    """Return which fb_uids currently have a live extension session.

    Dashboard uses this to show 🟢/🔴 per account row.
    """
    client = get_fb_client()
    sessions = client.ws_stats["sessions"]
    sessions_by_uid = _select_best_session_by_uid(sessions, include_stale=False)
    all_sessions_by_uid = _select_best_session_by_uid(sessions, include_stale=True)
    accounts = await crud.list_accounts()
    result = []
    for acc in accounts:
        fb_uid = acc.get("fb_uid")
        session = sessions_by_uid.get(fb_uid) or all_sessions_by_uid.get(fb_uid)
        result.append({
            "id": acc["id"],
            "fb_uid": fb_uid,
            "extension_online": bool(fb_uid and session and not session.get("stale")),
            "extension_health": session.get("health") if session else "offline",
            "last_seen_age_s": session.get("last_seen_age_s") if session else None,
            "profile_id": session.get("profile_id") if session else None,
            "profile_name": session.get("profile_name") if session else None,
            "extension_live_actions_enabled": session.get("extension_live_actions_enabled") if session else None,
        })
    return {
        "sessions": sessions,
        "accounts": result,
        "total_sessions": len(sessions),
    }


@router.post("", response_model=AccountPublic)
async def create_account(body: AccountCreate):
    kwargs = body.model_dump(exclude_none=True, exclude={"name"})
    return await crud.create_account(name=body.name, **kwargs)


@router.get("/{account_id}", response_model=AccountPublic)
async def get_account(account_id: str):
    acc = await crud.get_account(account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    return acc


@router.patch("/{account_id}", response_model=AccountPublic)
async def update_account(account_id: str, body: AccountUpdate):
    kwargs = body.model_dump(exclude_none=True)
    result = await crud.update_account(account_id, **kwargs)
    if not result:
        raise HTTPException(404, "Account not found")
    return result


@router.delete("/{account_id}")
async def delete_account(account_id: str):
    ok = await crud.delete_account(account_id)
    if not ok:
        raise HTTPException(404, "Account not found")
    return {"ok": True}


@router.get("/{account_id}/activities")
async def get_activities(account_id: str, limit: int = 50):
    return await crud.list_activities(account_id=account_id, limit=limit)


@router.get("/{account_id}/queue-summary")
async def get_account_queue_summary(account_id: str):
    return await crud.get_account_queue_summary(account_id)
