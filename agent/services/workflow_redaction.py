"""Secret-safe serialization for Workflow Lab evidence."""

from __future__ import annotations

from .workflow_contract import normalize_capture_event
import hashlib


def _safe_query_key(key: str) -> str:
    lowered = key.lower()
    if any(marker in lowered for marker in ("token", "cookie", "auth", "pass", "secret", "session", "jwt", "fb_dtsg", "lsd", "c_user")):
        return "key_sha256:" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return key[:64]


def redact_capture_event(payload: dict, capture_id: str) -> dict:
    event = normalize_capture_event(payload, capture_id)
    return {
        "schemaVersion": 1,
        "captureId": event.capture_id,
        "method": event.method,
        "host": event.host,
        "path": event.path,
        "status": event.status,
        "resourceType": event.resource_type,
        "timingMs": event.timing_ms,
        "queryShape": [_safe_query_key(key) for key in event.query_shape],
        "valueAliases": {_safe_query_key(key): value for key, value in event.value_aliases.items()},
    }
