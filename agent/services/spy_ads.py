"""FBKit — Spy Ads Service.

Monitors competitor Facebook Ads Library and pages for:
- New ad creatives
- Ad copy changes
- Active/Inactive status tracking
- Notifications on new ads detected

Spy targets are persisted in SQLite (spy_target table).
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from agent.db import crud
from agent.db.schema import get_db
from agent.services.event_bus import event_bus

logger = logging.getLogger(__name__)


class SpyTarget:
    """A single ad spy target (page or advertiser)."""

    def __init__(self, target_id: str, config: dict,
                 status: str = "ACTIVE", ads_found: int = 0, last_checked: str = None):
        self.id = target_id
        self.page_name = config.get("page_name", "")
        self.page_id = config.get("page_id", "")
        self.page_url = config.get("page_url", "")
        self.check_interval = config.get("check_interval", 3600)
        self.last_checked = last_checked
        self.ads_found = ads_found
        self.status = status

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "page_name": self.page_name,
            "page_id": self.page_id,
            "page_url": self.page_url,
            "check_interval": self.check_interval,
            "last_checked": self.last_checked,
            "ads_found": self.ads_found,
            "status": self.status,
        }

    @classmethod
    def from_db_row(cls, row: dict) -> "SpyTarget":
        config = {
            "page_name": row["page_name"],
            "page_id": row["page_id"],
            "page_url": row.get("page_url", ""),
            "check_interval": row.get("check_interval", 3600),
        }
        return cls(
            row["id"],
            config,
            status=row.get("status", "ACTIVE"),
            ads_found=row.get("ads_found", 0),
            last_checked=row.get("last_checked"),
        )


class SpyAdsService:
    """Monitors competitor ads via Facebook Ad Library scraping."""

    def __init__(self):
        self._targets: dict[str, SpyTarget] = {}
        self._running = False
        self._shutdown = asyncio.Event()

    @property
    def stats(self) -> dict:
        return {
            "running": self._running,
            "targets": len(self._targets),
            "active": sum(1 for t in self._targets.values() if t.status == "ACTIVE"),
            "total_ads_found": sum(t.ads_found for t in self._targets.values()),
        }

    async def _load_from_db(self):
        """Load all spy targets from DB into memory on startup."""
        rows = await crud.list_spy_targets()
        for row in rows:
            target = SpyTarget.from_db_row(row)
            self._targets[target.id] = target
        logger.info("SpyAds: loaded %d targets from DB", len(self._targets))

    async def add_target(self, config: dict) -> SpyTarget:
        """Add a page/advertiser to monitor and persist to DB."""
        row = await crud.create_spy_target(
            page_name=config["page_name"],
            page_id=config["page_id"],
            page_url=config.get("page_url", ""),
            check_interval=config.get("check_interval", 3600),
        )
        target = SpyTarget.from_db_row(row)
        self._targets[target.id] = target
        logger.info("Spy target added: %s (%s)", target.page_name, target.id)
        return target

    def get_target(self, target_id: str) -> Optional[SpyTarget]:
        return self._targets.get(target_id)

    def list_targets(self) -> list[dict]:
        return [t.to_dict() for t in self._targets.values()]

    async def remove_target(self, target_id: str) -> bool:
        if target_id in self._targets:
            del self._targets[target_id]
            await crud.delete_spy_target(target_id)
            return True
        return False

    async def start(self):
        """Background loop that checks targets periodically."""
        self._running = True
        await self._load_from_db()
        logger.info("SpyAds service started")

        while not self._shutdown.is_set():
            try:
                now = datetime.utcnow()

                for target in self._targets.values():
                    if target.status != "ACTIVE":
                        continue

                    if target.last_checked:
                        elapsed = (now - datetime.fromisoformat(target.last_checked)).total_seconds()
                        if elapsed < target.check_interval:
                            continue

                    await self._check_target(target)

                try:
                    await asyncio.wait_for(self._shutdown.wait(), timeout=60)
                except asyncio.TimeoutError:
                    pass

            except Exception as e:
                logger.error("SpyAds error: %s", e)
                await asyncio.sleep(30)

        self._running = False
        logger.info("SpyAds service stopped")

    def request_shutdown(self):
        self._shutdown.set()

    async def _check_target(self, target: SpyTarget):
        """Check a single target for new ads by queuing a SCRAPE task."""
        ad_lib_url = (
            f"https://www.facebook.com/ads/library/"
            f"?active_status=active&ad_type=all&country=ALL"
            f"&view_all_page_id={target.page_id}"
        )

        payload = {
            "profileUrl": ad_lib_url,
            "spy_target_id": target.id,
            "page_name": target.page_name,
        }

        try:
            await crud.create_task(
                account_id="system",
                task_type="SCRAPE_PROFILE",
                payload=json.dumps(payload),
                ref_id=target.id,
            )
            target.last_checked = datetime.utcnow().isoformat()

            # Persist last_checked to DB
            await crud.update_spy_target(target.id, last_checked=target.last_checked)

            logger.info("SpyAds: queued check for %s", target.page_name)
            await event_bus.emit("spy_check", {
                "target": target.page_name,
                "url": ad_lib_url,
            })
        except Exception as e:
            logger.error("SpyAds check failed for %s: %s", target.page_name, e)

    async def record_ads_found(self, target_id: str, ads: list[dict]):
        """Record newly discovered ads (called from scrape result handler)."""
        target = self._targets.get(target_id)
        if not target:
            return

        db = await get_db()
        new_ads = 0

        for ad in ads:
            ad_id = ad.get("ad_id", "")
            cur = await db.execute("SELECT id FROM spy_ad WHERE fb_ad_id = ?", (ad_id,))
            existing = await cur.fetchone()

            if not existing:
                await db.execute(
                    """INSERT INTO spy_ad (id, target_id, fb_ad_id, page_name,
                       ad_text, media_url, ad_status, first_seen)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid.uuid4()),
                        target_id,
                        ad_id,
                        target.page_name,
                        ad.get("text", ""),
                        ad.get("media_url", ""),
                        ad.get("status", "ACTIVE"),
                        datetime.utcnow().isoformat(),
                    )
                )
                new_ads += 1
                await event_bus.emit("spy_new_ad", {
                    "page": target.page_name,
                    "ad_id": ad_id,
                    "text": ad.get("text", "")[:100],
                })

        if new_ads:
            target.ads_found += new_ads
            await crud.update_spy_target(target.id, ads_found=target.ads_found)

        await db.commit()

    async def list_ads(self, target_id: str = None) -> list[dict]:
        """List all discovered ads, optionally filtered by target."""
        db = await get_db()
        if target_id:
            cur = await db.execute(
                "SELECT * FROM spy_ad WHERE target_id = ? ORDER BY first_seen DESC",
                (target_id,)
            )
        else:
            cur = await db.execute(
                "SELECT * FROM spy_ad ORDER BY first_seen DESC LIMIT 200"
            )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ─── Singleton ───────────────────────────────────────────────

_spy: Optional[SpyAdsService] = None


def get_spy_ads() -> SpyAdsService:
    global _spy
    if _spy is None:
        _spy = SpyAdsService()
    return _spy
