"""FBKit — Post & Message Scheduler.

Periodically checks for scheduled posts and messages that are due,
then creates tasks in the queue to execute them.
"""
import asyncio
import json
import logging

from agent.config import SCHEDULER_CHECK_INTERVAL
from agent.db import crud
from agent.services.event_bus import event_bus
from agent.services.safety_gate import enforce_payload
from agent.utils.time import utc_now_iso

logger = logging.getLogger(__name__)


class Scheduler:
    """Background scheduler for timed posts and messages."""

    def __init__(self):
        self._shutdown = False
        self._processed_count = 0

    @property
    def stats(self) -> dict:
        return {
            "running": not self._shutdown,
            "processed_total": self._processed_count,
            "check_interval_s": SCHEDULER_CHECK_INTERVAL,
        }

    def request_shutdown(self):
        self._shutdown = True
        logger.info("Scheduler shutdown requested")

    async def start(self):
        """Main scheduler loop — checks every SCHEDULER_CHECK_INTERVAL seconds."""
        logger.info("Scheduler started (interval=%ds)", SCHEDULER_CHECK_INTERVAL)

        while not self._shutdown:
            try:
                now = utc_now_iso()
                processed = 0

                # 1. Check scheduled posts
                posts = await crud.list_scheduled_posts(before=now)
                for post in posts:
                    await self._enqueue_post(post)
                    processed += 1

                # 2. Check scheduled messages
                messages = await crud.list_scheduled_messages(before=now)
                for msg in messages:
                    await self._enqueue_message(msg)
                    processed += 1

                if processed > 0:
                    self._processed_count += processed
                    logger.info("Scheduler enqueued %d items", processed)
                    await event_bus.emit("scheduler_enqueue", {
                        "count": processed,
                        "total": self._processed_count,
                    })

            except Exception as e:
                logger.error("Scheduler error: %s", e)

            await asyncio.sleep(SCHEDULER_CHECK_INTERVAL)

        logger.info("Scheduler stopped (processed %d total)", self._processed_count)

    async def _enqueue_post(self, post: dict):
        """Create a task for a scheduled post."""
        claimed = await crud.claim_scheduled_post(post["id"], utc_now_iso())
        if claimed is None:
            logger.debug("Skipped already claimed post %s", post["id"][:8])
            return
        post = claimed
        post_type = post.get("post_type", "TEXT")
        task_type = f"POST_{post_type}"

        payload = {
            "content": post.get("content", ""),
            "targetType": post.get("target_type", "TIMELINE"),
            "targetId": post.get("target_id"),
        }

        # Include media paths for IMAGE/VIDEO/REEL posts
        media_paths_raw = post.get("media_paths")
        if media_paths_raw:
            try:
                payload["mediaPaths"] = json.loads(media_paths_raw)
            except (json.JSONDecodeError, TypeError):
                payload["mediaPaths"] = []

        await crud.create_task(
            account_id=post["account_id"],
            task_type=task_type,
            payload=json.dumps(enforce_payload(task_type, payload)),
            ref_id=post["id"],
        )

        logger.debug("Enqueued post %s (%s)", post["id"][:8], task_type)

    async def _enqueue_message(self, msg: dict):
        """Create a task for a scheduled message."""
        claimed = await crud.claim_scheduled_message(msg["id"], utc_now_iso())
        if claimed is None:
            logger.debug("Skipped already claimed message %s", msg["id"][:8])
            return
        msg = claimed
        payload = {
            "recipientName": msg.get("recipient_name", ""),
            "recipientUid": msg.get("recipient_uid"),
            "content": msg.get("content", ""),
            "mediaPath": msg.get("media_path"),
        }

        await crud.create_task(
            account_id=msg["account_id"],
            task_type="SEND_MESSAGE",
            payload=json.dumps(enforce_payload("SEND_MESSAGE", payload)),
            ref_id=msg["id"],
        )

        logger.debug("Enqueued message %s", msg["id"][:8])


# ─── Singleton ──────────────────────────────────────────────

_scheduler: Scheduler | None = None


def get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler
