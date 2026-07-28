from agent.services.workflow_store import WorkflowStore


def test_store_is_local_ttl_bounded_and_reviewable(tmp_path):
    store = WorkflowStore(tmp_path / "workflow_lab.sqlite3", ttl_seconds=60)
    store.create_capture("cap-1", "profile-1")
    store.append_event("cap-1", {"schemaVersion": 1, "method": "GET", "host": "example.com", "path": "/"})
    assert store.inspect_capture("cap-1")["events"][0]["host"] == "example.com"
    assert store.stop_capture("cap-1")["status"] == "stopped"
    assert store.delete_capture("cap-1") is True
    assert store.inspect_capture("cap-1") is None


def test_store_sequence_is_idempotent_and_restart_recoverable(tmp_path):
    path = tmp_path / "workflow_lab.sqlite3"
    store = WorkflowStore(path)
    store.create_capture("cap-2", "profile-2")
    event = {"schemaVersion": 1, "method": "GET", "host": "www.facebook.com", "path": "/"}
    store.append_event("cap-2", event, sequence=4)
    store.append_event("cap-2", event, sequence=4)
    restarted = WorkflowStore(path)
    assert len(restarted.inspect_capture("cap-2")["events"]) == 1


def test_store_gc_removes_expired_capture_only(tmp_path):
    path = tmp_path / "workflow_lab.sqlite3"
    store = WorkflowStore(path, ttl_seconds=60)
    store.create_capture("cap-old", "profile")
    with store._connect() as db:
        db.execute("UPDATE workflow_captures SET updated_at = 0 WHERE id = 'cap-old'")
    assert store.gc() == 1
    assert store.inspect_capture("cap-old") is None
