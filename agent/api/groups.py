"""FBKit — Groups API routes (Phase 3)."""
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from agent.db import crud
from agent.db.schema import get_db

router = APIRouter(prefix="/groups", tags=["groups"])


class GroupCreate(BaseModel):
    account_id: str
    name: str
    group_fb_id: Optional[str] = None
    url: Optional[str] = None
    member_count: Optional[int] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    member_count: Optional[int] = None
    status: Optional[str] = None


class GroupAction(BaseModel):
    account_id: str
    group_url: str


# ─── CRUD ────────────────────────────────────────────────────

@router.get("")
async def list_groups(account_id: str = None, status: str = None):
    db = await get_db()
    query = "SELECT * FROM fb_group WHERE 1=1"
    params = []
    if account_id:
        query += " AND account_id = ?"
        params.append(account_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    cur = await db.execute(query, params)
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.post("")
async def create_group(body: GroupCreate):
    import uuid
    db = await get_db()
    group_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO fb_group (id, account_id, name, group_fb_id, url, member_count)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (group_id, body.account_id, body.name, body.group_fb_id, body.url, body.member_count)
    )
    await db.commit()
    cur = await db.execute("SELECT * FROM fb_group WHERE id = ?", (group_id,))
    return dict(await cur.fetchone())


@router.get("/{group_id}")
async def get_group(group_id: str):
    db = await get_db()
    cur = await db.execute("SELECT * FROM fb_group WHERE id = ?", (group_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Group not found")
    return dict(row)


@router.patch("/{group_id}")
async def update_group(group_id: str, body: GroupUpdate):
    db = await get_db()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "No fields to update")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [group_id]
    await db.execute(
        f"UPDATE fb_group SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
        values,
    )
    await db.commit()
    cur = await db.execute("SELECT * FROM fb_group WHERE id = ?", (group_id,))
    return dict(await cur.fetchone())


@router.delete("/{group_id}")
async def delete_group(group_id: str):
    db = await get_db()
    cur = await db.execute("DELETE FROM fb_group WHERE id = ?", (group_id,))
    await db.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "Group not found")
    return {"ok": True}


# ─── Actions ─────────────────────────────────────────────────

@router.post("/join")
async def join_group(body: GroupAction):
    """Create a task to join a Facebook group."""
    payload = {"groupUrl": body.group_url}
    task = await crud.create_task(
        account_id=body.account_id,
        task_type="JOIN_GROUP",
        payload=json.dumps(payload),
    )
    return task


@router.post("/leave")
async def leave_group(body: GroupAction):
    """Create a task to leave a Facebook group."""
    payload = {"groupUrl": body.group_url}
    task = await crud.create_task(
        account_id=body.account_id,
        task_type="LEAVE_GROUP",
        payload=json.dumps(payload),
    )
    return task


@router.post("/scrape")
async def scrape_group(body: GroupAction):
    """Create a task to scrape group members."""
    payload = {"groupUrl": body.group_url}
    task = await crud.create_task(
        account_id=body.account_id,
        task_type="SCRAPE_GROUP",
        payload=json.dumps(payload),
    )
    return task
