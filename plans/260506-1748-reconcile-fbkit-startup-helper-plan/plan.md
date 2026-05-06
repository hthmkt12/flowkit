---
title: "Reconcile FBKit startup helper plan status"
description: "Plan to verify the safe Windows startup helper, update stale plan status, and run focused safety regression without live Facebook actions."
status: completed
priority: P2
effort: 30m
branch: main
tags: [fbkit, safety, docs, verification, no-live-actions]
created: 2026-05-06
---

# Reconcile FBKit Startup Helper Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development. Implement task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the existing safe Windows startup helper, reconcile stale plan metadata, and confirm focused FBKit safety tests still pass.

**Architecture:** No runtime behavior changes. Treat this as a docs/status reconciliation plus verification batch. Keep all Facebook mutation safety defaults intact and do not start live/social action flows.

**Tech Stack:** Markdown plans, PowerShell, Python pytest via Windows repo venv (`& ".\.venv\Scripts\python.exe" -m pytest ...`).

---

## Scope Lock

Allowed files:
- Modify: `plans/260506-1215-safe-windows-startup-helper/plan.md`
- Modify only if test evidence shows wording drift: `README.md`

Read/verify only:
- `scripts/start-fbkit-safe.ps1`
- `tests/unit/test_safe_start_script.py`
- `tests/unit/test_fbkit_dry_run_smoke_script.py`
- `tests/unit/test_safety_gate.py`
- `tests/unit/test_extension_dry_run.py`

Out of scope:
- No agent startup.
- No Chrome/browser/Facebook actions.
- No approval endpoint calls.
- No `LIVE_ACTIONS_ENABLED=true`.
- No runtime smoke unless separately approved by user.
- No feature work.

## Initial Facts Before Execution

- `scripts/start-fbkit-safe.ps1` exists.
- `tests/unit/test_safe_start_script.py` exists.
- README mentions `scripts/start-fbkit-safe.ps1` and `-PrintOnly`.
- Existing plan `plans/260506-1215-safe-windows-startup-helper/plan.md` started with `status: pending`.
- That old plan started with expected test file `tests/unit/test_start_fbkit_safe_script.py`, but actual file is `tests/unit/test_safe_start_script.py`.
- Working tree was clean during brainstorm (`git status --short` no changed files).

## Task 1: Verify startup helper tests

**Files:**
- Read: `scripts/start-fbkit-safe.ps1`
- Read: `tests/unit/test_safe_start_script.py`

- [x] **Step 1: Run focused startup helper test**

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_safe_start_script.py -q
```

Expected:

```text
3 passed
```

- [x] **Step 2: If test fails, stop and diagnose**

Do not update plan status if this command fails. Capture failure output and fix only after separate approval if code/docs changes are needed beyond plan reconciliation.

## Task 2: Reconcile old startup helper plan status

**Files:**
- Modify: `plans/260506-1215-safe-windows-startup-helper/plan.md`

- [x] **Step 1: Update YAML frontmatter only after Task 1 passes**

Change:

```yaml
status: pending
```

to:

```yaml
status: completed
```

- [x] **Step 2: Correct stale test filename reference**

In the old plan, replace references to:

```text
tests/unit/test_start_fbkit_safe_script.py
```

with:

```text
tests/unit/test_safe_start_script.py
```

- [x] **Step 3: Add completion note near Done criteria**

Add a concise note:

```markdown
## Completion Note

- Implemented as `scripts/start-fbkit-safe.ps1`.
- Covered by `tests/unit/test_safe_start_script.py`.
- README documents safe helper and `-PrintOnly` mode.
- Verified with focused pytest command before marking complete.
```

## Task 3: Run focused FBKit safety regression

**Files:**
- Read/test: `tests/unit/test_safe_start_script.py`
- Read/test: `tests/unit/test_fbkit_dry_run_smoke_script.py`
- Read/test: `tests/unit/test_safety_gate.py`
- Read/test: `tests/unit/test_extension_dry_run.py`

- [x] **Step 1: Run focused regression**

```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests\unit\test_safe_start_script.py tests\unit\test_fbkit_dry_run_smoke_script.py tests\unit\test_safety_gate.py tests\unit\test_extension_dry_run.py -q
```

Expected:

```text
all selected tests pass
```

- [x] **Step 2: If regression fails, do not broaden scope automatically**

Report failing test names and error summaries. Do not mask failures. Do not start agent/browser/Facebook.

## Task 4: Inspect final diff and prepare optional commit

**Files:**
- Inspect: `plans/260506-1215-safe-windows-startup-helper/plan.md`
- Inspect: this plan file

- [x] **Step 1: Inspect diff**

```powershell
git diff -- plans\260506-1215-safe-windows-startup-helper\plan.md plans\260506-1748-reconcile-fbkit-startup-helper-plan\plan.md
git status --short
```

Expected:

```text
Only plan/status docs changed.
No generated logs, databases, browser artifacts, or secret files staged.
```

- [x] **Step 2: Commit only if user explicitly asks**

Suggested commit message:

```text
docs: reconcile fbkit startup helper plan status
```

Do not commit automatically. Do not push.

## Success Criteria

- Startup helper focused test passes.
- Old startup helper plan status accurately reflects implementation state.
- Old plan references actual test file path.
- Focused safety/smoke regression passes.
- No live Facebook/social actions triggered.
- No server/browser started.
- No approval/live flags changed.

## Completion Evidence

- Startup helper focused test: `3 passed in 0.09s`.
- Focused FBKit safety/smoke regression after docs update: `80 passed in 6.57s`.
- Tester subagent reran focused regression independently: `80 passed in 6.83s`.
- No live Facebook/social actions, agent startup, browser startup, or approval endpoints were used.

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---:|---|
| Accidentally claiming helper complete without test evidence | Medium | Task 1 must pass before status update |
| Accidental live Facebook mutation | High | No runtime smoke, no approval endpoint, no live flags |
| Docs-only change hiding real test failure | Medium | Stop on failing focused tests |
| Over-cleaning legacy docs | Low | Do not touch legacy docs in this plan |

## Dependencies

- Repo venv exists at `.venv\Scripts\python.exe`.
- Pytest dependencies installed.
- PowerShell available on Windows.

## Unresolved Questions

- None. Used `status: completed` without adding a new `completed:` field to preserve existing plan metadata style.
