"""Tests for the safe FBKit dry-run smoke script."""

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "fbkit-dry-run-smoke.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("fbkit_dry_run_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_task_payload_supports_safe_variants_and_is_always_dry_run():
    script = _load_script()

    cases = {
        "POST_TEXT": {"content": "hello"},
        "LIKE_POST": {"postUrl": "hello", "reaction": "LIKE"},
        "COMMENT_POST": {"postUrl": "hello", "comment": script.COMMENT_SMOKE_TEXT},
        "SEND_MESSAGE": {"recipientName": "hello", "content": script.MESSAGE_SMOKE_TEXT},
    }

    for variant, expected_payload in cases.items():
        payload = script.build_task_payload("account-1", "hello", variant)

        assert payload == {
            "account_id": "account-1",
            "task_type": variant,
            "payload": {**expected_payload, "dryRun": True},
        }


def test_build_task_payload_rejects_unknown_variant():
    script = _load_script()

    try:
        script.build_task_payload("account-1", "hello", "APPROVE_TASK")
    except ValueError as exc:
        assert "Unsupported smoke variant" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_parse_args_defaults_to_post_text_variant():
    script = _load_script()

    args = script.parse_args([])

    assert args.variant == "POST_TEXT"


def test_parse_args_accepts_safe_variant():
    script = _load_script()

    args = script.parse_args(["--variant", "LIKE_POST"])

    assert args.variant == "LIKE_POST"


def test_run_smoke_submits_selected_variant(monkeypatch):
    script = _load_script()
    submitted_body = None

    def fake_request_json(base_url, path, method="GET", body=None, api_key=None):
        nonlocal submitted_body
        if path == "/api/status":
            return {"extension": {"sessions": [{"logged_in": True, "fb_uid": "fb-7"}]}}
        if path == "/api/accounts":
            return [{"id": "account-7", "fb_uid": "fb-7"}]
        if path == "/api/tasks" and method == "POST":
            submitted_body = body
            return {"id": "task-7"}
        if path == "/api/tasks/task-7":
            return {"id": "task-7", "status": "COMPLETED", "result": '{"success": true, "dryRun": true}'}
        raise AssertionError(f"Unexpected call: {path} {method}")

    monkeypatch.setattr(script, "request_json", fake_request_json)

    assert script.run_smoke("http://agent", "https://example.invalid/post", None, 1, "LIKE_POST") == 0
    assert submitted_body == script.build_task_payload("account-7", "https://example.invalid/post", "LIKE_POST")


def test_run_smoke_posts_only_safe_dry_run_task_for_each_variant(monkeypatch):
    script = _load_script()
    calls = []

    def fake_request_json(base_url, path, method="GET", body=None, api_key=None):
        calls.append((path, method, body))
        if path == "/api/status":
            return {"extension": {"sessions": [{"logged_in": True, "fb_uid": "fb-safe"}]}}
        if path == "/api/accounts":
            return [{"id": "account-safe", "fb_uid": "fb-safe"}]
        if path == "/api/tasks" and method == "POST":
            assert body["payload"]["dryRun"] is True
            assert "live" not in body["payload"]
            assert "liveRun" not in body["payload"]
            assert "_serverApproved" not in body["payload"]
            return {"id": f"task-{body['task_type']}"}
        if path.startswith("/api/tasks/task-"):
            return {"status": "COMPLETED", "result": '{"success": true, "dryRun": true}'}
        raise AssertionError(f"Unexpected call: {path} {method}")

    monkeypatch.setattr(script, "request_json", fake_request_json)

    for variant in script.SAFE_VARIANTS:
        calls.clear()
        assert script.run_smoke("http://agent", "hello", None, 1, variant) == 0
        task_posts = [call for call in calls if call[0] == "/api/tasks" and call[1] == "POST"]
        assert len(task_posts) == 1
        assert not any("approve" in path.lower() for path, _, _ in calls)
        assert not any(path.startswith("/api/tasks/") and path.endswith("/approve") for path, _, _ in calls)


def test_find_logged_in_session_returns_only_logged_in_uid():
    script = _load_script()

    uid = script.find_logged_in_uid({
        "extension": {
            "sessions": [
                {"fb_uid": None, "logged_in": False},
                {"fb_uid": "100004822807900", "logged_in": True},
            ]
        }
    })

    assert uid == "100004822807900"


def test_find_logged_in_session_rejects_missing_logged_in_uid():
    script = _load_script()

    assert script.find_logged_in_uid({"extension": {"sessions": []}}) is None


def test_completed_task_requires_dry_run_result():
    script = _load_script()

    assert script.is_completed_dry_run({
        "status": "COMPLETED",
        "result": '{"success": true, "dryRun": true}',
    }) is True
    assert script.is_completed_dry_run({
        "status": "COMPLETED",
        "result": '{"success": true, "dryRun": false}',
    }) is False


def test_run_smoke_returns_2_when_no_logged_in_extension(monkeypatch):
    script = _load_script()

    def fake_request_json(base_url, path, method="GET", body=None, api_key=None):
        assert api_key == "test-key"
        assert path == "/api/status"
        return {"extension": {"sessions": []}}

    monkeypatch.setattr(script, "request_json", fake_request_json)

    assert script.run_smoke("http://agent", "hello", "test-key", 1) == 2


