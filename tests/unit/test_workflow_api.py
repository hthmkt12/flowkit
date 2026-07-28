import pytest
from fastapi import HTTPException

from agent.api import workflows


@pytest.mark.asyncio
async def test_workflow_api_is_inspect_only(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKFLOW_LAB_API_KEY", "test-key")
    workflows._store = workflows.WorkflowStore(tmp_path / "workflow_lab.sqlite3")
    workflows._store.create_capture("cap-api", "profile-1")
    inspected = await workflows.inspect_workflow_capture("cap-api", "profile-1", "test-key")
    assert inspected["status"] == "running"
    analysis = await workflows.analyze_workflow_capture("cap-api", "profile-1", "test-key")
    assert analysis["executeAllowed"] is False
    with pytest.raises(HTTPException) as exc:
        await workflows.review_workflow_capture("cap-api", workflows.WorkflowReview(decision="accept"), "profile-1", "test-key")
    assert exc.value.status_code == 409
    stopped = await workflows.stop_workflow_capture("cap-api", "profile-1", "test-key")
    assert stopped["status"] == "stopped"
    assert (await workflows.delete_workflow_capture("cap-api", "profile-1", "test-key"))["logicalRetention"] is True


@pytest.mark.asyncio
async def test_workflow_api_has_no_start_or_ingest_route():
    paths = {route.path for route in workflows.router.routes}
    assert not any(route.endswith("/start") or route.endswith("/events") for route in paths)


@pytest.mark.asyncio
async def test_workflow_api_wrong_profile_cannot_stop_or_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKFLOW_LAB_API_KEY", "test-key")
    workflows._store = workflows.WorkflowStore(tmp_path / "workflow_lab.sqlite3")
    workflows._store.create_capture("cap-scope", "owner")
    with pytest.raises(HTTPException) as stopped:
        await workflows.stop_workflow_capture("cap-scope", "attacker", "test-key")
    assert stopped.value.status_code == 404
    assert workflows._store.inspect_capture("cap-scope")["status"] == "running"
    with pytest.raises(HTTPException) as deleted:
        await workflows.delete_workflow_capture("cap-scope", "attacker", "test-key")
    assert deleted.value.status_code == 404
    assert workflows._store.inspect_capture("cap-scope") is not None
