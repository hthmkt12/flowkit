---
title: "Extend FBKit dry-run smoke variants"
description: "Plan to add selectable safe dry-run smoke task variants without approval or live dispatch paths."
status: completed
priority: P2
effort: 2h
branch: unknown
tags: [fbkit, smoke-test, dry-run, safety, tdd]
created: 2026-05-06
---

# Extend FBKit Dry-Run Smoke Variants Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or executing-plans. Implement task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add selectable safe variants `POST_TEXT`, `LIKE_POST`, `COMMENT_POST`, `SEND_MESSAGE` to `scripts/fbkit-dry-run-smoke.py`, with every submitted payload containing `dryRun: True`.

**Architecture:** Keep one script, one test file. Add a small variant registry/payload builder, route CLI `--variant` into `run_smoke`, and preserve default `POST_TEXT`. No approval endpoints. No live flags. No server changes.

**Tech Stack:** Python stdlib (`argparse`, `json`, `urllib`), pytest, Windows repo venv: `& ".\.venv\Scripts\python.exe"`.

---

## Scope Lock

Allowed files only:
- Modify: `scripts/fbkit-dry-run-smoke.py`
- Modify: `tests/unit/test_fbkit_dry_run_smoke_script.py`

Out of scope:
- No API/server/extension changes.
- No approval endpoint calls.
- No `live`, `liveRun`, `dryRun=False`, `LIVE_ACTIONS_ENABLED`, or other live-dispatch flags.
- No broad refactor beyond small helpers needed for variants.

## Explicit Data Flow

1. CLI input enters `parse_args`: `--base-url`, `--content`, `--api-key`, `--poll-seconds`, new `--variant`.
2. `main` passes parsed values into `run_smoke`.
3. `run_smoke` reads `/api/status`, extracts logged-in `fb_uid`, resolves/creates local account via `/api/accounts`.
4. `build_task_payload(account_id, content, variant)` maps variant to task payload, always injecting `payload["dryRun"] = True`.
5. `run_smoke` posts exactly one `/api/tasks` request. No other mutation/control endpoints.
6. Poll loop reads `/api/tasks/{task_id}` until terminal/timeout.
7. `is_completed_dry_run` parses task result and returns success only when `status == COMPLETED`, `success == true`, and result `dryRun is True`.
8. Output exits as JSON success line or stderr failure with non-zero code.

## Dependency Graph

```text
Task 1 tests for variant contract
  -> Task 2 minimal script variant registry + CLI
    -> Task 3 update existing run_smoke tests for signature/default behavior
      -> Task 4 safety regression tests: no approval endpoints/live fields
        -> Task 5 verification commands
```

Blockers:
- Task 2 cannot start until Task 1 RED is observed.
- Task 4 cannot finalize until all variant payload shapes are explicit and stable.

## Variant Payload Contract

Use smallest plausible payloads; all must include `dryRun: True`:

```python
POST_TEXT = {
    "account_id": account_id,
    "task_type": "POST_TEXT",
    "payload": {"content": content, "dryRun": True},
}

LIKE_POST = {
    "account_id": account_id,
    "task_type": "LIKE_POST",
    "payload": {"postUrl": content, "dryRun": True},
}

COMMENT_POST = {
    "account_id": account_id,
    "task_type": "COMMENT_POST",
    "payload": {"postUrl": content, "comment": "FBKit smoke test comment - dry run only", "dryRun": True},
}

SEND_MESSAGE = {
    "account_id": account_id,
    "task_type": "SEND_MESSAGE",
    "payload": {"recipientName": content, "content": "FBKit smoke test message - dry run only", "dryRun": True},
}
```

Rationale: keep one existing `--content` input to avoid new CLI surface. For non-post variants, `content` is the safe target placeholder/value. `SEND_MESSAGE` follows the existing worker/client payload contract (`recipientName` + `content`). Dry-run extension path should not execute live action.

## Task 1: Write failing variant payload tests

**Files:**
- Modify: `tests/unit/test_fbkit_dry_run_smoke_script.py`

- [x] Add/replace payload test with parametrized cases:

```python
def test_build_task_payload_supports_safe_variants_and_is_always_dry_run():
    script = _load_script()

    cases = {
        "POST_TEXT": {"content": "hello"},
        "LIKE_POST": {"postUrl": "hello"},
        "COMMENT_POST": {"postUrl": "hello", "comment": "FBKit smoke test comment - dry run only"},
        "SEND_MESSAGE": {"recipientName": "hello", "content": "FBKit smoke test message - dry run only"},
    }

    for variant, expected_payload_subset in cases.items():
        payload = script.build_task_payload("account-1", "hello", variant)
        assert payload["account_id"] == "account-1"
        assert payload["task_type"] == variant
        assert payload["payload"] == {**expected_payload_subset, "dryRun": True}
```

- [x] Add invalid variant test:

