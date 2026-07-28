"""Source-controlled, read-only adapter registry for Workflow Lab."""

from __future__ import annotations

from .workflow_capability import WorkflowReadOnlyCapabilityGate


class WorkflowAdapterRegistry:
    def __init__(self, gate: WorkflowReadOnlyCapabilityGate | None = None) -> None:
        if gate is not None and type(gate) is not WorkflowReadOnlyCapabilityGate:
            raise TypeError("Workflow Lab uses the sealed capability gate")
        self._gate = gate or WorkflowReadOnlyCapabilityGate()

    def list_adapters(self) -> list[str]:
        return ["get_post_metrics", "read_page_clone"]

    def inspect(self, command: str, evidence: dict) -> dict:
        self._gate.require(command, "inspect")
        if not isinstance(evidence, dict):
            raise ValueError("adapter evidence must be an object")
        mode = "DOM_FALLBACK" if command == "get_post_metrics" else "SCRAPE_PAGE_CLONE"
        return {"schemaVersion": 1, "command": command, "mode": mode, "readOnly": True}

    def execute(self, command: str, payload: dict) -> None:
        self._gate.require(command, "execute")
