"""Analysis-only replayability classifier; it never constructs or sends requests."""

from __future__ import annotations

from .workflow_contract import Replayability


def analyze_replayability(events: list[dict]) -> dict:
    if not isinstance(events, list) or len(events) > 1000:
        raise ValueError("events must be a bounded list")
    if not events:
        mode = Replayability.NON_REPLAYABLE
    elif any(event.get("method") in {"POST", "PUT", "PATCH", "DELETE"} for event in events if isinstance(event, dict)):
        mode = Replayability.BROWSER_SESSION_REQUIRED
    elif any(event.get("resourceType") == "Document" for event in events if isinstance(event, dict)):
        mode = Replayability.DOM_FALLBACK
    else:
        mode = Replayability.OBSERVED_REQUEST_CANDIDATE
    return {
        "schemaVersion": 1,
        "replayability": mode.value,
        "readOnly": True,
        "executeAllowed": False,
        "reason": "metadata-only analysis; no response body or executor",
        "eventCount": len(events),
    }
