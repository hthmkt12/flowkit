import json

from agent.services.workflow_adapters import WorkflowAdapterRegistry
from agent.services.workflow_analyzer import analyze_replayability
from agent.services.workflow_redaction import redact_capture_event
from agent.services.workflow_store import WorkflowStore


def test_synthetic_capture_store_analyzer_adapter_chain_is_secret_free(tmp_path, monkeypatch):
    store = WorkflowStore(tmp_path / "workflow_lab.sqlite3")
    store.create_capture("cap-e2e", "profile-e2e", fb_uid="uid-e2e", tab_id="tab-e2e")
    event = redact_capture_event(
        {"method": "GET", "url": "https://www.facebook.com/api/post?access_token=fixture-secret", "status": 200, "resourceType": "XHR"},
        "cap-e2e",
    )
    store.append_event("cap-e2e", event)
    capture = store.inspect_capture("cap-e2e")
    analysis = analyze_replayability(capture["events"])
    adapter = WorkflowAdapterRegistry().inspect("get_post_metrics", capture["events"][0])
    assert analysis["executeAllowed"] is False
    assert adapter["readOnly"] is True
    serialized = json.dumps({"capture": capture, "analysis": analysis, "adapter": adapter})
    assert "fixture-secret" not in serialized
    assert "access_token" not in serialized
    assert "responseBody" not in serialized
    assert "tab-e2e" in serialized
