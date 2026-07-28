"""Sealed capability boundary for read-only Workflow Lab adapters."""

from __future__ import annotations


class WorkflowReadOnlyCapabilityGate:
    _ALLOW = frozenset({("get_post_metrics", "inspect"), ("read_page_clone", "inspect")})

    def allows(self, adapter: str, operation: str) -> bool:
        return (adapter, operation) in self._ALLOW

    def require(self, adapter: str, operation: str) -> None:
        if not self.allows(adapter, operation):
            raise PermissionError("Workflow Lab capability is read-only and sealed")
