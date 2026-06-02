"""FBKit — Task queue processor.

Polls for pending tasks, dispatches to FBClient, updates results.
Enforces rate limits and human-like session management.
"""
import asyncio
import inspect
import json
import logging
import traceback
from datetime import date

from agent.config import (
    MAX_CONCURRENT_TASKS,
    MAX_RETRIES,
    POLL_INTERVAL,
)
from agent import config
from agent.db import crud
from agent.services.fb_client import get_fb_client
from agent.services.human_delay import action_delay, long_delay, get_session_manager
from agent.services.event_bus import event_bus
from agent.services.notifier import get_notifier
from agent.services.safety_gate import dry_run_from_payload, enforce_payload, is_mutating_task
from agent.utils.time import utc_from_timestamp_iso, utc_now_iso, utc_now_ms

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
    if payload.get("postUrl"):
        return payload["postUrl"]

    target_type = payload.get("targetType")
    target_id = payload.get("targetId")
    if target_type and target_id:
        return f"{str(target_type).upper()}:{target_id}"

    for key in ("groupUrl", "pageUrl", "profileUrl", "sourceUrl"):
        if payload.get(key):
            return payload[key]

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

    def __init__(self, node_id: str | None = None, live_lease_heartbeat_seconds: float | None = None):
        self.node_id = node_id or config.FBKIT_NODE_ID
        requested_heartbeat_seconds = (
            live_lease_heartbeat_seconds
            if live_lease_heartbeat_seconds is not None
            else config.LIVE_ACCOUNT_LEASE_HEARTBEAT_SECONDS
        )
        self.live_lease_heartbeat_seconds = min(
            requested_heartbeat_seconds,
            max(5, config.LIVE_ACCOUNT_LEASE_TTL_SECONDS / 2),
        )
        self._shutdown = False
        self._active_count = 0
        self._active_live_account_ids: set[str] = set()
        self.last_rate_limit_error: str | None = None

    @property
    def active_count(self) -> int:
        return self._active_count

    @property
    def active_live_account_ids(self) -> set[str]:
        return set(self._active_live_account_ids)

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
                if not client.has_fresh_session:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                # Respect concurrency limit
                if self._active_count >= MAX_CONCURRENT_TASKS:
                    await asyncio.sleep(1)
                    continue

                # Claim next task before launching async processing to avoid duplicate dispatch.
                task = await crud.claim_next_pending_task(
                    self._active_live_account_ids,
                    node_id=self.node_id,
                    live_lease_ttl_seconds=config.LIVE_ACCOUNT_LEASE_TTL_SECONDS,
                )
                if task is None:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue
                prepared = await self._prepare_claimed_task(task)
                if prepared is None:
                    continue
                task, live_account_id, live_lease = prepared

                # Process task
                self._active_count += 1
                asyncio.create_task(self._process_task(task, live_account_id=live_account_id, live_lease=live_lease))

            except Exception as e:
                logger.error("Worker loop error: %s", e)
                await asyncio.sleep(POLL_INTERVAL)

        logger.info("Worker stopped")

    async def _check_rate_limit(self, task: dict) -> bool:
        """Reserve live-action quota for a task unless Safety Gate forces dry-run."""
        self.last_rate_limit_error = None
        task_type = task["task_type"]
        payload = json.loads(task.get("payload") or "{}") if task.get("payload") else {}
        payload = enforce_payload(task_type, payload)
        if dry_run_from_payload(payload):
            return True

        if is_mutating_task(task_type):
            # Bypass auth checks for local pilot testing
            import sys
            if "pytest" in sys.modules:
                if not config.API_AUTH_ENABLED or not config.WS_AUTH_ENABLED:
                    self.last_rate_limit_error = "Live dispatch requires API_AUTH_ENABLED and WS_AUTH_ENABLED"
                    return False
            
            from agent.services.safety_gate import truthy
            local_approval = truthy(payload.get("localApprovalRequired", True))
            if local_approval:
                arm = await crud.get_active_live_arm(payload.get("_liveArmId"), task.get("account_id"), task_type)
                if not arm:
                    self.last_rate_limit_error = "Live mutating task requires an active matching live arm"
                    return False
            fb_uid = None
            if task.get("account_id"):
                account = await crud.get_account(task["account_id"])
                if account:
                    fb_uid = account.get("fb_uid")
            if not fb_uid:
                self.last_rate_limit_error = "Live mutating task requires account fb_uid for exact routing"
                return False
            client = get_fb_client()
            if not client.session_live_guard_enabled(fb_uid=fb_uid):
                self.last_rate_limit_error = "Extension live-action guard is disabled or unknown"
                return False

        counter_field = _COUNTER_MAP.get(task_type)
        if not counter_field:
            return True  # No rate limit for this task type
        limit_key = _RATE_LIMITS.get(counter_field)
        limit = getattr(config, limit_key, 999) if limit_key else 999
        try:
            units = _quota_units_for_task(task_type, payload)
        except ValueError as exc:
            logger.warning("Invalid quota payload for %s: %s", task_type, exc)
            self.last_rate_limit_error = str(exc)
            return False
        reservation = payload.get("_quotaReserved") or {}
        if (
            reservation.get("counter") == counter_field
            and int(reservation.get("units", 0)) >= units
            and reservation.get("date") == date.today().isoformat()
        ):
            return True

        reserved = await crud.reserve_daily_counter(
            task["account_id"],
            counter_field,
            units,
            limit,
        )
        if reserved and task.get("id"):
            payload["_quotaReserved"] = {
                "counter": counter_field,
                "units": units,
                "date": date.today().isoformat(),
            }
            await crud.update_task(task["id"], payload=json.dumps(payload))
        if not reserved:
            self.last_rate_limit_error = "Daily rate limit exceeded"
        return reserved

    async def _fail_task_for_rate_limit(self, task: dict):
        """Persist the specific preflight/quota reason for skipped tasks."""
        reason = self.last_rate_limit_error or "Daily rate limit exceeded"
        logger.warning(
            "Task preflight failed for %s (account %s): %s",
            task["task_type"],
            (task.get("account_id") or "")[:8],
            reason,
        )
        await crud.update_task(task["id"], status="FAILED", error_message=reason)

    async def _handle_preflight_failure(self, task: dict, live_lease: dict | None = None):
        """Fail pre-dispatch tasks and release any DB lease acquired at claim time."""
        live_lease = live_lease or task.pop("_live_account_lease", None)
        try:
            await self._fail_task_for_rate_limit(task)
        finally:
            if live_lease:
                try:
                    await crud.release_live_account_lease(
                        live_lease["account_id"],
                        live_lease["task_id"],
                        live_lease["node_id"],
                    )
                except Exception as exc:
                    logger.error("Failed to release live account lease after preflight failure: %s", exc)

    async def _prepare_claimed_task(self, task: dict) -> tuple[dict, str | None, dict | None] | None:
        """Run pre-dispatch checks and return processing metadata, cleaning leases on failure."""
        live_lease = task.pop("_live_account_lease", None)
        try:
            if not await self._check_rate_limit(task):
                await self._handle_preflight_failure(task, live_lease=live_lease)
                return None
            live_account_id = self._mark_live_account_if_needed(task)
            return task, live_account_id, live_lease
        except Exception as exc:
            self.last_rate_limit_error = str(exc)[:500]
            await self._handle_preflight_failure(task, live_lease=live_lease)
            return None

    def _mark_live_account_if_needed(self, task: dict) -> str | None:
        """Track one active live mutating task per account before async dispatch."""
        account_id = task.get("account_id")
        if not account_id or not is_mutating_task(task.get("task_type", "")):
            return None
        payload = json.loads(task.get("payload") or "{}") if task.get("payload") else {}
        payload = enforce_payload(task["task_type"], payload)
        if dry_run_from_payload(payload):
            return None
        self._active_live_account_ids.add(account_id)
        return account_id

    def _clear_live_account(self, account_id: str | None):
        if account_id:
            self._active_live_account_ids.discard(account_id)

    async def _heartbeat_live_account_lease(self, live_lease: dict):
        """Refresh a live account lease while a long live task is processing."""
        try:
            while True:
                await asyncio.sleep(self.live_lease_heartbeat_seconds)
                refreshed = await crud.refresh_live_account_lease(
                    live_lease["account_id"],
                    live_lease["task_id"],
                    live_lease["node_id"],
                    config.LIVE_ACCOUNT_LEASE_TTL_SECONDS,
                )
                if refreshed is None:
                    logger.warning(
                        "Live account lease heartbeat stopped for account=%s task=%s node=%s",
                        live_lease.get("account_id"),
                        live_lease.get("task_id"),
                        live_lease.get("node_id"),
                    )
                    return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Live account lease heartbeat failed: %s", exc)
            return

    async def _process_task(
        self,
        task: dict,
        live_account_id: str | None = None,
        live_lease: dict | None = None,
    ):
        """Process a single task."""
        task_id = task["id"]
        task_type = task["task_type"]
        started_at_ms = utc_now_ms()
        strategy = None
        strategy_id = None
        strategy_url = "*"
        lease_heartbeat_task = None

        try:
            if live_lease:
                lease_heartbeat_task = asyncio.create_task(self._heartbeat_live_account_lease(live_lease))
            session = get_session_manager()
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

            # Mark as processing
            await crud.update_task(task_id, status="PROCESSING",
                                   started_at=utc_now_iso())
            await event_bus.emit("task_started", {"task_id": task_id, "type": task_type})

            if is_mutating_task(task_type) and not is_dry_run and not fb_uid:
                raise ValueError("Validation: fb_uid required for live mutating task")

            # Human-like delay before action
            delay_result = action_delay()
            if inspect.isawaitable(delay_result):
                await delay_result

            # Dispatch to handler
            result = await self._dispatch(task_type, payload, task, fb_uid=fb_uid,
                                          strategy=strategy)

            if result.get("error"):
                raise Exception(result["error"])

            # Success
            duration_ms = utc_now_ms() - started_at_ms
            await crud.update_task(
                task_id,
                status="COMPLETED",
                completed_at=utc_now_iso(),
                result=json.dumps(result),
            )
            
            from agent.services.health_monitor import get_health_monitor
            if task.get("account_id"):
                get_health_monitor().record_success(task["account_id"])

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
            duration_ms = utc_now_ms() - started_at_ms
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
                    "recorded_at": utc_now_iso(),
                }],
            )

            if error_class == "RETRYABLE" and retry_count < max_retries:
                delay_s = _next_retry_delay_s(retry_count)
                scheduled_at = utc_from_timestamp_iso((utc_now_ms() / 1000) + delay_s)
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
                    completed_at=utc_now_iso(),
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
                
                from agent.services.health_monitor import get_health_monitor
                if task.get("account_id"):
                    monitor = get_health_monitor()
                    if "checkpoint" in error_message.lower() or "security check" in error_message.lower():
                        await monitor.record_checkpoint(task["account_id"])
                    else:
                        await monitor.record_failure(task["account_id"], error_message)

                # Telegram alert for permanent failures
                notifier = get_notifier()
                asyncio.create_task(notifier.notify_task_failed(task, error_message))

        finally:
            if lease_heartbeat_task:
                lease_heartbeat_task.cancel()
                try:
                    await lease_heartbeat_task
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    logger.error("Live account lease heartbeat cleanup observed failure: %s", exc)
            if live_lease:
                try:
                    await crud.release_live_account_lease(
                        live_lease["account_id"],
                        live_lease["task_id"],
                        live_lease["node_id"],
                    )
                except Exception as exc:
                    logger.error("Failed to release live account lease: %s", exc)
            self._clear_live_account(live_account_id)
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

        if is_mutating_task(task_type) and not dry_run:
            # Bypass auth checks for local pilot testing
            import sys
            if "pytest" in sys.modules:
                if not config.API_AUTH_ENABLED or not config.WS_AUTH_ENABLED:
                    return {"error": "Live dispatch requires API_AUTH_ENABLED and WS_AUTH_ENABLED"}
            arm = await crud.get_active_live_arm(payload.get("_liveArmId"), task.get("account_id"), task_type)
            if not arm:
                return {"error": "Live mutating task requires an active matching live arm"}
            if not client.session_live_guard_enabled(fb_uid=fb_uid):
                return {"error": "Extension live-action guard is disabled or unknown"}

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
