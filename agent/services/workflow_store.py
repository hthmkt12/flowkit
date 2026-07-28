"""Dedicated local Workflow Lab SQLite store; never shares task tables."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


class WorkflowStore:
    def __init__(self, path: str | Path = "runtime/workflow_lab.sqlite3", ttl_seconds: int = 3600) -> None:
        self.path = str(path)
        self.ttl_seconds = max(60, min(int(ttl_seconds), 86400))
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS workflow_captures (id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, fb_uid TEXT, tab_id TEXT, status TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS workflow_events (capture_id TEXT NOT NULL, seq INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(capture_id, seq))")

    def _connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def create_capture(self, capture_id: str, profile_id: str, fb_uid: str | None = None, tab_id: str | None = None) -> dict:
        now = time.time()
        with self._connect() as db:
            if not capture_id.strip() or len(capture_id) > 128 or not profile_id.strip() or len(profile_id) > 128:
                raise ValueError("capture and profile identifiers must be bounded")
            if fb_uid is not None and (not fb_uid.strip() or len(fb_uid) > 128):
                raise ValueError("fb_uid must be bounded")
            if tab_id is not None and (not tab_id.strip() or len(tab_id) > 128):
                raise ValueError("tab_id must be bounded")
            db.execute("INSERT INTO workflow_captures VALUES (?, ?, ?, ?, 'running', ?, ?)", (capture_id.strip(), profile_id.strip(), fb_uid, tab_id, now, now))
        return self.inspect_capture(capture_id)

    def append_event(self, capture_id: str, payload: dict, sequence: int | None = None) -> None:
        if not isinstance(payload, dict) or len(json.dumps(payload, separators=(",", ":"))) > 16384:
            raise ValueError("workflow event must be bounded JSON")
        if any(key.lower() in {"body", "responsebody", "headers", "cookie", "authorization", "postdata"} for key in payload):
            raise ValueError("workflow event contains forbidden secret-bearing fields")
        with self._connect() as db:
            row = db.execute("SELECT status FROM workflow_captures WHERE id = ?", (capture_id,)).fetchone()
            if not row or row["status"] != "running":
                raise ValueError("capture is not running")
            count = db.execute("SELECT COUNT(*) FROM workflow_events WHERE capture_id = ?", (capture_id,)).fetchone()[0]
            if count >= 1000:
                raise ValueError("capture event quota exceeded")
            seq = count if sequence is None else sequence
            if not isinstance(seq, int) or seq < 0 or seq > 1000000:
                raise ValueError("event sequence must be bounded")
            existing = db.execute("SELECT payload FROM workflow_events WHERE capture_id = ? AND seq = ?", (capture_id, seq)).fetchone()
            if existing:
                if existing[0] != json.dumps(payload, separators=(",", ":")):
                    raise ValueError("duplicate sequence has different payload")
                return
            db.execute("INSERT INTO workflow_events VALUES (?, ?, ?)", (capture_id, seq, json.dumps(payload, separators=(",", ":"))))
            db.execute("UPDATE workflow_captures SET updated_at = ? WHERE id = ?", (time.time(), capture_id))

    def list_captures(self, profile_id: str | None = None) -> list[dict]:
        self.gc()
        with self._connect() as db:
            if profile_id:
                rows = db.execute("SELECT id FROM workflow_captures WHERE profile_id = ? ORDER BY created_at DESC", (profile_id,))
            else:
                rows = db.execute("SELECT id FROM workflow_captures ORDER BY created_at DESC")
            return [self.inspect_capture(row[0]) for row in rows]

    def gc(self) -> int:
        cutoff = time.time() - self.ttl_seconds
        with self._connect() as db:
            ids = [row[0] for row in db.execute("SELECT id FROM workflow_captures WHERE updated_at < ?", (cutoff,))]
            for capture_id in ids:
                db.execute("DELETE FROM workflow_events WHERE capture_id = ?", (capture_id,))
                db.execute("DELETE FROM workflow_captures WHERE id = ?", (capture_id,))
            return len(ids)

    def stop_capture(self, capture_id: str) -> dict | None:
        with self._connect() as db:
            db.execute("UPDATE workflow_captures SET status = 'stopped', updated_at = ? WHERE id = ?", (time.time(), capture_id))
        return self.inspect_capture(capture_id)

    def inspect_capture(self, capture_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM workflow_captures WHERE id = ?", (capture_id,)).fetchone()
            if not row:
                return None
            events = [json.loads(item[0]) for item in db.execute("SELECT payload FROM workflow_events WHERE capture_id = ? ORDER BY seq", (capture_id,))]
            return {"id": row["id"], "profileId": row["profile_id"], "fbUid": row["fb_uid"], "tabId": row["tab_id"], "status": row["status"], "events": events}

    def delete_capture(self, capture_id: str) -> bool:
        with self._connect() as db:
            db.execute("DELETE FROM workflow_events WHERE capture_id = ?", (capture_id,))
            changed = db.execute("DELETE FROM workflow_captures WHERE id = ?", (capture_id,)).rowcount
            return changed > 0
