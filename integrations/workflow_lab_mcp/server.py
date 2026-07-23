"""Local-only Workflow Lab MCP facade. Disabled unless WORKFLOW_LAB_MCP_ENABLED=1."""

from __future__ import annotations

import os
from typing import Any

from agent.services.workflow_analyzer import analyze_replayability
from agent.services.workflow_store import WorkflowStore


TOOLS = ("list_captures", "inspect_workflow", "explain_request", "compare_runs", "check_replayability")
_FORBIDDEN = {"cookie", "body", "headers", "authorization", "execute", "promote", "url"}
_ARGUMENTS = {"list_captures": set(), "inspect_workflow": {"captureId"}, "explain_request": {"captureId"}, "check_replayability": {"captureId"}, "compare_runs": {"captureId", "otherCaptureId"}}


class WorkflowLabMCP:
    def __init__(self, store: WorkflowStore | None = None) -> None:
        self.enabled = os.environ.get("WORKFLOW_LAB_MCP_ENABLED", "").lower() in {"1", "true", "yes"}
        self.store = store or WorkflowStore()

    def call(self, tool: str, args: dict[str, Any], profile_id: str) -> dict[str, Any]:
        if not self.enabled:
            raise PermissionError("Workflow Lab MCP is disabled")
        if not isinstance(profile_id, str) or not profile_id.strip() or len(profile_id) > 128:
            raise ValueError("bounded profile_id is required")
        if tool not in TOOLS or not isinstance(args, dict) or set(args) - _ARGUMENTS[tool] or any(key.lower() in _FORBIDDEN for key in args):
            raise ValueError("unsupported or unsafe MCP operation")
        capture_id = args.get("captureId")
        if tool == "list_captures":
            return {"captures": self.store.list_captures(profile_id)[:100]}
        if not isinstance(capture_id, str) or not capture_id.strip() or len(capture_id) > 128:
            raise ValueError("opaque captureId is required")
        capture = self.store.inspect_capture(capture_id)
        if not capture or capture["profileId"] != profile_id:
            raise LookupError("capture not found")
        if tool == "check_replayability":
            return analyze_replayability(capture["events"])
        if tool == "compare_runs":
            return {"observed": True, "captureId": capture_id, "comparison": "unavailable"}
        if tool == "explain_request":
            return {"observed": True, "captureId": capture_id, "explanation": "metadata-only request shape"}
        safe_events = []
        for event in capture["events"][:100]:
            if not isinstance(event, dict):
                continue
            safe_events.append({key: event[key] for key in ("schemaVersion", "captureId", "method", "host", "path", "status", "resourceType", "timingMs", "queryShape", "valueAliases") if key in event})
        return {"id": capture["id"], "status": capture["status"], "events": safe_events, "readOnly": True}


def main() -> None:
    if os.environ.get("WORKFLOW_LAB_MCP_ENABLED", "").lower() not in {"1", "true", "yes"}:
        raise SystemExit("Workflow Lab MCP disabled; set WORKFLOW_LAB_MCP_ENABLED=1 for local stdio use")
    raise SystemExit("stdio launcher is intentionally not auto-started by FBKit")
