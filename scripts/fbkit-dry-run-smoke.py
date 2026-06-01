"""Safe FBKit runtime smoke test.

This script submits one selected safe dry-run task through the public API and
verifies the worker/extension path returns a dryRun result. It never approves
tasks and never asks the server for live dispatch.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


SAFE_VARIANTS = ("POST_TEXT", "LIKE_POST", "COMMENT_POST", "SEND_MESSAGE")
COMMENT_SMOKE_TEXT = "FBKit smoke test comment - dry run only"
MESSAGE_SMOKE_TEXT = "FBKit smoke test message - dry run only"


def request_json(base_url: str, path: str, method: str = "GET", body: dict | None = None, api_key: str | None = None) -> dict | list:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def find_logged_in_uid(status: dict) -> str | None:
    sessions = status.get("extension", {}).get("sessions", [])
    fresh_sessions = [
        session
        for session in sessions
        if session.get("logged_in") and session.get("fb_uid") and not is_stale_session(session)
    ]
    if not fresh_sessions:
        return None
    selected = min(fresh_sessions, key=lambda session: session.get("last_seen_age_s") or 0)
    return str(selected["fb_uid"])


def has_stale_logged_in_session(status: dict) -> bool:
    sessions = status.get("extension", {}).get("sessions", [])
    return any(session.get("logged_in") and session.get("fb_uid") and is_stale_session(session) for session in sessions)


def is_stale_session(session: dict) -> bool:
    return session.get("stale") is True or session.get("health") == "stale"


def find_account_id(accounts: list[dict], fb_uid: str) -> str | None:
    for account in accounts:
        if str(account.get("fb_uid")) == fb_uid:
            return account.get("id")
    return None


def build_task_payload(account_id: str, content: str, variant: str = "POST_TEXT") -> dict:
    if variant == "POST_TEXT":
        payload = {"content": content}
    elif variant == "LIKE_POST":
        payload = {"postUrl": content, "reaction": "LIKE"}
    elif variant == "COMMENT_POST":
        payload = {"postUrl": content, "comment": COMMENT_SMOKE_TEXT}
    elif variant == "SEND_MESSAGE":
        payload = {"recipientName": content, "content": MESSAGE_SMOKE_TEXT}
    else:
        raise ValueError(f"Unsupported smoke variant: {variant}")
    payload["dryRun"] = True
    return {
        "account_id": account_id,
        "task_type": variant,
        "payload": payload,
    }


def is_completed_dry_run(task: dict) -> bool:
    if task.get("status") != "COMPLETED":
        return False
    try:
        result = json.loads(task.get("result") or "{}")
    except json.JSONDecodeError:
        return False
    return bool(result.get("success") and result.get("dryRun") is True)


def ensure_account(base_url: str, fb_uid: str, api_key: str | None) -> str:
    accounts = request_json(base_url, "/api/accounts", api_key=api_key)
    account_id = find_account_id(accounts, fb_uid)
    if account_id:
        return account_id
    account = request_json(
        base_url,
        "/api/accounts",
        method="POST",
        api_key=api_key,
        body={
            "name": "Smoke Dry Run Account",
            "fb_uid": fb_uid,
            "notes": "Created by scripts/fbkit-dry-run-smoke.py",
        },
    )
    return account["id"]


def run_smoke(base_url: str, content: str, api_key: str | None, poll_seconds: int, variant: str = "POST_TEXT") -> int:
    status = request_json(base_url, "/api/status", api_key=api_key)
    fb_uid = find_logged_in_uid(status)
    if not fb_uid:
        if has_stale_logged_in_session(status):
            print("FAIL: only stale logged-in extension sessions found; refresh the extension heartbeat and retry", file=sys.stderr)
            return 2
        print("FAIL: no logged-in extension session with fb_uid", file=sys.stderr)
        return 2

    account_id = ensure_account(base_url, fb_uid, api_key)
    task = request_json(base_url, "/api/tasks", method="POST", api_key=api_key, body=build_task_payload(account_id, content, variant))
    task_id = task["id"]
    deadline = time.time() + poll_seconds

    while time.time() < deadline:
        task = request_json(base_url, f"/api/tasks/{task_id}", api_key=api_key)
        if task.get("status") in {"COMPLETED", "FAILED", "CANCELLED"}:
            break
        time.sleep(2)

    if not is_completed_dry_run(task):
        print(json.dumps(task, ensure_ascii=False, indent=2), file=sys.stderr)
        print("FAIL: smoke task did not complete with dryRun=true", file=sys.stderr)
        return 3

    print(json.dumps({"ok": True, "task_id": task_id, "fb_uid": fb_uid, "account_id": account_id}, ensure_ascii=False))
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a safe FBKit dry-run smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8100")
    parser.add_argument("--content", default="FBKit smoke test - dry run only")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--variant", choices=SAFE_VARIANTS, default="POST_TEXT")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        return run_smoke(args.base_url, args.content, args.api_key, args.poll_seconds, args.variant)
    except urllib.error.URLError as exc:
        print(f"FAIL: API request failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
