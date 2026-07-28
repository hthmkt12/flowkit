"""FBKit — Post API routes (Phase 2 Enhanced)."""
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from agent.db import crud
from agent.services.safety_gate import enforce_payload

router = APIRouter(prefix="/posts", tags=["posts"])


class PostCreate(BaseModel):
    account_id: str
    post_type: Optional[str] = "TEXT"
    content: Optional[str] = None
    media_paths: Optional[list[str]] = None
    target_type: Optional[str] = "TIMELINE"
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    scheduled_at: Optional[str] = None
    auto_queue: Optional[bool] = True


class PostUpdate(BaseModel):
    content: Optional[str] = None
    media_paths: Optional[list[str]] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    status: Optional[str] = None
    scheduled_at: Optional[str] = None


class ReupVideoCreate(BaseModel):
    """Create a Reup Video task — downloads from source and posts as Reel."""
    account_id: str
    source_url: str
    content: Optional[str] = None
    target_id: Optional[str] = None  # Fanpage ID


@router.get("")
async def list_posts(account_id: str = None, status: str = None):
    return await crud.list_posts(account_id=account_id, status=status)


@router.post("")
async def create_post(body: PostCreate):
    kwargs = body.model_dump(exclude_none=True, exclude={"account_id", "post_type", "auto_queue"})
    if body.media_paths:
        kwargs["media_paths"] = json.dumps(body.media_paths)

    # Set status based on scheduling
    if body.scheduled_at:
        kwargs["status"] = "SCHEDULED"
    else:
        kwargs["status"] = "DRAFT"

    post = await crud.create_post(
        account_id=body.account_id,
        post_type=body.post_type,
        **kwargs,
    )

    # Auto-create a task if requested
    if body.auto_queue and not body.scheduled_at:
        task_type = f"POST_{body.post_type}"
        payload = {
            "content": body.content or "",
            "targetType": body.target_type or "TIMELINE",
            "targetId": body.target_id,
        }
        if body.media_paths:
            payload["mediaPaths"] = body.media_paths
        payload = enforce_payload(task_type, payload)

        await crud.create_task(
            account_id=body.account_id,
            task_type=task_type,
            payload=json.dumps(payload),
            ref_id=post["id"],
        )
        post = await crud.update_post(post["id"], status="SCHEDULED")

    return post


@router.post("/reup")
async def create_reup_post(body: ReupVideoCreate):
    """Create a video reup task — downloads video from URL and posts as Reel."""
    payload = {
        "sourceUrl": body.source_url,
        "content": body.content or "",
        "targetId": body.target_id,
    }
    payload = enforce_payload("REUP_VIDEO", payload)

    # Create a post record to track the reup
    post = await crud.create_post(
        account_id=body.account_id,
        post_type="REEL",
        content=body.content,
        target_type="REEL",
        target_id=body.target_id,
        status="SCHEDULED",
    )

    # Create the reup task
    task = await crud.create_task(
        account_id=body.account_id,
        task_type="REUP_VIDEO",
        payload=json.dumps(payload),
        ref_id=post["id"],
    )

    return {"post": post, "task": task}


@router.get("/scheduled")
async def list_scheduled_posts():
    """Get all posts that are scheduled (waiting to be posted)."""
    return await crud.list_scheduled_posts()


@router.post("/{post_id}/queue")
async def queue_post(post_id: str):
    """Queue one reviewed draft through the standard dry-run/approval gate."""
    post = await crud.get_post(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    if post.get("status") != "DRAFT":
        raise HTTPException(409, "Only DRAFT posts can be queued")

    task_type = f"POST_{post.get('post_type', 'TEXT')}"
    payload = {
        "content": post.get("content", ""),
        "targetType": post.get("target_type", "TIMELINE"),
        "targetId": post.get("target_id"),
    }
    if post.get("media_paths"):
        try:
            payload["mediaPaths"] = json.loads(post["media_paths"])
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(409, "Post media paths are unreadable")
    try:
        payload = enforce_payload(task_type, payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    queued_post = await crud.claim_draft_post_for_queue(post_id)
    if not queued_post:
        raise HTTPException(409, "Post was already queued or changed")
    try:
        task = await crud.create_task(
            account_id=queued_post["account_id"],
            task_type=task_type,
            payload=json.dumps(payload),
            ref_id=queued_post["id"],
        )
    except Exception:
        await crud.update_post(post_id, status="DRAFT")
        raise
    return {"post": queued_post, "task": task}


@router.get("/{post_id}")
async def get_post(post_id: str):
    post = await crud.get_post(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    return post


@router.patch("/{post_id}")
async def update_post(post_id: str, body: PostUpdate):
    """Update a post's content, schedule, or status."""
    existing = await crud.get_post(post_id)
    if not existing:
        raise HTTPException(404, "Post not found")

    kwargs = body.model_dump(exclude_none=True)
    if "media_paths" in kwargs and kwargs["media_paths"]:
        kwargs["media_paths"] = json.dumps(kwargs["media_paths"])

    post = await crud.update_post(post_id, **kwargs)
    return post


@router.delete("/{post_id}")
async def delete_post(post_id: str):
    ok = await crud.delete_post(post_id)
    if not ok:
        raise HTTPException(404, "Post not found")
    return {"ok": True}
