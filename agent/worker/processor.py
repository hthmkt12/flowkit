"""FBKit — Task queue processor.

Polls for pending tasks, dispatches to FBClient, updates results.
Enforces rate limits and human-like session management.
"""
import asyncio
import json
import logging
import traceback
from datetime import datetime

from agent.config import (
    MAX_CONCURRENT_TASKS,
    MAX_RETRIES,
    POLL_INTERVAL,
)
from agent.db import crud
from agent.services.fb_client import get_fb_client
from agent.services.human_delay import action_delay, long_delay, get_session_manager
from agent.services.event_bus import event_bus
from agent.services.notifier import get_notifier
from agent.services.safety_gate import dry_run_from_payload, enforce_payload

logger = logging.getLogger(__name__)

# Map task_type → daily counter field in account table
_COUNTER_MAP = {
    "POST_TEXT": "daily_posts",
    "POST_IMAGE": "daily_posts",
    "POST_VIDEO": "daily_posts",
    "POST_LINK": "daily_posts",
    "POST_STORY": "daily_posts",
    "POST_REEL": "daily_posts",
    "SEND_MESSAGE": "daily_messages",
    "SEND_BULK_MESSAGE": "daily_messages",
    "LIKE_POST": "daily_likes",
    "COMMENT_POST": "daily_comments",
    "ADD_FRIEND": "daily_friends",
    "ACCEPT_FRIEND": "daily_friends",
    "SHARE_POST": "daily_posts",
}

# Map task_type → rate limit config key
_RATE_LIMITS = {
    "daily_posts": "RATE_LIMIT_POSTS_PER_DAY",
    "daily_messages": "RATE_LIMIT_MESSAGES_PER_DAY",
    "daily_likes": "RATE_LIMIT_LIKES_PER_DAY",
    "daily_comments": "RATE_LIMIT_COMMENTS_PER_DAY",
    "daily_friends": "RATE_LIMIT_FRIEND_REQUESTS_PER_DAY",
}


def _classify_error(error_message: str) -> str:
    lower = (error_message or "").lower()
    non_retryable_keywords = (
        "invalid api key",
        "unauthorized",
        "forbidden",
        "not logged in",
        "unsupported",
        "unknown task type",
        "validation",
    )
    if any(k in lower for k in non_retryable_keywords):
        return "NON_RETRYABLE"
    return "RETRYABLE"


def _next_retry_delay_s(retry_count: int) -> int:
    base = 2
    cap = 120
    exp = min(cap, base ** max(retry_count, 1))
    jitter = int((retry_count * 131) % 3)
    return exp + jitter


def _strategy_url_from_payload(payload: dict) -> str:
    for key in ("postUrl", "groupUrl", "pageUrl", "profileUrl", "sourceUrl"):
        if payload.get(key):
            return payload[key]

    target_type = payload.get("targetType")
    target_id = payload.get("targetId")
    if target_type and target_id:
        return f"{str(target_type).upper()}:{target_id}"

    return "*"


def _quota_units_for_task(task_type: str, payload: dict) -> int:
    if task_type == "SEND_BULK_MESSAGE":
        return len(_bulk_recipients_from_payload(payload))
    return 1


def _bulk_recipients_from_payload(payload: dict) -> list[dict]:
    recipients = payload.get("recipients")
    if not isinstance(recipients, list) or not recipients:
        raise ValueError("SEND_BULK_MESSAGE requires a non-empty recipients list")
    for index, recipient in enumerate(recipients, start=1):
        if not isinstance(recipient, dict):
            raise ValueError(f"Recipient #{index} must be an object")
        if not recipient.get("uid") and not recipient.get("name"):
            raise ValueError(f"Recipient #{index} requires uid or name")
    return recipients