```python
def test_build_task_payload_rejects_unknown_variant():
    script = _load_script()

    try:
        script.build_task_payload("account-1", "hello", "APPROVE_TASK")
    except ValueError as exc:
        assert "Unsupported smoke variant" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
```

- [x] Run RED:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_fbkit_dry_run_smoke_script.py::test_build_task_payload_supports_safe_variants_and_is_always_dry_run tests\unit\test_fbkit_dry_run_smoke_script.py::test_build_task_payload_rejects_unknown_variant -q
```

Expected: fail because current `build_task_payload` accepts only `(account_id, content)` and no variant.

## Task 2: Implement minimal variant registry and CLI option

**Files:**
- Modify: `scripts/fbkit-dry-run-smoke.py`

- [x] Add constants near imports:

```python
SAFE_VARIANTS = ("POST_TEXT", "LIKE_POST", "COMMENT_POST", "SEND_MESSAGE")
COMMENT_SMOKE_TEXT = "FBKit smoke test comment - dry run only"
MESSAGE_SMOKE_TEXT = "FBKit smoke test message - dry run only"
```

- [x] Replace `build_task_payload(account_id, content)` with `build_task_payload(account_id, content, variant="POST_TEXT")` using explicit branches only:

```python
def build_task_payload(account_id: str, content: str, variant: str = "POST_TEXT") -> dict:
    if variant == "POST_TEXT":
        payload = {"content": content}
    elif variant == "LIKE_POST":
        payload = {"postUrl": content}
    elif variant == "COMMENT_POST":
        payload = {"postUrl": content, "comment": COMMENT_SMOKE_TEXT}
    elif variant == "SEND_MESSAGE":
        payload = {"recipientName": content, "content": MESSAGE_SMOKE_TEXT}
    else:
        raise ValueError(f"Unsupported smoke variant: {variant}")
    payload["dryRun"] = True
    return {"account_id": account_id, "task_type": variant, "payload": payload}
```

- [x] Change `run_smoke` signature and call site:

```python
def run_smoke(base_url: str, content: str, api_key: str | None, poll_seconds: int, variant: str = "POST_TEXT") -> int:
    ...
    task = request_json(base_url, "/api/tasks", method="POST", api_key=api_key, body=build_task_payload(account_id, content, variant))
```

- [x] Add CLI argument:

```python
parser.add_argument("--variant", choices=SAFE_VARIANTS, default="POST_TEXT")
```

- [x] Pass variant from `main`:

```python
return run_smoke(args.base_url, args.content, args.api_key, args.poll_seconds, args.variant)
```

- [x] Run GREEN for Task 1 tests.

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_fbkit_dry_run_smoke_script.py::test_build_task_payload_supports_safe_variants_and_is_always_dry_run tests\unit\test_fbkit_dry_run_smoke_script.py::test_build_task_payload_rejects_unknown_variant -q
```

Expected: pass.

## Task 3: Preserve backwards compatibility

**Files:**
- Modify: `tests/unit/test_fbkit_dry_run_smoke_script.py`
- Modify: `scripts/fbkit-dry-run-smoke.py`

- [x] Keep default behavior: no `--variant` means `POST_TEXT`, no caller break because `run_smoke(..., poll_seconds)` still works via default parameter.
- [x] Update only assertions that call `build_task_payload` in existing tests to pass default-compatible call or variant-aware call.
- [x] Add CLI parse test:

```python
def test_parse_args_defaults_to_post_text_variant():
    script = _load_script()

    args = script.parse_args([])

    assert args.variant == "POST_TEXT"
```

- [x] Add CLI choices test:

```python
def test_parse_args_accepts_each_safe_variant():
    script = _load_script()

    for variant in script.SAFE_VARIANTS:
        args = script.parse_args(["--variant", variant])
        assert args.variant == variant
```

- [x] Run focused tests:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_fbkit_dry_run_smoke_script.py -q
```

Expected: pass.

## Task 4: Safety regression tests: no approval endpoints, no live fields

**Files:**
- Modify: `tests/unit/test_fbkit_dry_run_smoke_script.py`

- [x] Add endpoint safety test over all variants:

```python
def test_run_smoke_posts_only_task_endpoint_for_each_variant(monkeypatch):
    script = _load_script()
    called_paths = []

    def fake_request_json(base_url, path, method="GET", body=None, api_key=None):
        called_paths.append((path, method, body))
        if path == "/api/status":
            return {"extension": {"sessions": [{"logged_in": True, "fb_uid": "fb-safe"}]}}
        if path == "/api/accounts" and method == "GET":
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
        called_paths.clear()
        assert script.run_smoke("http://agent", "hello", None, 1, variant) == 0
        assert not any("approval" in path.lower() for path, _, _ in called_paths)
        assert not any(path.startswith("/api/tasks/") and path.endswith("/approve") for path, _, _ in called_paths)
