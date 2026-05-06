"""FBKit — CRUD operations for all tables."""
import base64
import fnmatch
import json
import logging
import uuid
from datetime import datetime, date
from json import JSONDecodeError

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from agent.db.schema import get_db
from agent.config import DATA_ENCRYPTION_KEY
from agent.services.safety_gate import enforce_payload, is_mutating_task

logger = logging.getLogger(__name__)

_SENSITIVE_ACCOUNT_FIELDS = {"cookies_data", "session_data"}

_DEV_KEY_FALLBACK = "fbkit-local-dev-key"


def _derive_fernet_key(seed: str) -> bytes:
    """Derive a Fernet-compatible 32-byte key using HKDF."""
    material = seed or _DEV_KEY_FALLBACK
    if material == _DEV_KEY_FALLBACK:
        logger.warning(
            "DATA_ENCRYPTION_KEY not set — using insecure dev fallback. "
            "Set DATA_ENCRYPTION_KEY env var before deploying to production."
        )
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"fbkit-hkdf-salt-v1",
        info=b"fbkit-fernet-key",
    )
    raw = hkdf.derive(material.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


_FERNET = Fernet(_derive_fernet_key(DATA_ENCRYPTION_KEY))


def _new_id() -> str:
    return str(uuid.uuid4())


def _row_to_dict(row) -> dict | None:
    if row is None:
        return None
    return dict(row)


def _encrypt_if_needed(field: str, value):
    if value is None or field not in _SENSITIVE_ACCOUNT_FIELDS:
        return value
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    text = str(value)
    return _FERNET.encrypt(text.encode("utf-8")).decode("utf-8")


def _decrypt_if_needed(field: str, value):
    if value is None or field not in _SENSITIVE_ACCOUNT_FIELDS:
        return value
    try:
        return _FERNET.decrypt(str(value).encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return value


def _decrypt_account_row(data: dict | None) -> dict | None:
    if not data:
        return data
    for field in _SENSITIVE_ACCOUNT_FIELDS:
        if field in data:
            data[field] = _decrypt_if_needed(field, data.get(field))
    return data


def _rows_to_list(rows) -> list[dict]:
    return [dict(r) for r in rows]


def _strip_task_server_fields(payload: dict) -> dict:
    payload.pop("_quotaReserved", None)
    payload.pop("_serverApproved", None)
    payload.pop("approved", None)
    return payload


def _enforce_task_payload_for_insert(task_type: str, raw_payload) -> str | None:
    if raw_payload is None:
        payload = {}
    elif isinstance(raw_payload, str):
        try:
            payload = json.loads(raw_payload or "{}")
        except JSONDecodeError as exc:
            if is_mutating_task(task_type):
                raise ValueError("Mutating task payload must be valid JSON") from exc
            return raw_payload
    elif isinstance(raw_payload, dict):
        payload = dict(raw_payload)
    else:
        if is_mutating_task(task_type):
            raise ValueError("Mutating task payload must be a JSON object")
        return raw_payload

    if not isinstance(payload, dict):
        if is_mutating_task(task_type):
            raise ValueError("Mutating task payload must be a JSON object")
        return raw_payload

    if is_mutating_task(task_type):
        payload = _strip_task_server_fields(payload)
    payload = enforce_payload(task_type, payload)
    return json.dumps(payload) if payload else None


# ─── Account ────────────────────────────────────────────────

async def create_account(name: str, **kwargs) -> dict:
    db = await get_db()
    aid = _new_id()
    cols = ["id", "name"] + list(kwargs.keys())
    vals = [aid, name] + [_encrypt_if_needed(k, v) for k, v in kwargs.items()]
    placeholders = ", ".join("?" * len(cols))
    col_str = ", ".join(cols)
    await db.execute(f"INSERT INTO account ({col_str}) VALUES ({placeholders})", vals)
    await db.commit()
    return await get_account(aid)


async def get_account(account_id: str) -> dict | None:
    db = await get_db()
    cur = await db.execute("SELECT * FROM account WHERE id = ?", (account_id,))
    return _decrypt_account_row(_row_to_dict(await cur.fetchone()))


async def list_accounts(status: str = None) -> list[dict]:
    db = await get_db()
    if status:
        cur = await db.execute("SELECT * FROM account WHERE status = ? ORDER BY updated_at DESC", (status,))
    else:
        cur = await db.execute("SELECT * FROM account ORDER BY updated_at DESC")
    rows = _rows_to_list(await cur.fetchall())
    return [_decrypt_account_row(r) for r in rows]


async def update_account(account_id: str, **kwargs) -> dict | None:
    if not kwargs:
        return await get_account(account_id)
    db = await get_db()
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = [_encrypt_if_needed(k, v) for k, v in kwargs.items()] + [account_id]
    await db.execute(f"UPDATE account SET {sets} WHERE id = ?", vals)
    await db.commit()
    return await get_account(account_id)


async def delete_account(account_id: str) -> bool:
    db = await get_db()
    cur = await db.execute("DELETE FROM account WHERE id = ?", (account_id,))
    await db.commit()
    return cur.rowcount > 0


async def reset_daily_counters(account_id: str):
    """Reset daily rate limit counters."""
    db = await get_db()
    today = date.today().isoformat()
    await db.execute(
        "UPDATE account SET daily_posts=0, daily_messages=0, daily_likes=0, "
        "daily_comments=0, daily_friends=0, daily_reset_at=?, updated_at=? WHERE id=?",
        (today, datetime.utcnow().isoformat(), account_id)
    )
    await db.commit()


async def increment_daily_counter(account_id: str, counter: str):
    """Increment a daily counter (e.g. 'daily_posts')."""
    db = await get_db()
    # Check if we need to reset (new day)
    acc = await get_account(account_id)
    if acc and acc.get("daily_reset_at") != date.today().isoformat():
        await reset_daily_counters(account_id)
    await db.execute(
        f"UPDATE account SET {counter} = {counter} + 1, updated_at = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), account_id)
    )
    await db.commit()


async def reserve_daily_counter(account_id: str, counter: str, units: int, limit: int) -> bool:
    """Atomically reserve daily quota units before a live action runs."""
    if units <= 0:
        return True

    db = await get_db()
    acc = await get_account(account_id)
    if acc and acc.get("daily_reset_at") != date.today().isoformat():
        await reset_daily_counters(account_id)

    cur = await db.execute(
        f"UPDATE account SET {counter} = {counter} + ?, updated_at = ? "
        f"WHERE id = ? AND ({counter} + ?) <= ?",
        (units, datetime.utcnow().isoformat(), account_id, units, limit),
    )
    await db.commit()
    return cur.rowcount == 1


# ─── Post ────────────────────────────────────────────────────

async def create_post(account_id: str, post_type: str = "TEXT", **kwargs) -> dict:
    db = await get_db()
    pid = _new_id()
    cols = ["id", "account_id", "post_type"] + list(kwargs.keys())
    vals = [pid, account_id, post_type] + list(kwargs.values())
    placeholders = ", ".join("?" * len(cols))
    col_str = ", ".join(cols)
    await db.execute(f"INSERT INTO post ({col_str}) VALUES ({placeholders})", vals)
    await db.commit()
    return await get_post(pid)


async def get_post(post_id: str) -> dict | None:
    db = await get_db()
    cur = await db.execute("SELECT * FROM post WHERE id = ?", (post_id,))
    return _row_to_dict(await cur.fetchone())


async def list_posts(account_id: str = None, status: str = None) -> list[dict]:
    db = await get_db()
    conditions, params = [], []
    if account_id:
        conditions.append("account_id = ?")
        params.append(account_id)
    if status:
        conditions.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cur = await db.execute(f"SELECT * FROM post {where} ORDER BY created_at DESC", params)
    return _rows_to_list(await cur.fetchall())


async def update_post(post_id: str, **kwargs) -> dict | None:
    if not kwargs:
        return await get_post(post_id)
    db = await get_db()
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [post_id]
    await db.execute(f"UPDATE post SET {sets} WHERE id = ?", vals)
    await db.commit()
    return await get_post(post_id)


async def claim_scheduled_post(post_id: str, before: str) -> dict | None:
    """Claim one due scheduled post before enqueueing its task."""
    db = await get_db()
    now = datetime.utcnow().isoformat()
    cur = await db.execute(
        "UPDATE post SET status = 'POSTING', updated_at = ? "
        "WHERE id = ? AND status = 'SCHEDULED' AND scheduled_at <= ?",
        (now, post_id, before),
    )
    await db.commit()
    if cur.rowcount != 1:
        return None
    return await get_post(post_id)


async def delete_post(post_id: str) -> bool:
    db = await get_db()
    cur = await db.execute("DELETE FROM post WHERE id = ?", (post_id,))
    await db.commit()
    return cur.rowcount > 0


async def list_scheduled_posts(before: str = None) -> list[dict]:
    """Get posts scheduled before a given datetime (ISO format)."""
    db = await get_db()
    if before:
        cur = await db.execute(
            "SELECT * FROM post WHERE status = 'SCHEDULED' AND scheduled_at <= ? ORDER BY scheduled_at",
            (before,)
        )
    else:
        cur = await db.execute(
            "SELECT * FROM post WHERE status = 'SCHEDULED' ORDER BY scheduled_at"
        )
    return _rows_to_list(await cur.fetchall())


# ─── Message ────────────────────────────────────────────────

async def create_message(account_id: str, recipient_name: str, content: str, **kwargs) -> dict:
    db = await get_db()
    mid = _new_id()
    cols = ["id", "account_id", "recipient_name", "content"] + list(kwargs.keys())
    vals = [mid, account_id, recipient_name, content] + list(kwargs.values())
    placeholders = ", ".join("?" * len(cols))
    col_str = ", ".join(cols)
    await db.execute(f"INSERT INTO message ({col_str}) VALUES ({placeholders})", vals)
    await db.commit()
    return await get_message(mid)


async def get_message(message_id: str) -> dict | None:
    db = await get_db()
    cur = await db.execute("SELECT * FROM message WHERE id = ?", (message_id,))
    return _row_to_dict(await cur.fetchone())


async def list_messages(account_id: str = None, status: str = None) -> list[dict]:
    db = await get_db()
    conditions, params = [], []
    if account_id:
        conditions.append("account_id = ?")
        params.append(account_id)
    if status:
        conditions.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cur = await db.execute(f"SELECT * FROM message {where} ORDER BY created_at DESC", params)
    return _rows_to_list(await cur.fetchall())


async def update_message(message_id: str, **kwargs) -> dict | None:
    if not kwargs:
        return await get_message(message_id)
    db = await get_db()
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [message_id]
    await db.execute(f"UPDATE message SET {sets} WHERE id = ?", vals)
    await db.commit()
    return await get_message(message_id)


async def claim_scheduled_message(message_id: str, before: str) -> dict | None:
    """Claim one due scheduled message before enqueueing its task."""
    db = await get_db()
    now = datetime.utcnow().isoformat()
    cur = await db.execute(
        "UPDATE message SET status = 'SENDING', updated_at = ? "
        "WHERE id = ? AND status = 'SCHEDULED' AND scheduled_at <= ?",
        (now, message_id, before),
    )
    await db.commit()
    if cur.rowcount != 1:
        return None
    return await get_message(message_id)


async def list_scheduled_messages(before: str = None) -> list[dict]:
    """Get messages scheduled before a given datetime (ISO format)."""
    db = await get_db()
    if before:
        cur = await db.execute(
            "SELECT * FROM message WHERE status = 'SCHEDULED' AND scheduled_at <= ? ORDER BY scheduled_at",
            (before,)
        )
    else:
        cur = await db.execute(
            "SELECT * FROM message WHERE status = 'SCHEDULED' ORDER BY scheduled_at"
        )
    return _rows_to_list(await cur.fetchall())


async def delete_message(message_id: str) -> bool:
    db = await get_db()
    cur = await db.execute("DELETE FROM message WHERE id = ?", (message_id,))
    await db.commit()
    return cur.rowcount > 0


# ─── Task ────────────────────────────────────────────────────

async def create_task(
    account_id: str,
    task_type: str,
    *,
    enforce_safety: bool = True,
    **kwargs,
) -> dict:
    if enforce_safety:
        enforced_payload = _enforce_task_payload_for_insert(task_type, kwargs.get("payload"))
        if enforced_payload is None:
            kwargs.pop("payload", None)
        else:
            kwargs["payload"] = enforced_payload

    db = await get_db()
    tid = _new_id()
    cols = ["id", "account_id", "task_type"] + list(kwargs.keys())
    vals = [tid, account_id, task_type] + list(kwargs.values())
    placeholders = ", ".join("?" * len(cols))
    col_str = ", ".join(cols)
    await db.execute(f"INSERT INTO task ({col_str}) VALUES ({placeholders})", vals)
    await db.commit()
    return await get_task(tid)


async def get_task(task_id: str) -> dict | None:
    db = await get_db()
    cur = await db.execute("SELECT * FROM task WHERE id = ?", (task_id,))
    return _row_to_dict(await cur.fetchone())


async def list_tasks(status: str = None, task_type: str = None, account_id: str = None) -> list[dict]:
    db = await get_db()
    conditions, params = [], []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if task_type:
        conditions.append("task_type = ?")
        params.append(task_type)
    if account_id:
        conditions.append("account_id = ?")
        params.append(account_id)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cur = await db.execute(
        f"SELECT * FROM task {where} ORDER BY priority DESC, created_at ASC", params
    )
    return _rows_to_list(await cur.fetchall())


async def update_task(task_id: str, **kwargs) -> dict | None:
    if not kwargs:
        return await get_task(task_id)
    db = await get_db()
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [task_id]
    await db.execute(f"UPDATE task SET {sets} WHERE id = ?", vals)
    await db.commit()
    return await get_task(task_id)


async def approve_pending_task(task_id: str, payload: str) -> dict | None:
    """Update approval payload only if the task is still pending."""
    db = await get_db()
    cur = await db.execute(
        "UPDATE task SET payload = ?, updated_at = ? WHERE id = ? AND status = 'PENDING'",
        (payload, datetime.utcnow().isoformat(), task_id),
    )
    await db.commit()
    if cur.rowcount != 1:
        return None
    return await get_task(task_id)


async def get_next_pending_task() -> dict | None:
    """Get the highest-priority pending task that's ready to run."""
    db = await get_db()
    now = datetime.utcnow().isoformat()
    cur = await db.execute(
        "SELECT * FROM task WHERE status = 'PENDING' "
        "AND (scheduled_at IS NULL OR scheduled_at <= ?) "
        "ORDER BY priority DESC, created_at ASC LIMIT 1",
        (now,)
    )
    return _row_to_dict(await cur.fetchone())


async def claim_next_pending_task() -> dict | None:
    """Atomically move the next ready task to PROCESSING and return it."""
    db = await get_db()
    now = datetime.utcnow().isoformat()
    cur = await db.execute(
        "SELECT id FROM task WHERE status = 'PENDING' "
        "AND (scheduled_at IS NULL OR scheduled_at <= ?) "
        "ORDER BY priority DESC, created_at ASC LIMIT 1",
        (now,),
    )
    row = await cur.fetchone()
    if row is None:
        return None

    task_id = row["id"]
    cur = await db.execute(
        "UPDATE task SET status = 'PROCESSING', started_at = ?, updated_at = ? "
        "WHERE id = ? AND status = 'PENDING'",
        (now, now, task_id),
    )
    await db.commit()
    if cur.rowcount != 1:
        return None
    return await get_task(task_id)


async def cancel_task(task_id: str) -> dict | None:
    return await update_task(task_id, status="CANCELLED")


# ─── FB Group ───────────────────────────────────────────────

async def create_group(account_id: str, name: str, **kwargs) -> dict:
    db = await get_db()
    gid = _new_id()
    cols = ["id", "account_id", "name"] + list(kwargs.keys())
    vals = [gid, account_id, name] + list(kwargs.values())
    placeholders = ", ".join("?" * len(cols))
    col_str = ", ".join(cols)
    await db.execute(f"INSERT INTO fb_group ({col_str}) VALUES ({placeholders})", vals)
    await db.commit()
    return await get_group(gid)


async def get_group(group_id: str) -> dict | None:
    db = await get_db()
    cur = await db.execute("SELECT * FROM fb_group WHERE id = ?", (group_id,))
    return _row_to_dict(await cur.fetchone())


async def list_groups(account_id: str = None) -> list[dict]:
    db = await get_db()
    if account_id:
        cur = await db.execute(
            "SELECT * FROM fb_group WHERE account_id = ? ORDER BY name", (account_id,)
        )
    else:
        cur = await db.execute("SELECT * FROM fb_group ORDER BY name")
    return _rows_to_list(await cur.fetchall())


# ─── Activity Log ───────────────────────────────────────────

async def log_activity(account_id: str, action: str, detail: str = None):
    db = await get_db()
    await db.execute(
        "INSERT INTO activity_log (account_id, action, detail) VALUES (?, ?, ?)",
        (account_id, action, detail)
    )
    await db.commit()


async def list_activities(account_id: str = None, limit: int = 50) -> list[dict]:
    db = await get_db()
    if account_id:
        cur = await db.execute(
            "SELECT * FROM activity_log WHERE account_id = ? ORDER BY created_at DESC LIMIT ?",
            (account_id, limit)
        )
    else:
        cur = await db.execute(
            "SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?", (limit,)
        )
    return _rows_to_list(await cur.fetchall())


async def get_task_stats(account_id: str = None) -> dict:
    """Get aggregated task counts by status."""
    db = await get_db()
    if account_id:
        cur = await db.execute(
            "SELECT status, COUNT(*) as cnt FROM task WHERE account_id = ? GROUP BY status",
            (account_id,)
        )
    else:
        cur = await db.execute("SELECT status, COUNT(*) as cnt FROM task GROUP BY status")
    rows = await cur.fetchall()
    return {row["status"]: row["cnt"] for row in rows}


async def delete_task(task_id: str) -> bool:
    db = await get_db()
    cur = await db.execute("DELETE FROM task WHERE id = ?", (task_id,))
    await db.commit()
    return cur.rowcount > 0


# ─── Seed Campaign ───────────────────────────────────────────

async def create_seed_campaign(name: str, config: dict, **kwargs) -> dict:
    db = await get_db()
    cid = _new_id()
    await db.execute(
        "INSERT INTO seed_campaign (id, name, config, stats) VALUES (?, ?, ?, ?)",
        (cid, name, json.dumps(config), json.dumps({"total": 0, "success": 0, "failed": 0}))
    )
    await db.commit()
    return await get_seed_campaign(cid)


async def get_seed_campaign(campaign_id: str) -> dict | None:
    db = await get_db()
    cur = await db.execute("SELECT * FROM seed_campaign WHERE id = ?", (campaign_id,))
    return _row_to_dict(await cur.fetchone())


async def list_seed_campaigns(status: str = None) -> list[dict]:
    db = await get_db()
    if status:
        cur = await db.execute(
            "SELECT * FROM seed_campaign WHERE status = ? ORDER BY created_at DESC", (status,)
        )
    else:
        cur = await db.execute("SELECT * FROM seed_campaign ORDER BY created_at DESC")
    return _rows_to_list(await cur.fetchall())


async def update_seed_campaign(campaign_id: str, **kwargs) -> dict | None:
    if not kwargs:
        return await get_seed_campaign(campaign_id)
    db = await get_db()
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [campaign_id]
    await db.execute(f"UPDATE seed_campaign SET {sets} WHERE id = ?", vals)
    await db.commit()
    return await get_seed_campaign(campaign_id)


async def delete_seed_campaign(campaign_id: str) -> bool:
    db = await get_db()
    cur = await db.execute("DELETE FROM seed_campaign WHERE id = ?", (campaign_id,))
    await db.commit()
    return cur.rowcount > 0


# ─── Spy Target ─────────────────────────────────────────────

async def create_spy_target(page_name: str, page_id: str, **kwargs) -> dict:
    db = await get_db()
    tid = _new_id()
    cols = ["id", "page_name", "page_id"] + list(kwargs.keys())
    vals = [tid, page_name, page_id] + list(kwargs.values())
    placeholders = ", ".join("?" * len(cols))
    col_str = ", ".join(cols)
    await db.execute(f"INSERT INTO spy_target ({col_str}) VALUES ({placeholders})", vals)
    await db.commit()
    return await get_spy_target(tid)


async def get_spy_target(target_id: str) -> dict | None:
    db = await get_db()
    cur = await db.execute("SELECT * FROM spy_target WHERE id = ?", (target_id,))
    return _row_to_dict(await cur.fetchone())


async def list_spy_targets(status: str = None) -> list[dict]:
    db = await get_db()
    if status:
        cur = await db.execute(
            "SELECT * FROM spy_target WHERE status = ? ORDER BY created_at DESC", (status,)
        )
    else:
        cur = await db.execute("SELECT * FROM spy_target ORDER BY created_at DESC")
    return _rows_to_list(await cur.fetchall())


async def update_spy_target(target_id: str, **kwargs) -> dict | None:
    if not kwargs:
        return await get_spy_target(target_id)
    db = await get_db()
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [target_id]
    await db.execute(f"UPDATE spy_target SET {sets} WHERE id = ?", vals)
    await db.commit()
    return await get_spy_target(target_id)


async def delete_spy_target(target_id: str) -> bool:
    db = await get_db()
    cur = await db.execute("DELETE FROM spy_target WHERE id = ?", (target_id,))
    await db.commit()
    return cur.rowcount > 0


# ── Spy Ads ──────────────────────────────────────────────────────────────────

async def list_spy_ads(target_id: str | None = None, limit: int = 200) -> list[dict]:
    db = await get_db()
    if target_id:
        cur = await db.execute(
            "SELECT * FROM spy_ad WHERE target_id = ? ORDER BY first_seen DESC LIMIT ?",
            (target_id, limit),
        )
    else:
        cur = await db.execute(
            "SELECT * FROM spy_ad ORDER BY first_seen DESC LIMIT ?", (limit,)
        )
    return _rows_to_list(await cur.fetchall())


# ─── Task Strategy (learned automation patterns) ────────────

async def get_strategy(task_type: str, url_pattern: str = "*") -> dict | None:
    """Get the best matching strategy for a task type + URL pattern."""
    # Try exact match first, then stored URL-family patterns, then wildcard fallback.
    row = await _get_strategy_exact(task_type, url_pattern)
    if row:
        return row
    row = await _get_strategy_pattern_match(task_type, url_pattern)
    if row:
        return row
    # Fallback to wildcard
    if url_pattern != "*":
        row = await _get_strategy_exact(task_type, "*")
        if row:
            return row
    return None


async def upsert_strategy(
    task_type: str,
    url_pattern: str = "*",
    selectors: dict | None = None,
    wait_strategies: list | None = None,
    workarounds: list | None = None,
    notes: str | None = None,
) -> dict:
    """Create or update a strategy for a task type + URL pattern."""
    db = await get_db()
    existing = await _get_strategy_exact(task_type, url_pattern)
    now = datetime.utcnow().isoformat()

    if existing:
        # Merge: extend lists, update dicts
        merged_selectors = _merge_dicts(
            json.loads(existing.get("selectors") or "{}") if isinstance(existing.get("selectors"), str) else (existing.get("selectors") or {}),
            selectors or {},
        )
        merged_waits = _merge_lists(
            existing.get("wait_strategies") or [],
            wait_strategies or [],
        )
        merged_workarounds = _merge_lists(
            existing.get("workarounds") or [],
            workarounds or [],
        )
        merged_notes = notes if notes else existing.get("notes")

        await db.execute(
            "UPDATE task_strategy SET selectors=?, wait_strategies=?, "
            "workarounds=?, notes=?, updated_at=? "
            "WHERE id=?",
            (
                json.dumps(merged_selectors, ensure_ascii=False),
                json.dumps(merged_waits, ensure_ascii=False),
                json.dumps(merged_workarounds, ensure_ascii=False),
                merged_notes,
                now,
                existing["id"],
            ),
        )
        await db.commit()
        return await _get_strategy_by_id(existing["id"])
    else:
        sid = _new_id()
        await db.execute(
            "INSERT INTO task_strategy (id, task_type, url_pattern, selectors, "
            "wait_strategies, workarounds, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                sid,
                task_type,
                url_pattern,
                json.dumps(selectors or {}, ensure_ascii=False),
                json.dumps(wait_strategies or [], ensure_ascii=False),
                json.dumps(workarounds or [], ensure_ascii=False),
                notes,
            ),
        )
        await db.commit()
        return await _get_strategy_by_id(sid)


async def record_strategy_outcome(
    task_type: str, url_pattern: str = "*", success: bool = True
) -> None:
    """Increment success/fail count and update timestamps."""
    db = await get_db()
    now = datetime.utcnow().isoformat()
    if success:
        await db.execute(
            "UPDATE task_strategy SET success_count = success_count + 1, "
            "last_success = ?, updated_at = ? WHERE task_type = ? AND url_pattern = ?",
            (now, now, task_type, url_pattern),
        )
    else:
        await db.execute(
            "UPDATE task_strategy SET fail_count = fail_count + 1, "
            "last_failure = ?, updated_at = ? WHERE task_type = ? AND url_pattern = ?",
            (now, now, task_type, url_pattern),
        )
    await db.commit()


async def list_strategies(task_type: str | None = None) -> list[dict]:
    """List all strategies, optionally filtered by task_type."""
    db = await get_db()
    if task_type:
        cur = await db.execute(
            "SELECT * FROM task_strategy WHERE task_type = ? ORDER BY success_count DESC",
            (task_type,),
        )
    else:
        cur = await db.execute(
            "SELECT * FROM task_strategy ORDER BY task_type, success_count DESC"
        )
    return [_deserialize_strategy(dict(r)) for r in await cur.fetchall()]


async def _get_strategy_exact(task_type: str, url_pattern: str) -> dict | None:
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM task_strategy WHERE task_type = ? AND url_pattern = ?",
        (task_type, url_pattern),
    )
    row = _row_to_dict(await cur.fetchone())
    return _deserialize_strategy(row) if row else None


