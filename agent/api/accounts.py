"""FBKit — Account API routes."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from agent.db import crud
from agent.services.fb_client import get_fb_client

router = APIRouter(prefix="/accounts", tags=["accounts"])


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


@router.get("")
async def list_accounts(status: str = None):
    return await crud.list_accounts(status=status)


@router.get("/activity")
async def list_all_activities(limit: int = 100):
    """All activity logs across all accounts."""
    return await crud.list_activities(limit=limit)


@router.get("/extension-status")
async def get_extension_status():
    """Return which fb_uids currently have a live extension session.

    Dashboard uses this to show 🟢/🔴 per account row.
    """
    client = get_fb_client()
    sessions = client.ws_stats["sessions"]
    online_uids = {s["fb_uid"] for s in sessions if s.get("fb_uid")}
    accounts = await crud.list_accounts()
    result = []
    for acc in accounts:
        fb_uid = acc.get("fb_uid")
        result.append({
            "id": acc["id"],
            "fb_uid": fb_uid,
            "extension_online": fb_uid in online_uids if fb_uid else False,
        })
    return {
        "sessions": sessions,
        "accounts": result,
        "total_sessions": len(sessions),
    }


@router.post("")
async def create_account(body: AccountCreate):
    kwargs = body.model_dump(exclude_none=True, exclude={"name"})
    return await crud.create_account(name=body.name, **kwargs)


@router.get("/{account_id}")
async def get_account(account_id: str):
    acc = await crud.get_account(account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    return acc


@router.patch("/{account_id}")
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
