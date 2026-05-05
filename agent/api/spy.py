"""FBKit — Spy Ads API routes (Phase 3).

Monitor competitor ads via Facebook Ad Library:
- Add/remove spy targets (persisted in SQLite)
- View discovered ads
- Track monitoring stats
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from agent.services.spy_ads import get_spy_ads

router = APIRouter(prefix="/spy", tags=["spy-ads"])


class SpyTargetCreate(BaseModel):
    page_name: str
    page_id: str
    page_url: Optional[str] = None
    check_interval: Optional[int] = 3600  # seconds


@router.get("/targets")
async def list_targets():
    spy = get_spy_ads()
    return spy.list_targets()


@router.get("/targets/stats")
async def spy_stats():
    spy = get_spy_ads()
    return spy.stats


@router.post("/targets")
async def add_target(body: SpyTargetCreate):
    spy = get_spy_ads()
    target = await spy.add_target(body.model_dump())
    return target.to_dict()


@router.get("/targets/{target_id}")
async def get_target(target_id: str):
    spy = get_spy_ads()
    target = spy.get_target(target_id)
    if not target:
        raise HTTPException(404, "Target not found")
    return target.to_dict()


@router.delete("/targets/{target_id}")
async def remove_target(target_id: str):
    spy = get_spy_ads()
    ok = await spy.remove_target(target_id)
    if not ok:
        raise HTTPException(404, "Target not found")
    return {"ok": True}


@router.get("/ads")
async def list_ads(target_id: str = None):
    """List all discovered competitor ads."""
    spy = get_spy_ads()
    return await spy.list_ads(target_id=target_id)