```

- [x] Run safety focused test:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_fbkit_dry_run_smoke_script.py::test_run_smoke_posts_only_task_endpoint_for_each_variant -q
```

Expected: pass.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---:|---:|---|
| Wrong payload key for extension handler | Medium | Medium | Use explicit test matrix; keep smoke dry-run only; runtime validation catches terminal failure. |
| Accidentally enables live path | Low | High | Hard-code `dryRun=True`; CLI choices only safe variants; tests assert no live/approval fields/endpoints. |
| Break existing `POST_TEXT` smoke usage | Low | Medium | Default `variant="POST_TEXT"`; parse default test; existing run tests retained. |
| Over-engineered registry/refactor | Medium | Low | Use simple constants and explicit branches; no new files. |

High item mitigation: live-path risk is tested at payload and endpoint levels; no env/live flags added.

## Test Matrix

Unit tests:
- `build_task_payload` for all four variants.
- Unknown variant rejects before request post.
- Every variant payload has `dryRun is True`.
- No variant payload has `live`, `liveRun`, `_serverApproved`.
- CLI default variant is `POST_TEXT`.
- CLI accepts exactly `SAFE_VARIANTS` via argparse choices.
- Existing account, create account, no extension, failed/cancelled/non-dry-run/timeout flows still pass.

Integration-ish unit via monkeypatch:
- `run_smoke` submits one `/api/tasks` per variant.
- No approval endpoint path called.

Manual dry-run runtime, optional after unit tests and only with safe env:
```powershell
$env:LIVE_ACTIONS_ENABLED="false"
$env:DRY_RUN_DEFAULT="true"
$env:APPROVAL_REQUIRED="true"
$env:API_AUTH_ENABLED="false"
$env:WS_AUTH_ENABLED="false"
& ".\.venv\Scripts\python.exe" -m agent.main
```

Then in another PowerShell:
```powershell
& ".\.venv\Scripts\python.exe" scripts\fbkit-dry-run-smoke.py --variant POST_TEXT
& ".\.venv\Scripts\python.exe" scripts\fbkit-dry-run-smoke.py --variant LIKE_POST --content "https://www.facebook.com/example/posts/example"
& ".\.venv\Scripts\python.exe" scripts\fbkit-dry-run-smoke.py --variant COMMENT_POST --content "https://www.facebook.com/example/posts/example"
& ".\.venv\Scripts\python.exe" scripts\fbkit-dry-run-smoke.py --variant SEND_MESSAGE --content "100000000000000"
```

## Required Verification Commands

Run from `D:\vm extention  facebook\flowkit`:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_fbkit_dry_run_smoke_script.py -q
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_fbkit_dry_run_smoke_script.py tests\unit\test_safety_gate.py -q
```

Expected: all pass. If second command too broad for this change budget, minimum accepted command is first test file only because plan scope is script + its unit tests.

## Rollback Plan

Per phase rollback:
- Tests only changed and fail unexpectedly: revert test edits in `tests/unit/test_fbkit_dry_run_smoke_script.py`.
- Script variant implementation breaks default smoke: revert `scripts/fbkit-dry-run-smoke.py` to prior two-argument `build_task_payload` and no `--variant`; keep/restore original POST_TEXT tests.
- Runtime smoke reveals extension payload mismatch: keep unit-safe dry-run guards, disable non-working variant by removing it from `SAFE_VARIANTS` and tests until payload contract is confirmed. Default `POST_TEXT` remains available.

No DB migrations, data migration, or user data rollback needed.

## Backwards Compatibility Strategy

- Existing command still works: `& ".\.venv\Scripts\python.exe" scripts\fbkit-dry-run-smoke.py`.
- Existing behavior remains `POST_TEXT` with `payload.content` and `dryRun=True`.
- Existing callers of `run_smoke(base_url, content, api_key, poll_seconds)` continue because new `variant` has default.
- No API schema changes. No stored data changes.

## File Ownership

Single implementation lane only. No parallel edits recommended.

| File | Owner | Notes |
|---|---|---|
| `scripts/fbkit-dry-run-smoke.py` | implementer | Minimal helper + CLI changes only. |
| `tests/unit/test_fbkit_dry_run_smoke_script.py` | implementer/tester | TDD additions and existing assertions. |

## Success Criteria

- `--variant` accepts only `POST_TEXT`, `LIKE_POST`, `COMMENT_POST`, `SEND_MESSAGE`.
- Default variant remains `POST_TEXT`.
- For every variant, body posted to `/api/tasks` includes `payload.dryRun is True`.
- No approval endpoint is called in tests.
- No payload includes live flags or `_serverApproved`.
- Required verification command passes with Windows venv Python.
- Implementation files stay limited to smoke script, smoke tests, README usage, and this plan status update.

## Unresolved Questions

None.
