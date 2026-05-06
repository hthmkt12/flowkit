# FBKit Safe Hardening Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove stale Google Flow guidance and close the remaining safe-mode task-creation/approval footguns without triggering live Facebook/social actions.

**Architecture:** Keep safety enforcement centralized at the task persistence boundary (`agent/db/crud.py`) and explicit at the API boundary (`agent/api/tasks.py`). Documentation updates should be static root instruction replacements only; do not regenerate legacy tool artifacts unless the stale generator must be neutralized.

**Tech Stack:** Python, FastAPI route functions, SQLite CRUD helpers, pytest async tests, Windows PowerShell verification.

---

## Files to modify

- `AGENTS.md` — replace stale Google Flow / `/fk:*` content with concise FBKit safety-first agent instructions. Remove the auto-generated warning if editing directly, or also neutralize `setup.py` regeneration if necessary.
- `CLAUDE.md` — same replacement, tailored for Claude but with identical FBKit safety rules.
- `agent/db/crud.py` — harden `create_task(...)` so direct mutating task inserts cannot bypass Safety Gate by default, while preserving read-only tasks and allowing internal trusted callers to pass an explicit opt-out only when needed.
- `agent/api/tasks.py` — make approval fail explicitly when `LIVE_ACTIONS_ENABLED=false`; keep current pending-status, malformed-payload, and audit behavior when live actions are enabled.
- `tests/unit/test_safety_gate.py` — add/update TDD tests for direct CRUD hardening and approval-disabled behavior.
- Optional only if tests reveal stale regeneration risk: `setup.py` — stop generating Google Flow root guidance or update the generated root body to FBKit safety-first instructions. Do not touch `.claude/commands/`, `.opencode/`, generated skill files, or local artifacts.

## TDD tasks

### Task 1: Replace root instructions with FBKit safety-first guidance

- [x] Write/inspect docs expectations manually first: root `AGENTS.md` and `CLAUDE.md` must say FBKit is dry-run first; do not trigger Facebook/social live actions; use PowerShell pytest command; do not commit/push unless asked; avoid generated/local artifacts; stale Google Flow, media UUID, `/fk:*`, batch video pipeline guidance must be removed.
- [x] Replace both files with a short shared structure:
  - project identity: `FBKit / FlowKit`
  - safety defaults: `LIVE_ACTIONS_ENABLED=false`, `DRY_RUN_DEFAULT=true`, `APPROVAL_REQUIRED=true`
  - critical rule: never perform/enable live Facebook/social actions unless explicitly requested and safe gates are verified
  - implementation rules: minimal changes, TDD, no generated/local artifacts unless necessary, no commit/push
  - verification command format: `& ".\.venv\Scripts\python.exe" -m pytest ...`
- [x] Do not update generated command files. If keeping `setup.py` unchanged would immediately reintroduce stale root docs in normal workflows, update only the root-doc generation template to emit the same FBKit safety-first content.

### Task 2: Close direct `crud.create_task(...)` mutating bypass

- [x] Add failing tests in `tests/unit/test_safety_gate.py`:
  - `test_crud_create_task_forces_direct_mutating_task_to_dry_run`: with `LIVE_ACTIONS_ENABLED=false`, direct `crud.create_task(..., task_type="POST_TEXT", payload=json.dumps({"content":"direct","dryRun":False,"_serverApproved":True}))` stores payload with `dryRun is True`, `safetyReason == "live_actions_disabled"`, and `_serverApproved` is absent or ineffective.
  - `test_crud_create_task_preserves_direct_read_only_payload`: direct `crud.create_task(..., task_type="CHECK_LOGIN", payload=json.dumps({"dryRun":False,"note":"read-only"}))` preserves payload and does not add `safetyReason`.
  - `test_crud_create_task_internal_trusted_caller_can_preserve_payload`: if an opt-out is required for existing tests/internal flows, call `crud.create_task(..., task_type="POST_TEXT", payload=json.dumps({"content":"trusted","dryRun":False,"_serverApproved":True}), enforce_safety=False)` and assert exact payload is preserved. Keep this escape hatch keyword-only and internal-looking; do not expose it through API schemas.
