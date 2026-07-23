import pytest

from agent.services.workflow_contract import (
    CaptureEvent,
    WorkflowDraft,
    Replayability,
    make_workflow_envelope,
    normalize_capture_event,
    normalize_workflow_draft,
)
from agent.services.workflow_redaction import redact_capture_event
from agent.services.workflow_capability import WorkflowReadOnlyCapabilityGate


def test_capture_event_keeps_metadata_only_and_aliases_values():
    event = normalize_capture_event(
        {
            "method": "POST",
            "url": "https://www.facebook.com/api?token=secret",
            "status": 200,
            "resourceType": "XHR",
            "timingMs": 12.5,
        },
        capture_id="cap-1",
    )
    assert isinstance(event, CaptureEvent)
    assert event.method == "POST"
    assert event.host == "www.facebook.com"
    assert event.path == "/api"
    assert event.query_shape == ["token"]
    assert event.value_aliases == {"token": "v1"}
    assert not hasattr(event, "requestHeaders")


def test_capture_event_rejects_raw_body_and_unbounded_input():
    with pytest.raises(ValueError, match="response body"):
        normalize_capture_event({"method": "GET", "url": "https://example.com", "responseBody": "x"}, "cap")
    with pytest.raises(ValueError, match="unsupported capture fields"):
        normalize_capture_event({"method": "GET", "url": "https://www.facebook.com", "requestHeaders": {}}, "cap")
    with pytest.raises(ValueError, match="approved host"):
        normalize_capture_event({"method": "GET", "url": "https://example.com"}, "cap")
    with pytest.raises(ValueError, match="resourceType"):
        normalize_capture_event({"method": "GET", "url": "https://www.facebook.com", "resourceType": {"secret": "x"}}, "cap")
    with pytest.raises(ValueError, match="credentials or fragment"):
        normalize_capture_event({"method": "GET", "url": "https://user:pass@www.facebook.com/a#frag"}, "cap")


def test_workflow_draft_is_positive_schema_and_read_only():
    draft = normalize_workflow_draft(
        {"name": "post metrics", "adapter": "get_post_metrics", "sourceCaptureId": "cap-1"}
    )
    assert isinstance(draft, WorkflowDraft)
    assert draft.adapter == "get_post_metrics"
    assert draft.read_only is True
    with pytest.raises(ValueError, match="unsupported"):
        normalize_workflow_draft({"name": "x", "adapter": "get_post_metrics", "execute": True})


def test_redaction_is_recursive_and_secret_free():
    value = redact_capture_event(
        {"method": "GET", "url": "https://www.facebook.com/a?token=secret", "status": 200},
        capture_id="cap-1",
    )
    assert value["captureId"] == "cap-1"
    assert value["queryShape"][0].startswith("key_sha256:")
    assert "secret" not in repr(value)
    assert "url" not in value


def test_capability_gate_has_sealed_read_only_allowlist():
    gate = WorkflowReadOnlyCapabilityGate()
    assert gate.allows("get_post_metrics", "inspect")
    assert gate.allows("read_page_clone", "inspect")
    assert not gate.allows("get_post_metrics", "execute")
    assert not gate.allows("unknown", "inspect")
    with pytest.raises(PermissionError):
        gate.require("get_post_metrics", "execute")


def test_versioned_read_only_envelope_is_bounded():
    envelope = make_workflow_envelope(
        replayability=Replayability.OBSERVED_REQUEST_CANDIDATE,
        evidence_refs=["cap-1"],
    )
    assert envelope.schema_version == 1
    assert envelope.risk == "READ_ONLY"
    assert envelope.evidence_refs == ("cap-1",)