class WorkerController:
    """Controls the background task processor."""

    def __init__(self):
        self._shutdown = False
        self._active_count = 0

    @property
    def active_count(self) -> int:
        return self._active_count

    def request_shutdown(self, *args):
        self._shutdown = True
        logger.info("Worker shutdown requested")

    async def drain(self):
        """Wait for active tasks to finish."""
        while self._active_count > 0:
            await asyncio.sleep(0.5)
        logger.info("Worker drained")

    async def start(self):
        """Main worker loop — polls for pending tasks."""
        logger.info("Worker started (poll=%ds, max_concurrent=%d)",
                     POLL_INTERVAL, MAX_CONCURRENT_TASKS)
        session = get_session_manager()

        while not self._shutdown:
            try:
                # Session management — take breaks like a real user
                if session.should_take_break():
                    break_duration = session.take_break()
                    await event_bus.emit("worker_break", {
                        "duration_s": int(break_duration),
                        "session": session.session_info,
                    })
                    await asyncio.sleep(min(break_duration, 60))  # Check shutdown every 60s
                    continue

                # Check extension connection
                client = get_fb_client()
                if not client.connected:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                # Respect concurrency limit
                if self._active_count >= MAX_CONCURRENT_TASKS:
                    await asyncio.sleep(1)
                    continue

                # Claim next task before launching async processing to avoid duplicate dispatch.
                task = await crud.claim_next_pending_task()
                if task is None:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                # Check rate limit
                if not await self._check_rate_limit(task):
                    logger.warning("Rate limit hit for %s (account %s), skipping",
                                   task["task_type"], task["account_id"][:8])
                    await crud.update_task(task["id"], status="FAILED",
                                           error_message="Daily rate limit exceeded")
                    continue

                # Process task
                self._active_count += 1
                asyncio.create_task(self._process_task(task))

            except Exception as e:
                logger.error("Worker loop error: %s", e)
                await asyncio.sleep(POLL_INTERVAL)

        logger.info("Worker stopped")

    async def _check_rate_limit(self, task: dict) -> bool:
        """Reserve live-action quota for a task unless Safety Gate forces dry-run."""
        from agent import config
        task_type = task["task_type"]
        payload = json.loads(task.get("payload") or "{}") if task.get("payload") else {}
        payload = enforce_payload(task_type, payload)
        if dry_run_from_payload(payload):
            return True

        counter_field = _COUNTER_MAP.get(task_type)
        if not counter_field:
            return True  # No rate limit for this task type
        limit_key = _RATE_LIMITS.get(counter_field)
        limit = getattr(config, limit_key, 999) if limit_key else 999
        try:
            units = _quota_units_for_task(task_type, payload)
        except ValueError as exc:
            logger.warning("Invalid quota payload for %s: %s", task_type, exc)
            return False
        reservation = payload.get("_quotaReserved") or {}
        if (
            reservation.get("counter") == counter_field
            and int(reservation.get("units", 0)) >= units
        ):
            return True

        reserved = await crud.reserve_daily_counter(
            task["account_id"],
            counter_field,
            units,
            limit,
        )
        if reserved and task.get("id"):
            payload["_quotaReserved"] = {"counter": counter_field, "units": units}
            await crud.update_task(task["id"], payload=json.dumps(payload))
        return reserved

    async def _process_task(self, task: dict):
        """Process a single task."""
        task_id = task["id"]
        task_type = task["task_type"]
        session = get_session_manager()
        started_at_ms = int(datetime.utcnow().timestamp() * 1000)
        payload = json.loads(task.get("payload") or "{}") if task.get("payload") else {}
        payload = enforce_payload(task_type, payload)
        is_dry_run = dry_run_from_payload(payload)
        strategy_url = _strategy_url_from_payload(payload)

        # Resolve the fb_uid for this account so we route to the right extension
        fb_uid: str | None = None
        if task.get("account_id"):
            account = await crud.get_account(task["account_id"])
            if account:
                fb_uid = account.get("fb_uid")  # may be None for legacy accounts

        # Load learned strategy for this task type (AutoBrowse pattern)
        strategy = await crud.get_strategy(task_type, strategy_url)
        strategy_id = strategy["id"] if strategy else None
        if strategy:
            logger.info(
                "Task %s (%s) using strategy for %s: %d successes, %d failures",
                task_id[:8], task_type, strategy.get("url_pattern", strategy_url),
                strategy.get("success_count", 0),
                strategy.get("fail_count", 0),
            )

        try:
            # Mark as processing
            await crud.update_task(task_id, status="PROCESSING",
                                   started_at=datetime.utcnow().isoformat())
            await event_bus.emit("task_started", {"task_id": task_id, "type": task_type})

            # Human-like delay before action
            await action_delay()

            # Dispatch to handler
            result = await self._dispatch(task_type, payload, task, fb_uid=fb_uid,
                                          strategy=strategy)

            if result.get("error"):
                raise Exception(result["error"])

            # Success
            duration_ms = int(datetime.utcnow().timestamp() * 1000) - started_at_ms
            await crud.update_task(
                task_id,
                status="COMPLETED",
                completed_at=datetime.utcnow().isoformat(),
                result=json.dumps(result),
            )

            # Record structured trace (AutoBrowse pattern)
            await crud.create_trace(
                task_id=task_id,
                task_type=task_type,
                status="SUCCESS",
                account_id=task.get("account_id"),
                duration_ms=duration_ms,
                strategy_id=strategy_id,
            )
            # Update strategy success count
            if strategy:
                await crud.record_strategy_outcome(
                    task_type,
                    strategy.get("url_pattern", strategy_url),
                    success=True,
                )

            # Log activity
            if task.get("account_id"):
                await crud.log_activity(task["account_id"], task_type,
                                        f"Task {task_id[:8]} completed")

            session.record_action()
            await event_bus.emit("task_completed", {"task_id": task_id, "type": task_type})

            # Telegram notification (non-blocking)
            notifier = get_notifier()
            asyncio.create_task(notifier.notify_task_completed(task))

            logger.info("Task %s (%s) completed in %dms", task_id[:8], task_type, duration_ms)

        except Exception as e:
            logger.error("Task %s (%s) failed: %s", task_id[:8], task_type, e)
            duration_ms = int(datetime.utcnow().timestamp() * 1000) - started_at_ms
            retry_count = task.get("retry_count", 0) + 1
            max_retries = task.get("max_retries", MAX_RETRIES)

            error_message = str(e)[:500]
            error_class = _classify_error(error_message)

            # Record structured trace for failure (AutoBrowse pattern)
            await crud.create_trace(
                task_id=task_id,
                task_type=task_type,
                status="FAILURE",
                account_id=task.get("account_id"),
                duration_ms=duration_ms,
                error_detail=error_message,
                strategy_id=strategy_id,
            )
            # Update strategy fail count
            if strategy:
                await crud.record_strategy_outcome(
                    task_type,
                    strategy.get("url_pattern", strategy_url),
                    success=False,
                )

            # Auto-learn: record error as a workaround hint for future runs
            await crud.upsert_strategy(
                task_type=task_type,
                url_pattern=strategy_url,
                workarounds=[{
                    "error": error_message[:200],
                    "error_class": error_class,
                    "recorded_at": datetime.utcnow().isoformat(),
                }],
            )

            if error_class == "RETRYABLE" and retry_count < max_retries:
                delay_s = _next_retry_delay_s(retry_count)
                scheduled_at = datetime.utcfromtimestamp(
                    datetime.utcnow().timestamp() + delay_s
                ).isoformat()
                await crud.update_task(
                    task_id,
                    status="PENDING",
                    retry_count=retry_count,
                    scheduled_at=scheduled_at,
                    error_message=error_message,
                )
                logger.info(
                    "Task %s retry scheduled in %ss (%d/%d)",
                    task_id[:8],
                    delay_s,
                    retry_count,
                    max_retries,
                )
            else:
                await crud.update_task(
                    task_id,
                    status="FAILED",
                    completed_at=datetime.utcnow().isoformat(),
                    error_message=error_message,
                )
                await event_bus.emit(
                    "task_failed",
                    {
                        "task_id": task_id,
                        "error": error_message[:200],
                        "error_class": error_class,
                    },
                )

                # Telegram alert for permanent failures
                notifier = get_notifier()
                asyncio.create_task(notifier.notify_task_failed(task, error_message))

        finally:
            self._active_count -= 1

    async def _dispatch(self, task_type: str, payload: dict, task: dict,
                        fb_uid: str | None = None,
                        strategy: dict | None = None) -> dict:
        """Dispatch task to the appropriate FBClient method.

        fb_uid routes the command to the correct extension session.
        strategy provides learned hints (selectors, wait times, workarounds)
        that the extension can use to improve reliability.
        If None, falls back to any connected extension.
        """
        client = get_fb_client()

        strategy_hints = None
        if strategy:
            strategy_hints = {
                "selectors": strategy.get("selectors"),
                "wait_strategies": strategy.get("wait_strategies"),
                "workarounds": strategy.get("workarounds"),
            }
        payload = enforce_payload(task_type, payload)
        dry_run = dry_run_from_payload(payload)

        if task_type == "CHECK_LOGIN":
            return await client.check_login(fb_uid=fb_uid)

        elif task_type == "POST_TEXT":
            return await client.post_text(
                content=payload.get("content", ""),
                target_type=payload.get("targetType", "TIMELINE"),
                target_id=payload.get("targetId"),
                fb_uid=fb_uid,
                strategy=strategy_hints,
                dry_run=dry_run,
            )

        elif task_type == "POST_LINK":
            content = payload.get("content", "")
            link_url = payload.get("linkUrl") or payload.get("url") or payload.get("link")
            if link_url:
                content = f"{content}\n{link_url}" if content else link_url
            return await client.post_text(
                content=content,
                target_type=payload.get("targetType", "TIMELINE"),
                target_id=payload.get("targetId"),
                fb_uid=fb_uid,
                strategy=strategy_hints,
                dry_run=dry_run,
            )

        elif task_type in ("POST_IMAGE", "POST_VIDEO"):
            return await client.post_with_media(
                content=payload.get("content", ""),
                media_paths=payload.get("mediaPaths", []),
                target_type=payload.get("targetType", "TIMELINE"),
                target_id=payload.get("targetId"),
                fb_uid=fb_uid,
                strategy=strategy_hints,
                dry_run=dry_run,
            )

        elif task_type == "POST_STORY":
            return await client.post_with_media(
                content=payload.get("content", ""),
                media_paths=payload.get("mediaPaths", []),
                target_type="STORY",
                target_id=payload.get("targetId"),
                fb_uid=fb_uid,
                strategy=strategy_hints,
                dry_run=dry_run,
            )

        elif task_type == "POST_REEL":
            return await client.post_with_media(
                content=payload.get("content", ""),
                media_paths=payload.get("mediaPaths", []),
                target_type="REEL",
                target_id=payload.get("targetId"),
                fb_uid=fb_uid,
                strategy=strategy_hints,
                dry_run=dry_run,
            )

        elif task_type == "SEND_MESSAGE":
            return await client.send_message(
                recipient_name=payload.get("recipientName", ""),
                content=payload.get("content", ""),
                recipient_uid=payload.get("recipientUid"),
                media_path=payload.get("mediaPath"),
                fb_uid=fb_uid,
                strategy=strategy_hints,
                dry_run=dry_run,
            )

        elif task_type == "SEND_BULK_MESSAGE":
            recipients = _bulk_recipients_from_payload(payload)
            content = payload.get("content", "")
            media_path = payload.get("mediaPath")
            results = []
            for recipient in recipients:
                r = await client.send_message(
                    recipient_name=recipient.get("name", ""),
                    content=content,
                    recipient_uid=recipient.get("uid"),
                    media_path=media_path,
                    fb_uid=fb_uid,
                    strategy=strategy_hints,
                    dry_run=dry_run,
                )
                results.append(r)
                if r.get("error"):
                    logger.warning("Bulk msg to %s failed: %s",
                                   recipient.get("name"), r["error"])
                await long_delay()
            sent = sum(1 for r in results if r.get("success"))
            return {
                "success": True,
                "message": f"Bulk message: {sent}/{len(recipients)} sent",
                "details": results,
            }

        elif task_type == "LIKE_POST":
            return await client.like_post(
                post_url=payload.get("postUrl", ""),
                reaction=payload.get("reaction", "LIKE"),
                fb_uid=fb_uid,
                strategy=strategy_hints,
                dry_run=dry_run,
            )

        elif task_type == "COMMENT_POST":
            return await client.comment_post(
                post_url=payload.get("postUrl", ""),
                comment=payload.get("comment", ""),
                fb_uid=fb_uid,
                strategy=strategy_hints,
                dry_run=dry_run,
            )

        elif task_type == "SHARE_POST":
            return await client.share_post(
                post_url=payload.get("postUrl", ""),
                comment=payload.get("comment", ""),
                target_type=payload.get("targetType", "TIMELINE"),
                target_id=payload.get("targetId"),
                fb_uid=fb_uid,
                strategy=strategy_hints,
                dry_run=dry_run,
            )

        elif task_type == "ADD_FRIEND":
            return await client.add_friend(
                profile_url=payload.get("profileUrl", ""),
                fb_uid=fb_uid,
                strategy=strategy_hints,
                dry_run=dry_run,
            )

        elif task_type == "ACCEPT_FRIEND":
            return await client.accept_friend(
                request_url=payload.get("requestUrl"),
                fb_uid=fb_uid,
                strategy=strategy_hints,
                dry_run=dry_run,
            )

        elif task_type == "JOIN_GROUP":
            return await client.join_group(
                group_url=payload.get("groupUrl", ""),
                fb_uid=fb_uid,
                strategy=strategy_hints,
                dry_run=dry_run,
            )

        elif task_type == "LEAVE_GROUP":
            return await client.leave_group(
                group_url=payload.get("groupUrl", ""),
                fb_uid=fb_uid,
                strategy=strategy_hints,
                dry_run=dry_run,
            )

        elif task_type == "FOLLOW_PAGE":
            return await client.follow_page(
                page_url=payload.get("pageUrl", ""),
                fb_uid=fb_uid,
                strategy=strategy_hints,
                dry_run=dry_run,
            )

        elif task_type == "UNFOLLOW_PAGE":
            return await client.unfollow_page(
                page_url=payload.get("pageUrl", ""),
                fb_uid=fb_uid,
                strategy=strategy_hints,
                dry_run=dry_run,
            )

        elif task_type == "SCRAPE_PROFILE":
            return await client.scrape_profile(
                profile_url=payload.get("profileUrl", ""),
                fb_uid=fb_uid,
                strategy=strategy_hints,
            )

        elif task_type == "SCRAPE_GROUP":
            return await client.scrape_group(
                group_url=payload.get("groupUrl", ""),
                fb_uid=fb_uid,
                strategy=strategy_hints,
            )

        elif task_type == "REUP_VIDEO":
            from agent.services.downloader import download_video
            source_url = payload.get("sourceUrl")
            if not source_url:
                return {"error": "sourceUrl is required for REUP_VIDEO"}
            if dry_run:
                return {
                    "success": True,
                    "dryRun": True,
                    "action": "reup_video",
                    "message": "Dry run: would download and post video",
                    "sourceUrl": source_url,
                }
            metadata = await download_video(source_url, task["id"])
            return await client.post_with_media(
                content=payload.get("content", metadata.get("title", "")),
                media_paths=[metadata["local_path"]],
                target_type="REEL",
                target_id=payload.get("targetId"),
                fb_uid=fb_uid,
                strategy=strategy_hints,
                dry_run=dry_run,
            )

        else:
            return {"error": f"Unknown task type: {task_type}"}


# ─── Singleton ──────────────────────────────────────────────

_controller: WorkerController | None = None


def get_worker_controller() -> WorkerController:
    global _controller
    if _controller is None:
        _controller = WorkerController()
    return _controller
