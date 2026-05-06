# FBKit Agent Instructions

This repository runs FBKit: a local-first Facebook automation assistant. The active stack is a Python FastAPI agent, SQLite task queue, and Chrome extension WebSocket bridge.

Base URL: `http://127.0.0.1:8100`

## Safety Rules

1. FBKit is dry-run first. Keep `LIVE_ACTIONS_ENABLED=false`, `DRY_RUN_DEFAULT=true`, and `APPROVAL_REQUIRED=true` unless the user explicitly asks for a controlled live test.
2. Do not trigger, approve, or enable real Facebook/social actions without explicit user approval, a safe target, and verified Safety Gate behavior.
3. Treat posting, messaging, liking, commenting, sharing, friend actions, group actions, page follow/unfollow, and video reup as mutating actions.
4. Direct task creation must still pass Safety Gate enforcement. Do not bypass it except in explicit internal tests with `enforce_safety=False`.
5. Never use the user's main Facebook account as the first live validation target.

## Development Rules

1. Read `README.md` before planning or implementing changes.
2. Keep changes minimal and direct. Follow YAGNI, KISS, and DRY.
3. Use TDD for behavior changes: write a failing test, verify RED, implement the smallest fix, verify GREEN.
4. Do not create or commit generated/local artifacts such as `repomix-output.xml`, temporary smoke files, or logs.
5. Do not commit, push, approve live tasks, start live mutation flows, or change production-like env flags unless the user explicitly asks.
6. Preserve Windows paths with spaces when running commands in this repo.

## Verification

Use the repo virtualenv on Windows:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest ...
```

For broad regression after Safety Gate changes:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_safety_gate.py -q
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_crud.py -q
& ".\.venv\Scripts\python.exe" -m pytest
```

Use `curl.exe` in PowerShell when calling local HTTP endpoints.

## Safe Runtime Checks

Only run runtime smoke checks in dry-run mode:

```powershell
$env:LIVE_ACTIONS_ENABLED="false"
$env:DRY_RUN_DEFAULT="true"
$env:APPROVAL_REQUIRED="true"
$env:API_AUTH_ENABLED="false"
$env:WS_AUTH_ENABLED="false"
& ".\.venv\Scripts\python.exe" -m agent.main
```

Then, in another shell:

```powershell
& ".\.venv\Scripts\python.exe" scripts\fbkit-dry-run-smoke.py
```

The smoke script must complete with `dryRun=true` and must not approve tasks or request live dispatch.
