"""Tests for the safe FBKit dry-run smoke script."""

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "fbkit-dry-run-smoke.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("fbkit_dry_run_smoke", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_task_payload_is_always_dry_run_post_text():
    script = _load_script()

    payload = script.build_task_payload("account-1", "hello")

    assert payload == {
        "account_id": "account-1",
        "task_type": "POST_TEXT",
        "payload": {
            "content": "hello",
            "dryRun": True,
        },
    }


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