- [x] Run expected failures:
  - `& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_safety_gate.py::test_crud_create_task_forces_direct_mutating_task_to_dry_run tests\unit\test_safety_gate.py::test_crud_create_task_preserves_direct_read_only_payload tests\unit\test_safety_gate.py::test_crud_create_task_internal_trusted_caller_can_preserve_payload -q`
- [x] Minimal implementation in `agent/db/crud.py`:
  - import `json`, `JSONDecodeError`, and `enforce_payload` if not already available.
  - change signature to `async def create_task(account_id: str, task_type: str, *, enforce_safety: bool = True, **kwargs) -> dict:` or equivalent preserving existing callers.
  - when `enforce_safety` and `payload` is present/absent, parse JSON payload safely, call `enforce_payload(task_type, payload_dict)`, and store `json.dumps(...)` only when the enforced payload is non-empty.
  - for malformed existing direct payloads, fail closed for mutating tasks with a clear `ValueError` rather than inserting unsafe raw JSON; preserve current behavior for non-mutating tasks if compatibility requires it.
  - strip external approval/quota markers either by sharing the API stripping helper in a neutral service or duplicating three explicit pops locally; prefer a small private CRUD helper to avoid API-layer imports.
- [x] Update only existing internal/tests callers that intentionally seed already-approved live payloads to pass `enforce_safety=False`; do not blanket-disable safety for API route callers, scheduler, auto-seed, posts, messages, groups, or spy/seeder flows.

### Task 3: Make approval explicit when live actions are disabled

- [x] Add failing test in `tests/unit/test_safety_gate.py`:
  - `test_approve_task_rejects_when_live_actions_disabled`: set `LIVE_ACTIONS_ENABLED=false`; create a pending `POST_TEXT`; call `tasks_api.approve_task(task["id"])`; assert `HTTPException.status_code == 409` and detail includes `LIVE_ACTIONS_ENABLED=false` or `Live actions are disabled`; reload task and assert `_serverApproved` is not present and `dryRun` remains true if safety enforcement added it.
- [x] Run expected failure:
  - `& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_safety_gate.py::test_approve_task_rejects_when_live_actions_disabled -q`
- [x] Minimal implementation in `agent/api/tasks.py`:
  - import `agent.config`.
  - after confirming task exists and before modifying payload/logging approval, if `not config.LIVE_ACTIONS_ENABLED`, raise `HTTPException(409, "Live actions are disabled (LIVE_ACTIONS_ENABLED=false); approval cannot enable live dispatch")`.
  - keep existing behavior for non-pending, malformed payload, atomic pending recheck, and audit logging when live actions are enabled.

### Task 4: Regression verification and cleanup

- [x] Run focused safety tests:
  - `& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_safety_gate.py -q`
- [x] Run CRUD tests because `crud.create_task` is shared:
  - `& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_crud.py -q`
- [x] If the suite has no live-action side effects, run broader unit regression:
  - `& ".\.venv\Scripts\python.exe" -m pytest tests\unit -q`
- [x] Inspect changes only; do not commit or push:
  - `git diff -- AGENTS.md CLAUDE.md agent\db\crud.py agent\api\tasks.py tests\unit\test_safety_gate.py setup.py`

## Notes / guardrails

- Do not start the agent, connect the extension, approve real tasks through HTTP, or enable live Facebook/social actions.
- Keep the CRUD hardening small: no new policy framework, no database migration, no broad refactor.
- Preserve read-only task behavior: no forced `dryRun`/`safetyReason` for non-mutating task types.
- Preserve internal callers by using an explicit trusted opt-out only where tests or worker-approved fixtures demonstrably need pre-approved payloads.
