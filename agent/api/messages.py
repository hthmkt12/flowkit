"""FBKit — Message API routes (Phase 2 Enhanced)."""
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from agent.db import crud
from agent.services.safety_gate import enforce_payload

router = APIRouter(prefix="/messages", tags=["messages"])


class MessageCreate(BaseModel):
    account_id: str
    recipient_name: str
    recipient_uid: Optional[str] = None
    content: str
    media_path: Optional[str] = None
    scheduled_at: Optional[str] = None
    auto_queue: Optional[bool] = True


class BulkMessageCreate(BaseModel):
    account_id: str
    recipients: list[dict]  # [{name, uid?}]
    content: str
    media_path: Optional[str] = None
    auto_queue: Optional[bool] = True


class MessageUpdate(BaseModel):
    content: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_uid: Optional[str] = None
    media_path: Optional[str] = None
    status: Optional[str] = None
    scheduled_at: Optional[str] = None


@router.get("")
async def list_messages(account_id: str = None, status: str = None):
    return await crud.list_messages(account_id=account_id, status=status)


@router.post("")
async def create_message(body: MessageCreate):
    kwargs = {}
    if body.recipient_uid:
        kwargs["recipient_uid"] = body.recipient_uid
    if body.media_path:
        kwargs["media_path"] = body.media_path
    if body.scheduled_at:
        kwargs["scheduled_at"] = body.scheduled_at
        kwargs["status"] = "SCHEDULED"

    msg = await crud.create_message(
        account_id=body.account_id,
        recipient_name=body.recipient_name,
        content=body.content,
        **kwargs,
    )

    # Auto-queue task
    if body.auto_queue and not body.scheduled_at:
        payload = {
            "recipientName": body.recipient_name,
            "recipientUid": body.recipient_uid,
            "content": body.content,
            "mediaPath": body.media_path,
        }
        payload = enforce_payload("SEND_MESSAGE", payload)
        await crud.create_task(
            account_id=body.account_id,
            task_type="SEND_MESSAGE",
            payload=json.dumps(payload),
            ref_id=msg["id"],
        )
        msg = await crud.update_message(msg["id"], status="PENDING")

    return msg


@router.post("/bulk")
async def create_bulk_messages(body: BulkMessageCreate):
    """Create messages for multiple recipients (queued with delays)."""
    created = []
    for recipient in body.recipients:
        msg = await crud.create_message(
            account_id=body.account_id,
            recipient_name=recipient.get("name", ""),
            content=body.content,
            recipient_uid=recipient.get("uid"),
            media_path=body.media_path,
        )
        created.append(msg)

    # Create a single bulk task if auto_queue
    if body.auto_queue:
        payload = {
            "recipients": body.recipients,
            "content": body.content,
            "mediaPath": body.media_path,
        }
        payload = enforce_payload("SEND_BULK_MESSAGE", payload)
        await crud.create_task(
            account_id=body.account_id,
            task_type="SEND_BULK_MESSAGE",
            payload=json.dumps(payload),
        )

    return {"count": len(created), "messages": created}


@router.get("/scheduled")
async def list_scheduled_messages():
    """Get all messages that are scheduled (waiting to be sent)."""
    return await crud.list_scheduled_messages()


@router.get("/{message_id}")
async def get_message(message_id: str):
    msg = await crud.get_message(message_id)
    if not msg:
        raise HTTPException(404, "Message not found")
    return msg


@router.patch("/{message_id}")
async def update_message(message_id: str, body: MessageUpdate):
    """Update a message's content, schedule, or status."""
    existing = await crud.get_message(message_id)
    if not existing:
        raise HTTPException(404, "Message not found")

    kwargs = body.model_dump(exclude_none=True)
    msg = await crud.update_message(message_id, **kwargs)
    return msg


@router.delete("/{message_id}")
async def delete_message(message_id: str):
    ok = await crud.delete_message(message_id)
    if not ok:
        raise HTTPException(404, "Message not found")
    return {"ok": True}
