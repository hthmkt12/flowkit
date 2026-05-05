"""FBKit — Telegram Notification Service.

Sends alerts to a Telegram bot/channel for key events:
- Task completed/failed
- Account banned / logged out
- Daily summary
"""
import asyncio
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


class TelegramNotifier:
    """Sends notifications to Telegram."""

    def __init__(self):
        self._enabled = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
        self._client = httpx.AsyncClient(timeout=15)
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._sent_count = 0
        self._error_count = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def stats(self) -> dict:
        return {
            "enabled": self._enabled,
            "sent": self._sent_count,
            "errors": self._error_count,
            "pending": self._queue.qsize(),
        }

    async def send(self, text: str, parse_mode: str = "HTML",
                   disable_notification: bool = False):
        """Queue a message to be sent."""
        if not self._enabled:
            logger.debug("Telegram notifier disabled — skipping: %s", text[:60])
            return
        try:
            self._queue.put_nowait({
                "text": text,
                "parse_mode": parse_mode,
                "disable_notification": disable_notification,
            })
        except asyncio.QueueFull:
            logger.warning("Telegram notification queue full — dropping message")

    async def send_now(self, text: str, parse_mode: str = "HTML",
                       disable_notification: bool = False) -> bool:
        """Send a message immediately (bypass queue)."""
        if not self._enabled:
            return False
        try:
            resp = await self._client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_notification": disable_notification,
                },
            )
            if resp.status_code == 200:
                self._sent_count += 1
                return True
            else:
                logger.error("Telegram API error %d: %s", resp.status_code, resp.text[:200])
                self._error_count += 1
                return False
        except Exception as e:
            logger.error("Telegram send error: %s", e)
            self._error_count += 1
            return False

    async def start(self):
        """Background loop that drains the notification queue."""
        logger.info("Telegram notifier started (enabled=%s)", self._enabled)
        while True:
            try:
                msg = await self._queue.get()
                await self.send_now(**msg)
                # Rate limit: Telegram allows ~30 msg/sec, we go slower
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Telegram notifier loop error: %s", e)
                await asyncio.sleep(5)

    # ─── Convenience methods ────────────────────────────────

    async def notify_task_completed(self, task: dict):
        task_type = task.get("task_type", "?")
        account_id = task.get("account_id", "?")[:8]
        await self.send(
            f"✅ <b>Task Completed</b>\n"
            f"Type: <code>{task_type}</code>\n"
            f"Account: <code>{account_id}…</code>",
            disable_notification=True,
        )

    async def notify_task_failed(self, task: dict, error: str = ""):
        task_type = task.get("task_type", "?")
        account_id = task.get("account_id", "?")[:8]
        await self.send(
            f"❌ <b>Task Failed</b>\n"
            f"Type: <code>{task_type}</code>\n"
            f"Account: <code>{account_id}…</code>\n"
            f"Error: {error[:200]}",
        )

    async def notify_account_alert(self, account: dict, reason: str):
        name = account.get("name", "?")
        await self.send(
            f"⚠️ <b>Account Alert</b>\n"
            f"Name: {name}\n"
            f"Reason: {reason}",
        )

    async def notify_daily_summary(self, stats: dict):
        completed = stats.get("COMPLETED", 0)
        failed = stats.get("FAILED", 0)
        pending = stats.get("PENDING", 0)
        total = completed + failed + pending
        await self.send(
            f"📊 <b>Daily Summary</b>\n"
            f"Total: {total} | ✅ {completed} | ❌ {failed} | ⏳ {pending}",
        )


# ─── Singleton ───────────────────────────────────────────────

_notifier: Optional[TelegramNotifier] = None


def get_notifier() -> TelegramNotifier:
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier
