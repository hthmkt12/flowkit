"""FBKit — Task API routes."""
import json
from json import JSONDecodeError
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from agent import config
from agent.db import crud
from agent.services.safety_gate import enforce_payload

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _strip_external_server_fields(payload: dict) -> dict:
    payload.pop("_quotaReserved", None)
    payload.pop("_serverApproved", None)
    payload.pop("approved", None)
    return payload


class TaskCreate(BaseModel):
    account_id: str
    task_type: str
    payload: Optional[dict] = None
    ref_id: Optional[str] = None
    priority: Optional[int] = 0
    scheduled_at: Optional[str] = None
    max_retries: Optional[int] = 3


class EngagementCreate(BaseModel):
    """Quick endpoint for engagement tasks (like, comment, share)."""
    account_id: str
    post_url: str
    action: str  # LIKE, COMMENT, SHARE
    reaction: Optional[str] = "LIKE"
    comment: Optional[str] = None
    target_type: Optional[str] = "TIMELINE"


@router.get("")
async def list_tasks(status: str = None, task_type: str = None, account_id: str = None):
    return await crud.list_tasks(status=status, task_type=task_type, account_id=account_id)


@router.get("/stats")
async def task_stats(account_id: str = None):
    """Get aggregated task statistics by status."""
    return await crud.get_task_stats(account_id=account_id)


@router.get("/pending/count")
async def pending_count():
    tasks = await crud.list_tasks(status="PENDING")
    return {"count": len(tasks)}


@router.post("")
async def create_task(body: TaskCreate):
    kwargs = {}
    payload = _strip_external_server_fields(dict(body.payload or {}))
    payload = enforce_payload(body.task_type, payload)
    if payload:
        kwargs["payload"] = json.dumps(payload)
    if body.ref_id:
        kwargs["ref_id"] = body.ref_id
    if body.priority:
        kwargs["priority"] = body.priority
    if body.scheduled_at:
        kwargs["scheduled_at"] = body.scheduled_at
    if body.max_retries is not None:
        kwargs["max_retries"] = body.max_retries
    return await crud.create_task(
        account_id=body.account_id,
        task_type=body.task_type,
        **kwargs,
    )


@router.post("/{task_id}/approve")
async def approve_task(task_id: str):
    task = await crud.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.get("status") != "PENDING":
        raise HTTPException(409, "Only PENDING tasks can be approved")
    if not config.LIVE_ACTIONS_ENABLED:
        raise HTTPException(
            409,
            "Live actions are disabled (LIVE_ACTIONS_ENABLED=false); approval cannot enable live dispatch",
        )

    try:
        payload = json.loads(task.get("payload") or "{}") if task.get("payload") else {}
    except JSONDecodeError:
        raise HTTPException(400, "Task payload is not valid JSON")
    payload.pop("safetyReason", None)
    payload["_serverApproved"] = True
    payload["dryRun"] = False
    payload = enforce_payload(task["task_type"], payload)
    approved_task = await crud.approve_pending_task(task_id, json.dumps(payload))
    if not approved_task:
        raise HTTPException(409, "Only PENDING tasks can be approved")
    if task.get("account_id"):
        await crud.log_activity(
            task["account_id"],
            "APPROVE_TASK",
            f"Approved task {task_id[:8]} ({task.get('task_type')}) for live dispatch",
        )
    return approved_task


@router.post("/engage")
async def create_engagement(body: EngagementCreate):
    """Quick endpoint to create engagement tasks."""
    action = body.action.upper()

    if action == "LIKE":
        task_type = "LIKE_POST"
        payload = {"postUrl": body.post_url, "reaction": body.reaction or "LIKE"}
    elif action == "COMMENT":
        if not body.comment:
            raise HTTPException(400, "Comment text is required for COMMENT action")
        task_type = "COMMENT_POST"
        payload = {"postUrl": body.post_url, "comment": body.comment}
    elif action == "SHARE":
        task_type = "SHARE_POST"
        payload = {
            "postUrl": body.post_url,
            "comment": body.comment or "",
            "targetType": body.target_type or "TIMELINE",
        }
    else:
        raise HTTPException(400, f"Unknown action: {action}. Use LIKE, COMMENT, or SHARE")

    payload = enforce_payload(task_type, payload)

    return await crud.create_task(
        account_id=body.account_id,
        task_type=task_type,
        payload=json.dumps(payload),
    )


@router.get("/{task_id}")
async def get_task(task_id: str):
    task = await crud.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    result = await crud.cancel_task(task_id)
    if not result:
        raise HTTPException(404, "Task not found")
    return result


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    ok = await crud.delete_task(task_id)
    if not ok:
        raise HTTPException(404, "Task not found")
    return {"ok": True}
