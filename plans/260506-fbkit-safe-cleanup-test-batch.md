---
title: "FBKit safe cleanup/test batch"
description: "Remove stale Google Flow setup constants and TDD dry-run smoke orchestration without live Facebook actions."
status: completed
priority: P2
effort: 2h
branch: main
tags: [fbkit, safety, tests, cleanup]
created: 2026-05-06
---

# FBKit Safe Cleanup/Test Batch Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use TDD. Do not perform live Facebook actions. Do not push.

**Goal:** Clean stale setup constants and cover `run_smoke` orchestration with isolated tests.

**Architecture:** Keep production behavior unchanged unless tests expose a real seam/bug. `run_smoke` tests monkeypatch module globals (`request_json`, `time.time`, `time.sleep`) so no network, no agent, no extension, no Facebook.

**Tech Stack:** Python stdlib, pytest, Windows venv command: `& ".\.venv\Scripts\python.exe" -m pytest ...`

---

## File ownership

- Modify: `tests/unit/test_setup_generation.py`
- Modify: `tests/unit/test_fbkit_dry_run_smoke_script.py`
- Modify: `setup.py`
- Modify only if RED test requires: `scripts/fbkit-dry-run-smoke.py`
- Do not edit: DB files, extension, agent runtime, generated configs.

## Data flows

- Setup cleanup: `setup.py` source constants -> tests read/import module -> generated `AGENTS.md` body remains FBKit-only -> no generated output regression.
- Smoke success test: fake `/api/status` -> `find_logged_in_uid` -> fake account lookup/create -> `build_task_payload(dryRun=True)` -> fake task create -> fake poll complete -> exit code `0`.
- Smoke failure test: fake status/task states -> `run_smoke` returns `2`/`3` -> no live approval, no live dispatch, no real HTTP.

## Dependency graph

1. Baseline tests before edits.
2. RED setup cleanup test before removing constants.
3. RED `run_smoke` orchestration tests before any smoke script change.
4. Minimal implementation/cleanup.
5. Targeted tests, then commit prep.

## Tasks

- [x] **Baseline verify current state**
  - Run:
    ```powershell
    & ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_setup_generation.py tests\unit\test_fbkit_dry_run_smoke_script.py -q
    ```
  - Expected: existing tests pass before changes. If not, stop and diagnose; do not mask failures.

- [x] **TDD: add RED setup cleanup test**
  - In `tests/unit/test_setup_generation.py`, add a source-level test asserting stale legacy inline constants/content are absent from `setup.py`: `_CRITICAL_RULES`, `_PIPELINE_OVERVIEW`, `_BATCH_API`, `/api/requests/batch`, `Image Material required`.
  - Run:
    ```powershell
    & ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_setup_generation.py -q
    ```
  - Expected: FAIL while stale constants still exist.

- [x] **GREEN: remove stale Google Flow constants only**
  - In `setup.py`, remove unused `_CRITICAL_RULES`, `_PIPELINE_OVERVIEW`, `_BATCH_API` blocks.
  - Do not change generator behavior, CLI args, state file handling, or FBKit safety rules.
  - Run setup tests again; expected PASS.

- [x] **TDD: add RED `run_smoke` orchestration tests**
  - In `tests/unit/test_fbkit_dry_run_smoke_script.py`, add tests using monkeypatch only:
    - success uses existing account, creates exactly one `POST_TEXT` task with `dryRun=True`, polls until completed, returns `0`.
    - success creates account when missing, then uses created account id.
    - no logged-in `fb_uid` returns `2` and does not call accounts/tasks endpoints.
    - terminal failed/cancelled or completed without `dryRun=True` returns `3`.
  - Patch `script.request_json` with an in-memory router; patch `script.time.sleep` no-op; patch `script.time.time` deterministic if needed.
  - Run:
    ```powershell
    & ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_fbkit_dry_run_smoke_script.py -q
    ```
  - Expected: at least one new test fails first, proving coverage gap or needed seam.

- [x] **GREEN: minimal smoke script improvements only if required**
  - If tests fail due to behavior bug, edit `scripts/fbkit-dry-run-smoke.py` minimally.
  - Allowed examples: guard missing task id, avoid sleeping after terminal status, clearer return on malformed account/task response.
  - Forbidden: real network in tests, approval endpoint calls, live dispatch flags, new dependencies, broad refactor.
  - Re-run smoke tests; expected PASS.

- [x] **Regression verification**
  - Run targeted batch:
    ```powershell
    & ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_setup_generation.py tests\unit\test_fbkit_dry_run_smoke_script.py -q
    ```
  - Optional if touched smoke behavior:
    ```powershell
    & ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_safety_gate.py -q
    ```
  - Expected: all pass. No server start. No Facebook/browser actions.

- [x] **Prepare commit, no push**
  - Inspect:
    ```powershell
    git diff -- setup.py tests\unit\test_setup_generation.py tests\unit\test_fbkit_dry_run_smoke_script.py scripts\fbkit-dry-run-smoke.py
    git status --short
    ```
- Commit only relevant files if tests pass:
    ```powershell
    git add setup.py tests\unit\test_setup_generation.py tests\unit\test_fbkit_dry_run_smoke_script.py scripts\fbkit-dry-run-smoke.py
    git commit -m "test: cover fbkit smoke orchestration"
    ```
  - Do not push.
  - Status: ready for local commit after final verification; push remains out of scope.

## Risk matrix

| Phase | Risk | LxI | Mitigation |
|---|---|---:|---|
| Setup cleanup | Removing used content | MxM | Remove only constants proven unused by grep/import tests; run setup tests. |
| Smoke tests | Accidental HTTP/Facebook action | LxH | Monkeypatch `request_json`; never start server/browser; assert no approval/live endpoints. |
| Smoke script change | Behavior drift | MxM | YAGNI: edit only if RED test requires; preserve `dryRun=True`. |
| Commit prep | Local artifacts included | MxM | `git status --short`; add explicit file list only. |

## Backward compatibility

- `setup.py` CLI and generated FBKit `AGENTS.md`/`GEMINI.md` behavior must remain compatible.
- Smoke script args and exit codes remain: API error `1`, no session `2`, dry-run incomplete `3`, success `0`.

## Test matrix

- Unit: setup source cleanup and generated Codex safety text.
- Unit: smoke helpers already covered.
- Unit: `run_smoke` success/failure orchestration with fake API router.
- E2E: explicitly out of scope; no real network/Facebook actions.

## Rollback

- Before commit: `git restore setup.py scripts\fbkit-dry-run-smoke.py tests\unit\test_setup_generation.py tests\unit\test_fbkit_dry_run_smoke_script.py`.
- After commit: `git revert <new-commit-sha>`; previous hardening commit `c896110` untouched.

## Success criteria

- Stale Google Flow constants removed from `setup.py`.
- `run_smoke` orchestration covered without network/Facebook.
- Targeted pytest command passes.
- Changes ready for local commit; no push.

## Unresolved questions

- None.
