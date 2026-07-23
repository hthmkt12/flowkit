"""Positive-schema contracts for the local, read-only Workflow Lab."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import parse_qsl, urlsplit


_EVENT_KEYS = {"method", "url", "status", "resourceType", "timingMs", "responseBody"}
_DRAFT_KEYS = {"name", "adapter", "sourceCaptureId", "steps", "ttlSeconds", "evidenceRefs"}
_ADAPTERS = {"get_post_metrics", "read_page_clone"}


class Replayability(StrEnum):
    DOM_FALLBACK = "DOM_FALLBACK"
    OBSERVED_REQUEST_CANDIDATE = "OBSERVED_REQUEST_CANDIDATE"
    TOKEN_REFRESH_REQUIRED = "TOKEN_REFRESH_REQUIRED"
    BROWSER_SESSION_REQUIRED = "BROWSER_SESSION_REQUIRED"
    NON_REPLAYABLE = "NON_REPLAYABLE"
    MUTATION_BLOCKED = "MUTATION_BLOCKED"


@dataclass(frozen=True)
class CaptureEvent:
    capture_id: str
    method: str
    host: str
    path: str
    status: int | None
    resource_type: str
    timing_ms: float | None
    query_shape: list[str]
    value_aliases: dict[str, str]


@dataclass(frozen=True)
class WorkflowDraft:
    name: str
    adapter: str
    source_capture_id: str
    read_only: bool = True
    schema_version: int = 1
    steps: tuple[str, ...] = ()
    ttl_seconds: int = 3600
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowEnvelope:
    schema_version: int
    risk: str
    replayability: Replayability
    ttl_seconds: int
    evidence_refs: tuple[str, ...]


def normalize_capture_event(payload: dict, capture_id: str) -> CaptureEvent:
    if not isinstance(payload, dict) or not isinstance(capture_id, str) or not capture_id.strip():
        raise ValueError("capture event and capture_id are required")
    unknown = set(payload) - _EVENT_KEYS
    if unknown:
        raise ValueError("unsupported capture fields: " + ", ".join(sorted(unknown)))
    if "responseBody" in payload:
        raise ValueError("response body is not accepted")
    method = payload.get("method", "GET")
    if not isinstance(method, str) or method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
        raise ValueError("unsupported HTTP method")
    raw_url = payload.get("url")
    if not isinstance(raw_url, str) or len(raw_url) > 4096:
        raise ValueError("url must be a bounded string")
    parsed = urlsplit(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("url must be an absolute HTTP URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("url contains credentials or fragment")
    host = parsed.hostname.lower().rstrip(".")
    if not (host == "facebook.com" or host.endswith(".facebook.com") or host == "fbcdn.net" or host.endswith(".fbcdn.net")):
        raise ValueError("url must use an approved host")
    query_shape = tuple(sorted({key[:128] for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}))
    aliases = {key: "v1" for key in query_shape}
    status = payload.get("status")
    if status is not None and (isinstance(status, bool) or not isinstance(status, int) or not 100 <= status <= 599):
        raise ValueError("status must be an HTTP status")
    timing = payload.get("timingMs")
    if timing is not None and (isinstance(timing, bool) or not isinstance(timing, (int, float)) or timing < 0 or timing > 600000):
        raise ValueError("timingMs must be bounded")
    resource_type = payload.get("resourceType", "Other")
    if not isinstance(resource_type, str):
        raise ValueError("resourceType must be a string")
    return CaptureEvent(
        capture_id=capture_id.strip()[:128], method=method.upper(), host=host,
        path=(parsed.path or "/")[:2048], status=status,
        resource_type=resource_type[:64],
        timing_ms=float(timing) if timing is not None else None,
        query_shape=list(query_shape), value_aliases=aliases,
    )


def normalize_workflow_draft(payload: dict) -> WorkflowDraft:
    if not isinstance(payload, dict):
        raise ValueError("workflow draft must be an object")
    unknown = set(payload) - _DRAFT_KEYS
    if unknown:
        raise ValueError("unsupported workflow draft fields: " + ", ".join(sorted(unknown)))
    name, adapter, capture_id = (payload.get("name"), payload.get("adapter"), payload.get("sourceCaptureId"))
    if not all(isinstance(value, str) and value.strip() for value in (name, adapter, capture_id)):
        raise ValueError("name, adapter, and sourceCaptureId are required")
    if adapter not in _ADAPTERS:
        raise ValueError("unsupported workflow adapter")
    steps = payload.get("steps", [])
    refs = payload.get("evidenceRefs", [])
    ttl = payload.get("ttlSeconds", 3600)
    if not isinstance(steps, list) or len(steps) > 32 or any(not isinstance(item, str) or not item.strip() for item in steps):
        raise ValueError("steps must be a bounded list of strings")
    if not isinstance(refs, list) or len(refs) > 64 or any(not isinstance(item, str) or not item.strip() for item in refs):
        raise ValueError("evidenceRefs must be a bounded list of strings")
    if isinstance(ttl, bool) or not isinstance(ttl, int) or ttl < 60 or ttl > 86400:
        raise ValueError("ttlSeconds must be between 60 and 86400")
    return WorkflowDraft(name=name.strip()[:128], adapter=adapter, source_capture_id=capture_id.strip()[:128],
                         steps=tuple(item.strip()[:128] for item in steps), ttl_seconds=ttl,
                         evidence_refs=tuple(item.strip()[:128] for item in refs))


def make_workflow_envelope(*, replayability: Replayability, ttl_seconds: int = 3600,
                           evidence_refs: list[str] | tuple[str, ...] = ()) -> WorkflowEnvelope:
    if not isinstance(replayability, Replayability):
        raise ValueError("replayability must use the Workflow Lab enum")
    if isinstance(ttl_seconds, bool) or not 60 <= ttl_seconds <= 86400:
        raise ValueError("ttlSeconds must be between 60 and 86400")
    if not isinstance(evidence_refs, (list, tuple)) or len(evidence_refs) > 64 or any(not isinstance(ref, str) or not ref.strip() for ref in evidence_refs):
        raise ValueError("evidenceRefs must be bounded opaque strings")
    return WorkflowEnvelope(1, "READ_ONLY", replayability, ttl_seconds, tuple(ref.strip()[:128] for ref in evidence_refs))
