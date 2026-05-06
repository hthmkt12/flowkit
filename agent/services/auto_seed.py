"""FBKit — Auto-Seeding Service.

Automated engagement loop that:
1. Reads target post URLs / groups / pages
2. Performs like → comment → share in sequence with human-like delays
3. Rotates across multiple accounts to avoid detection
4. Tracks engagement stats per campaign (persisted in SQLite)
"""
import asyncio
import json
import logging
import random
import uuid
from datetime import datetime
from typing import Optional

from agent.db import crud
from agent.services.event_bus import event_bus
from agent.services.safety_gate import enforce_payload

logger = logging.getLogger(__name__)


class SeedCampaign:
    """A single seeding campaign targeting posts for engagement."""

    def __init__(self, campaign_id: str, config: dict, status: str = "ACTIVE", stats: dict = None):
        self.id = campaign_id
        self.name = config.get("name", f"Campaign {campaign_id[:8]}")
        self.accounts = config.get("accounts", [])
        self.targets = config.get("targets", [])
        self.actions = config.get("actions", ["LIKE"])
        self.comments = config.get("comments", [])
        self.delay_min = config.get("delay_min", 60)
        self.delay_max = config.get("delay_max", 300)
        self.max_actions_per_account = config.get("max_actions_per_account", 20)
        self.status = status
        self.stats = stats or {"total": 0, "success": 0, "failed": 0}
        self._config = config  # Keep original for DB storage

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "accounts": self.accounts,
            "targets": self.targets,
            "actions": self.actions,
            "status": self.status,
            "stats": self.stats,
        }

    @classmethod
    def from_db_row(cls, row: dict) -> "SeedCampaign":
        config = json.loads(row.get("config") or "{}")
        stats = json.loads(row.get("stats") or "{}")
        config["name"] = row["name"]
        return cls(row["id"], config, status=row.get("status", "ACTIVE"), stats=stats)


class AutoSeeder:
    """Manages seeding campaigns — automated engagement loops."""

    def __init__(self):
        self._campaigns: dict[str, SeedCampaign] = {}
        self._running = False
        self._shutdown = asyncio.Event()

    @property
    def stats(self) -> dict:
        return {
            "running": self._running,
            "campaigns": len(self._campaigns),
            "active": sum(1 for c in self._campaigns.values() if c.status == "ACTIVE"),
        }

    async def _load_from_db(self):
        """Load all campaigns from DB into memory on startup."""
        rows = await crud.list_seed_campaigns()
        for row in rows:
            campaign = SeedCampaign.from_db_row(row)
            self._campaigns[campaign.id] = campaign
        logger.info("AutoSeeder: loaded %d campaigns from DB", len(self._campaigns))

    async def create_campaign(self, config: dict) -> SeedCampaign:
        """Create a new seeding campaign and persist to DB."""
        campaign_id = str(uuid.uuid4())
        name = config.get("name", f"Campaign {campaign_id[:8]}")
        campaign = SeedCampaign(campaign_id, config)
        await self._persist_create(campaign)
        self._campaigns[campaign.id] = campaign
        logger.info("Seeding campaign created: %s (%s)", name, campaign_id)
        return campaign

    async def _persist_create(self, campaign: SeedCampaign):
        """Insert campaign into DB with correct ID."""
        db_config = dict(campaign._config)
        db_config["name"] = campaign.name
        from agent.db.schema import get_db
        db = await get_db()
        await db.execute(
            "INSERT INTO seed_campaign (id, name, config, stats, status) VALUES (?, ?, ?, ?, ?)",
            (
                campaign.id,
                campaign.name,
                json.dumps(campaign._config),
                json.dumps(campaign.stats),
                campaign.status,
            )
        )
        await db.commit()

    def get_campaign(self, campaign_id: str) -> Optional[SeedCampaign]:
        return self._campaigns.get(campaign_id)

    def list_campaigns(self) -> list[dict]:
        return [c.to_dict() for c in self._campaigns.values()]

    async def stop_campaign(self, campaign_id: str) -> bool:
        campaign = self._campaigns.get(campaign_id)
        if campaign:
            campaign.status = "PAUSED"
            await crud.update_seed_campaign(campaign_id, status="PAUSED")
            return True
        return False

    async def delete_campaign(self, campaign_id: str) -> bool:
        if campaign_id in self._campaigns:
            del self._campaigns[campaign_id]
            await crud.delete_seed_campaign(campaign_id)
            return True
        return False

    async def start(self):
        """Background loop that processes active campaigns."""
        self._running = True
        await self._load_from_db()
        logger.info("AutoSeeder started")

        while not self._shutdown.is_set():
            try:
                active = [c for c in self._campaigns.values() if c.status == "ACTIVE"]

                for campaign in active:
                    await self._process_campaign(campaign)

                # Flush stats to DB every cycle
                await self._flush_stats()

                try:
                    await asyncio.wait_for(self._shutdown.wait(), timeout=30)
                except asyncio.TimeoutError:
                    pass

            except Exception as e:
                logger.error("AutoSeeder error: %s", e)
                await asyncio.sleep(10)

        self._running = False
        logger.info("AutoSeeder stopped")

    async def _flush_stats(self):
        """Persist in-memory stats back to DB."""
        for campaign in self._campaigns.values():
            try:
                await crud.update_seed_campaign(
                    campaign.id,
                    stats=json.dumps(campaign.stats),
                )
            except Exception as e:
                logger.debug("AutoSeeder stats flush error for %s: %s", campaign.id, e)

    def request_shutdown(self):
        self._shutdown.set()

    async def _process_campaign(self, campaign: SeedCampaign):
        """Process one round of a seeding campaign."""
        if not campaign.targets or not campaign.accounts:
            return

        account_id = random.choice(campaign.accounts)
        target = random.choice(campaign.targets)
        action = random.choice(campaign.actions)

        payload = {"postUrl": target}
        task_type = None

        if action == "LIKE":
            task_type = "LIKE_POST"
            payload["reaction"] = random.choice(["LIKE", "LOVE", "HAHA", "WOW", "CARE"])
        elif action == "COMMENT":
            task_type = "COMMENT_POST"
            payload["comment"] = random.choice(campaign.comments) if campaign.comments else "👍"
        elif action == "SHARE":
            task_type = "SHARE_POST"
            payload["targetType"] = "TIMELINE"

        if task_type:
            try:
                await crud.create_task(
                    account_id=account_id,
                    task_type=task_type,
                    payload=json.dumps(enforce_payload(task_type, payload)),
                    ref_id=campaign.id,
                )
                campaign.stats["total"] += 1
                campaign.stats["success"] += 1
                await event_bus.emit("seed_action", {
                    "campaign": campaign.name,
                    "action": action,
                    "target": target[:60],
                })
            except Exception as e:
                campaign.stats["failed"] += 1
                logger.error("Seed action failed: %s", e)

        delay = random.uniform(campaign.delay_min, campaign.delay_max)
        await asyncio.sleep(delay)


# ─── Singleton ───────────────────────────────────────────────

_seeder: Optional[AutoSeeder] = None


def get_auto_seeder() -> AutoSeeder:
    global _seeder
    if _seeder is None:
        _seeder = AutoSeeder()
    return _seeder
