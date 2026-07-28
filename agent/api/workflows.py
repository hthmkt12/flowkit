"""Inspect-only local Workflow Lab API; capture start and event ingest are absent."""

from __future__ import annotations

import os
import hmac
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from agent.services.workflow_store import WorkflowStore
from agent.services.workflow_analyzer import analyze_replayability

router = APIRouter(prefix="/workflow-lab", tags=["workflow-lab"])
_store = WorkflowStore()


class WorkflowReview(BaseModel):
    decision: str = Field(pattern="^(accept|reject)$")
    note: str = Field(default="", max_length=500)


def _authorize(key: str | None) -> None:
    expected = os.environ.get("WORKFLOW_LAB_API_KEY", "").strip()
    if not expected or not key or not hmac.compare_digest(key, expected):
        raise HTTPException(401, "Workflow Lab key required")


@router.get("")
async def list_workflow_captures(profile_id: str | None = None, x_workflow_profile: str | None = Header(default=None), x_workflow_lab_key: str | None = Header(default=None)):
    _authorize(x_workflow_lab_key)
    if not profile_id or profile_id != x_workflow_profile:
        raise HTTPException(403, "Workflow profile scope required")
    return {"captures": _store.list_captures(profile_id)}


@router.get("/{capture_id}")
async def inspect_workflow_capture(capture_id: str, x_workflow_profile: str | None = Header(default=None), x_workflow_lab_key: str | None = Header(default=None)):
    _authorize(x_workflow_lab_key)
    capture = _store.inspect_capture(capture_id)
    if not capture or capture["profileId"] != x_workflow_profile:
        raise HTTPException(404, "Capture not found")
    return capture


@router.post("/{capture_id}/stop")
async def stop_workflow_capture(capture_id: str, x_workflow_profile: str | None = Header(default=None), x_workflow_lab_key: str | None = Header(default=None)):
    _authorize(x_workflow_lab_key)
    current = _store.inspect_capture(capture_id)
    if not current or current["profileId"] != x_workflow_profile:
        raise HTTPException(404, "Capture not found")
    return _store.stop_capture(capture_id)


@router.post("/{capture_id}/review")
async def review_workflow_capture(capture_id: str, body: WorkflowReview, x_workflow_profile: str | None = Header(default=None), x_workflow_lab_key: str | None = Header(default=None)):
    _authorize(x_workflow_lab_key)
    capture = _store.inspect_capture(capture_id)
    if not capture or capture["profileId"] != x_workflow_profile:
        raise HTTPException(404, "Capture not found")
    if body.decision == "accept":
        raise HTTPException(409, "Review cannot promote or execute a workflow in V1")
    return {"captureId": capture_id, "decision": "reject", "note": body.note[:500], "readOnly": True}


@router.get("/{capture_id}/analysis")
async def analyze_workflow_capture(capture_id: str, x_workflow_profile: str | None = Header(default=None), x_workflow_lab_key: str | None = Header(default=None)):
    _authorize(x_workflow_lab_key)
    capture = _store.inspect_capture(capture_id)
    if not capture or capture["profileId"] != x_workflow_profile:
        raise HTTPException(404, "Capture not found")
    return {"captureId": capture_id, **analyze_replayability(capture["events"])}


@router.delete("/{capture_id}")
async def delete_workflow_capture(capture_id: str, x_workflow_profile: str | None = Header(default=None), x_workflow_lab_key: str | None = Header(default=None)):
    _authorize(x_workflow_lab_key)
    capture = _store.inspect_capture(capture_id)
    if not capture or capture["profileId"] != x_workflow_profile or not _store.delete_capture(capture_id):
        raise HTTPException(404, "Capture not found")
    return {"ok": True, "logicalRetention": True}
