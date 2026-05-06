---
title: "Safe Windows startup helper"
description: "Plan to add a PowerShell helper that starts FBKit in safe dry-run mode and can print without launching."
status: completed
priority: P2
effort: 1h
branch: main
tags: [windows, startup, safety, tests]
created: 2026-05-06
---

# Safe Windows Startup Helper Plan

**Goal:** Add `scripts/start-fbkit-safe.ps1` so Windows users can start `agent.main` with safe FBKit env defaults, or verify command output via `-PrintOnly` without launching server/browser/Facebook.

## Phase 1 — Script contract + tests

- **Files:** create `scripts/start-fbkit-safe.ps1`; create `tests/unit/test_safe_start_script.py`.
- **Data flow:** PowerShell args/env → safe env map (`LIVE_ACTIONS_ENABLED=false`, `DRY_RUN_DEFAULT=true`, `APPROVAL_REQUIRED=true`, `API_AUTH_ENABLED=false`, `WS_AUTH_ENABLED=false`) → default python path `.venv\Scripts\python.exe` → command `-m agent.main` → either printed only or invoked.
- **Test matrix:** static-read script text for `-PrintOnly` mode; assert env defaults + python/module command; assert no `Start-Process`, browser launch, Facebook URL, HTTP calls, or server start in print mode.
- **Verification:** `& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_safe_start_script.py -q`.
- **Risks:** High if tests accidentally launch server; mitigate by only executing print mode and asserting command text, never live mode. Medium if PowerShell unavailable in CI; keep static tests as fallback and mark subprocess test skip when `powershell` missing.

## Phase 2 — Minimal README quick start update

- **Files:** modify `README.md` only near lines 9-20.
- **Change:** mention helper before manual env block, e.g. `.
scripts\start-fbkit-safe.ps1 -PrintOnly` to verify and `.
scripts\start-fbkit-safe.ps1` to start safe local mode.
- **Backwards compatibility:** keep existing manual env instructions unchanged; helper is additive.
- **Verification:** same unit test plus static README assertion optional in `tests/unit/test_safe_start_script.py`.

## Dependency graph / ownership

- Phase 1 before Phase 2, because README should document final flags.
- File ownership: script owner touches `scripts/start-fbkit-safe.ps1`; test owner touches `tests/unit/test_safe_start_script.py`; docs owner touches `README.md`. No parallel overlap.

## Rollback

- Delete `scripts/start-fbkit-safe.ps1` and `tests/unit/test_safe_start_script.py`; revert README helper paragraph. Existing manual startup remains working.

## Done criteria

- Print mode outputs safe env defaults and exact python module command.
- Tests prove no Facebook/browser/server launch in verification path.
- README has minimal helper mention.
- No live Facebook action. No push.

## Completion Note

- Implemented as `scripts/start-fbkit-safe.ps1`.
- Covered by `tests/unit/test_safe_start_script.py`.
- README documents safe helper and `-PrintOnly` mode.
- Verified with focused pytest command before marking complete: `3 passed` for startup helper tests; `80 passed` for focused FBKit safety/smoke regression.

## Unresolved questions

- None. `-PrintOnly` is the canonical safe preview flag.
