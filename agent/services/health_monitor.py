"""FBKit — Health Monitor.

Tracks task failures, checkpoints, and handles automatic safety lockouts.
"""

from __future__ import annotations

import logging
from agent.db import crud

logger = logging.getLogger(__name__)


class HealthMonitor:
    def __init__(self, failure_threshold: int = 3):
        self.failure_threshold = failure_threshold
        self._consecutive_failures: dict[str, int] = {}

    def record_success(self, account_id: str):
        self._consecutive_failures[account_id] = 0

    async def record_failure(self, account_id: str, error_message: str | None = None):
        count = self._consecutive_failures.get(account_id, 0) + 1
        self._consecutive_failures[account_id] = count
        logger.warning(
            "Recorded task failure for account=%s (consecutive failures: %d/%d). Error: %s",
            account_id,
            count,
            self.failure_threshold,
            error_message,
        )
        if count >= self.failure_threshold:
            logger.error("Account %s reached failure threshold. Auto-pausing account.", account_id)
            await crud.update_account(account_id, status="PAUSED")
            await crud.log_activity(
                account_id,
                "HEALTH_AUTO_PAUSE",
                f"Auto-paused account due to {count} consecutive failures. Latest: {error_message or 'Unknown error'}",
            )
            self._consecutive_failures[account_id] = 0

    async def record_checkpoint(self, account_id: str):
        logger.error("Facebook checkpoint detected for account=%s. Auto-pausing account immediately.", account_id)
        await crud.update_account(account_id, status="PAUSED")
        await crud.log_activity(
            account_id,
            "HEALTH_CHECKPOINT",
            "Auto-paused account due to Facebook checkpoint detection",
        )
        self._consecutive_failures[account_id] = 0


_monitor = HealthMonitor()


def get_health_monitor() -> HealthMonitor:
    return _monitor
