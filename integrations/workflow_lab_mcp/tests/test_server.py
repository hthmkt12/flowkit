import pytest

from agent.services.workflow_store import WorkflowStore
from integrations.workflow_lab_mcp.server import WorkflowLabMCP


def test_mcp_is_off_by_default_and_read_only(tmp_path, monkeypatch):
    monkeypatch.delenv("WORKFLOW_LAB_MCP_ENABLED", raising=False)
    mcp = WorkflowLabMCP(WorkflowStore(tmp_path / "workflow.sqlite3"))
    with pytest.raises(PermissionError):
        mcp.call("list_captures", {"captureId": "cap"}, "profile")


def test_mcp_scopes_and_rejects_unsafe_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKFLOW_LAB_MCP_ENABLED", "1")
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    store.create_capture("cap", "profile")
    mcp = WorkflowLabMCP(store)
    assert len(mcp.call("list_captures", {}, "profile")["captures"]) == 1
    assert mcp.call("check_replayability", {"captureId": "cap"}, "profile")["readOnly"] is True
    with pytest.raises(LookupError):
        mcp.call("inspect_workflow", {"captureId": "cap"}, "other")
    with pytest.raises(ValueError):
        mcp.call("execute", {"captureId": "cap"}, "profile")
    with pytest.raises(ValueError):
        mcp.call("inspect_workflow", {"captureId": "cap", "cookie": "secret"}, "profile")
    with pytest.raises(ValueError):
        mcp.call("inspect_workflow", {"captureId": "cap", "unexpected": True}, "profile")
    with pytest.raises(ValueError):
        mcp.call("inspect_workflow", {"captureId": "cap"}, "")