async def _get_strategy_pattern_match(task_type: str, url_pattern: str) -> dict | None:
    """Find the most specific stored wildcard pattern matching a concrete URL."""
    if url_pattern == "*":
        return None
    db = await get_db()
    cur = await db.execute(
        "SELECT * FROM task_strategy WHERE task_type = ? AND url_pattern != '*' "
        "AND instr(url_pattern, '*') > 0 "
        "ORDER BY length(url_pattern) DESC, success_count DESC",
        (task_type,),
    )
    for row in await cur.fetchall():
        strategy = _row_to_dict(row)
        pattern = strategy.get("url_pattern")
        if pattern and fnmatch.fnmatchcase(url_pattern, pattern):
            return _deserialize_strategy(strategy)
    return None


async def _get_strategy_by_id(strategy_id: str) -> dict | None:
    db = await get_db()
    cur = await db.execute("SELECT * FROM task_strategy WHERE id = ?", (strategy_id,))
    row = _row_to_dict(await cur.fetchone())
    return _deserialize_strategy(row) if row else None


def _deserialize_strategy(row: dict | None) -> dict | None:
    """Parse JSON fields in a strategy row."""
    if not row:
        return None
    for field in ("selectors", "wait_strategies", "workarounds"):
        val = row.get(field)
        if isinstance(val, str):
            try:
                row[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return row


def _merge_dicts(base: dict, update: dict) -> dict:
    """Shallow merge, update wins on conflict."""
    merged = {**base}
    merged.update(update)
    return merged


def _merge_lists(base: list, update: list) -> list:
    """Deduplicate-merge two lists, preserving order."""
    seen = set()
    result = []
    for item in base + update:
        key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


# ─── Task Trace (structured execution logs) ─────────────────

async def create_trace(
    task_id: str,
    task_type: str,
    status: str,
    account_id: str | None = None,
    duration_ms: int | None = None,
    steps: list | None = None,
    error_detail: str | None = None,
    strategy_id: str | None = None,
) -> dict:
    """Record a structured execution trace for a task."""
    db = await get_db()
    await db.execute(
        "INSERT INTO task_trace (task_id, task_type, account_id, status, "
        "duration_ms, steps, error_detail, strategy_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            task_id,
            task_type,
            account_id,
            status,
            duration_ms,
            json.dumps(steps or [], ensure_ascii=False),
            error_detail,
            strategy_id,
        ),
    )
    await db.commit()
    cur = await db.execute(
        "SELECT * FROM task_trace WHERE task_id = ? ORDER BY id DESC LIMIT 1",
        (task_id,),
    )
    return _row_to_dict(await cur.fetchone())


async def list_traces(
    task_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List execution traces with optional filters."""
    db = await get_db()
    conditions, params = [], []
    if task_type:
        conditions.append("task_type = ?")
        params.append(task_type)
    if status:
        conditions.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)
    cur = await db.execute(
        f"SELECT * FROM task_trace {where} ORDER BY created_at DESC LIMIT ?",
        params,
    )
    return _rows_to_list(await cur.fetchall())