def test_run_smoke_uses_existing_account_and_completes(monkeypatch, capsys):
    script = _load_script()
    calls = []
    task = {
        "id": "task-1",
        "status": "COMPLETED",
        "result": '{"success": true, "dryRun": true}',
    }

    def fake_request_json(base_url, path, method="GET", body=None, api_key=None):
        calls.append((path, method, body, api_key))
        if path == "/api/status":
            return {"extension": {"sessions": [{"logged_in": True, "fb_uid": "fb-1"}]}}
        if path == "/api/accounts" and method == "GET":
            return [{"id": "account-1", "fb_uid": "fb-1"}]
        if path == "/api/tasks" and method == "POST":
            assert body == script.build_task_payload("account-1", "hello")
            return {"id": "task-1"}
        if path == "/api/tasks/task-1":
            return task
        raise AssertionError(f"Unexpected call: {path} {method}")

    monkeypatch.setattr(script, "request_json", fake_request_json)

    assert script.run_smoke("http://agent", "hello", "test-key", 1) == 0
    assert ("/api/accounts", "POST", {"name": "Smoke Dry Run Account", "fb_uid": "fb-1", "notes": "Created by scripts/fbkit-dry-run-smoke.py"}, "test-key") not in calls
    assert all(call[3] == "test-key" for call in calls)
    assert '"ok": true' in capsys.readouterr().out


def test_run_smoke_creates_account_when_missing(monkeypatch):
    script = _load_script()
    created_account_body = None

    def fake_request_json(base_url, path, method="GET", body=None, api_key=None):
        nonlocal created_account_body
        if path == "/api/status":
            return {"extension": {"sessions": [{"logged_in": True, "fb_uid": "fb-2"}]}}
        if path == "/api/accounts" and method == "GET":
            return []
        if path == "/api/accounts" and method == "POST":
            created_account_body = body
            return {"id": "account-2"}
        if path == "/api/tasks" and method == "POST":
            assert body["account_id"] == "account-2"
            return {"id": "task-2"}
        if path == "/api/tasks/task-2":
            return {"id": "task-2", "status": "COMPLETED", "result": '{"success": true, "dryRun": true}'}
        raise AssertionError(f"Unexpected call: {path} {method}")

    monkeypatch.setattr(script, "request_json", fake_request_json)

    assert script.run_smoke("http://agent", "hello", None, 1) == 0
    assert created_account_body == {
        "name": "Smoke Dry Run Account",
        "fb_uid": "fb-2",
        "notes": "Created by scripts/fbkit-dry-run-smoke.py",
    }


def test_run_smoke_returns_3_for_terminal_failure(monkeypatch):
    script = _load_script()

    def fake_request_json(base_url, path, method="GET", body=None, api_key=None):
        if path == "/api/status":
            return {"extension": {"sessions": [{"logged_in": True, "fb_uid": "fb-3"}]}}
        if path == "/api/accounts":
            return [{"id": "account-3", "fb_uid": "fb-3"}]
        if path == "/api/tasks" and method == "POST":
            return {"id": "task-3"}
        if path == "/api/tasks/task-3":
            return {"id": "task-3", "status": "FAILED", "result": "{}"}
        raise AssertionError(f"Unexpected call: {path} {method}")

    monkeypatch.setattr(script, "request_json", fake_request_json)

    assert script.run_smoke("http://agent", "hello", None, 1) == 3


def test_run_smoke_returns_3_for_terminal_cancelled(monkeypatch):
    script = _load_script()

    def fake_request_json(base_url, path, method="GET", body=None, api_key=None):
        if path == "/api/status":
            return {"extension": {"sessions": [{"logged_in": True, "fb_uid": "fb-5"}]}}
        if path == "/api/accounts":
            return [{"id": "account-5", "fb_uid": "fb-5"}]
        if path == "/api/tasks" and method == "POST":
            return {"id": "task-5"}
        if path == "/api/tasks/task-5":
            return {"id": "task-5", "status": "CANCELLED", "result": "{}"}
        raise AssertionError(f"Unexpected call: {path} {method}")

    monkeypatch.setattr(script, "request_json", fake_request_json)

    assert script.run_smoke("http://agent", "hello", None, 1) == 3


def test_run_smoke_returns_3_for_completed_non_dry_run(monkeypatch):
    script = _load_script()

    def fake_request_json(base_url, path, method="GET", body=None, api_key=None):
        if path == "/api/status":
            return {"extension": {"sessions": [{"logged_in": True, "fb_uid": "fb-6"}]}}
        if path == "/api/accounts":
            return [{"id": "account-6", "fb_uid": "fb-6"}]
        if path == "/api/tasks" and method == "POST":
            return {"id": "task-6"}
        if path == "/api/tasks/task-6":
            return {"id": "task-6", "status": "COMPLETED", "result": '{"success": true, "dryRun": false}'}
        raise AssertionError(f"Unexpected call: {path} {method}")

    monkeypatch.setattr(script, "request_json", fake_request_json)

    assert script.run_smoke("http://agent", "hello", None, 1) == 3


def test_run_smoke_returns_3_on_timeout(monkeypatch):
    script = _load_script()
    now = {"value": 100.0}

    def fake_time():
        return now["value"]

    def fake_sleep(seconds):
        now["value"] += seconds

    def fake_request_json(base_url, path, method="GET", body=None, api_key=None):
        if path == "/api/status":
            return {"extension": {"sessions": [{"logged_in": True, "fb_uid": "fb-4"}]}}
        if path == "/api/accounts":
            return [{"id": "account-4", "fb_uid": "fb-4"}]
        if path == "/api/tasks" and method == "POST":
            return {"id": "task-4"}
        if path == "/api/tasks/task-4":
            return {"id": "task-4", "status": "PROCESSING", "result": "{}"}
        raise AssertionError(f"Unexpected call: {path} {method}")

    monkeypatch.setattr(script, "request_json", fake_request_json)
    monkeypatch.setattr(script.time, "time", fake_time)
    monkeypatch.setattr(script.time, "sleep", fake_sleep)

    assert script.run_smoke("http://agent", "hello", None, 3) == 3
