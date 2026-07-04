"""FBKit — Ingestion Metrics Sync.

Periodically queries completed tasks with 'zoopost:' references,
fetches Facebook metrics via fb_client, and reports them to ZooPost Cloud.
"""
import asyncio
import json
import logging
import httpx

from agent import config
from agent.db import crud
from agent.services.fb_client import get_fb_client

logger = logging.getLogger(__name__)


class MetricsSync:
    def __init__(self):
        self._shutdown = False
        self._sync_count = 0

    @property
    def stats(self) -> dict:
        return {
            "running": not self._shutdown,
            "syncs_total": self._sync_count,
        }

    def request_shutdown(self):
        self._shutdown = True
        logger.info("MetricsSync shutdown requested")

    async def start(self):
        """Main metrics sync loop — checks every 60 seconds (or test interval)."""
        logger.info("MetricsSync started")
        
        import os
        interval = 10 if os.environ.get("ZOOPOST_ENV") == "test" else 60

        while not self._shutdown:
            try:
                await self.sync_metrics()
            except Exception as e:
                logger.error("MetricsSync error during sync: %s", e)

            # Sleep in small increments to respond quickly to shutdown requests
            for _ in range(int(interval)):
                if self._shutdown:
                    break
                await asyncio.sleep(1)

        logger.info("MetricsSync stopped")

    async def sync_metrics(self):
        if not config.ZOOPOST_CLOUD_API_URL:
            return

        tasks = await crud.list_due_metrics_tasks(
            limit=config.ZOOPOST_METRICS_BATCH_LIMIT,
            refresh_seconds=config.ZOOPOST_METRICS_REFRESH_SECONDS,
            max_age_days=config.ZOOPOST_METRICS_MAX_AGE_DAYS,
        )

        fb_client = get_fb_client()
        async with httpx.AsyncClient() as http_client:
            for row in tasks:
                if self._shutdown:
                    break
                
                task_id = row["id"]
                ref_id = row["ref_id"]
                result_str = row["result"]
                fb_uid = row["fb_uid"]
                dispatch_id = ref_id.split(":", 1)[1] if ":" in ref_id else None
                if not dispatch_id:
                    continue

                external_post_id = None
                if result_str:
                    try:
                        res_dict = json.loads(result_str)
                        if isinstance(res_dict, dict):
                            external_post_id = res_dict.get("externalPostId")
                    except Exception:
                        pass

                if not external_post_id:
                    continue

                logger.info(
                    "Syncing metrics for dispatch %s (post_id: %s, fb_uid: %s)",
                    dispatch_id, external_post_id, fb_uid
                )

                try:
                    # Query metrics from extension
                    res = await fb_client.get_post_metrics(external_post_id, fb_uid=fb_uid)
                    if not res or "error" in res:
                        logger.error(
                            "Failed to get post metrics from extension for %s: %s",
                            external_post_id, res.get("error") if res else "No response"
                        )
                        continue

                    metrics = res.get("metrics")
                    if not metrics:
                        logger.error(
                            "No metrics field in response from extension for %s: %s",
                            external_post_id, res
                        )
                        continue

                    # Post metrics back to ZooPost Cloud
                    url = f"{config.ZOOPOST_CLOUD_API_URL.rstrip('/')}/agent-gateway/targets/{dispatch_id}/metrics"
                    headers = {"X-Agent-Credential": config.ZOOPOST_AGENT_CREDENTIAL}

                    body = {
                        "reach": metrics.get("reach", 0),
                        "engagement": metrics.get("engagement", 0),
                        "likes": metrics.get("likes", 0),
                        "comments": metrics.get("comments", 0),
                        "shares": metrics.get("shares", 0),
                    }
                    
                    cloud_res = await http_client.post(url, json=body, headers=headers, timeout=10)
                    if cloud_res.status_code == 200:
                        await crud.mark_task_metrics_synced(task_id)
                        logger.info("Successfully synced metrics for dispatch %s to cloud", dispatch_id)
                        self._sync_count += 1
                    else:
                        logger.error(
                            "Failed to post metrics to cloud for dispatch %s. Status: %d, Response: %s",
                            dispatch_id, cloud_res.status_code, cloud_res.text
                        )
                except Exception as e:
                    logger.exception("Error syncing metrics for dispatch %s: %s", dispatch_id, e)


_metrics_sync: MetricsSync | None = None


def get_metrics_sync() -> MetricsSync:
    global _metrics_sync
    if _metrics_sync is None:
        _metrics_sync = MetricsSync()
    return _metrics_sync
