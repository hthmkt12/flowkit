"""FBKit — Seeding API routes (Phase 3).

Manages auto-engagement campaigns:
- Create/list/stop/delete seeding campaigns
- Track engagement stats per campaign
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from agent.services.auto_seed import get_auto_seeder

router = APIRouter(prefix="/seeding", tags=["seeding"])


class CampaignCreate(BaseModel):
    name: str
    accounts: list[str]  # Account IDs to rotate
    targets: list[str]  # Post URLs to engage with
    actions: Optional[list[str]] = ["LIKE"]  # LIKE, COMMENT, SHARE
    comments: Optional[list[str]] = []  # Pool of comments
    delay_min: Optional[int] = 60  # seconds between actions
    delay_max: Optional[int] = 300
    max_actions_per_account: Optional[int] = 20


@router.get("/campaigns")
async def list_campaigns():
    seeder = get_auto_seeder()
    return seeder.list_campaigns()


@router.get("/campaigns/stats")
async def seeder_stats():
    seeder = get_auto_seeder()
    return seeder.stats


@router.post("/campaigns")
async def create_campaign(body: CampaignCreate):
    seeder = get_auto_seeder()
    campaign = await seeder.create_campaign(body.model_dump())
    return campaign.to_dict()


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    seeder = get_auto_seeder()
    campaign = seeder.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return campaign.to_dict()


@router.post("/campaigns/{campaign_id}/stop")
async def stop_campaign(campaign_id: str):
    seeder = get_auto_seeder()
    ok = await seeder.stop_campaign(campaign_id)
    if not ok:
        raise HTTPException(404, "Campaign not found")
    return {"ok": True, "status": "PAUSED"}


@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: str):
    seeder = get_auto_seeder()
    ok = await seeder.delete_campaign(campaign_id)
    if not ok:
        raise HTTPException(404, "Campaign not found")
    return {"ok": True}
