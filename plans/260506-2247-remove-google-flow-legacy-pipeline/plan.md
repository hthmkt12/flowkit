# Remove Google Flow Legacy Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the unused Google Flow legacy pipeline so the repository is FBKit-only.

**Architecture:** Delete legacy docs, generated command stubs, local skill docs, deprecated Google Flow code, and unused video-generation SDK/model code only after import checks. Preserve current FBKit FastAPI routes, Safety Gate, SQLite task queue, Chrome extension bridge, and dry-run defaults.

**Tech Stack:** Python FastAPI, SQLite, Chrome extension, Markdown docs, PowerShell validation.

---

## Status

| Phase | Scope | Status |
|---|---|---|
| 1 | Inventory and import proof | Completed |
| 2 | Delete pure legacy artifacts | Completed |
| 3 | Update current FBKit docs/setup wording | Completed |
| 4 | Remove unused legacy SDK/models if compile-safe | Completed |
| 5 | Validate and review | Completed |

## Confirmed Decision

User confirmed: Google Flow legacy pipeline is no longer used and should be removed.

## Scope Guard

- Do not change FBKit task behavior.
- Do not change Safety Gate defaults.
- Do not enable or approve live Facebook actions.
- Preserve current active files under `agent/api`, `agent/services`, `agent/db`, `agent/worker`, and `extension` unless validation proves a legacy-only dependency.
- Working tree already contains unrelated dirty files; only remove/update files required for this legacy removal.

## Planned Deletes

- `_deprecated/**`
- `docs/deployment-kit/**`
- `skills/fk-*.md`
- `skills/song-templates/**`
- `.claude/commands/fk-*.md`
- `setup.py`
- `tests/unit/test_setup_generation.py`
- `PLAN.md`
- `agent/sdk/**` if active imports remain self-contained only
- legacy-only `agent/models/**` if active imports remain absent

## Execution Notes

- Import inventory found no active `agent.main` route registration for Google Flow routers.
- Active-code search found `agent/sdk` and `agent/models` imports were self-contained inside the legacy SDK/model packages; tests did not import them.
- Removed pure legacy docs/skills/generated commands/deprecated code and legacy SDK/model packages.
- Removed legacy showcase images under `docs/images/**` because they only supported the deleted README showcase.
- Rewrote `README.md`, `ARCHITECTURE.md`, `docs/codebase-summary.md`, `docs/common-issues.md`, and `setup.sh` as FBKit-only docs/setup.
- Removed legacy dashboard project/video/scene pages and components, then fixed the active `Account` type used by `AccountsPage`.
- Rewrote `scripts/statusline.sh` to use current FBKit `/health` and `/api/status` only.
- Removed unused legacy `agent/utils/paths.py` and stale `.gitignore` setup generator comments.
- Removed stale extension side panel files and unused worker parsing helper that still modeled video-generation request/response shapes.
- Ignored local `.claude/skills/**` and `.opencode/skills/**` mirror artifacts; no such skill files were tracked.
- Final active tracked scans excluding `plans/**` found no removed docs/runtime references.
- `compileall agent` passed after deletion.
- Full test suite passed: `205 passed`.
- Dashboard production build passed after legacy page removal.
- `git diff --check` passed with only Windows CRLF warnings.
- Final code review found no blockers.

## Planned Updates

- `README.md`: remove legacy Google Flow archive sections and keep FBKit quick start/safety docs.
- `ARCHITECTURE.md`: remove legacy Google Flow archive sections, leave FBKit current architecture only.
- `docs/codebase-summary.md`: remove legacy dual-domain references.
- `docs/common-issues.md`: replace legacy troubleshooting with FBKit-only issues or delete if empty.
- `setup.sh`: remove Google Flow onboarding wording; keep if still useful for FBKit bootstrap.
- `skills/README.md`: remove if it only indexes deleted legacy skills.

## Validation Commands

```powershell
& ".\.venv\Scripts\python.exe" -m compileall agent
& ".\.venv\Scripts\python.exe" -m pytest tests\unit -q
& ".\.venv\Scripts\python.exe" -m pytest -q
```

## Success Criteria

- No current docs/code/tests reference `Google Flow`, `Legacy FlowKit`, `_deprecated`, `docs/deployment-kit`, `skills/fk-*`, or `.claude/commands/fk-*` except historical plan files.
- FBKit startup imports compile successfully.
- Unit/full tests pass or unrelated failures are documented.
- Safety defaults remain unchanged: `LIVE_ACTIONS_ENABLED=false`, `DRY_RUN_DEFAULT=true`, `APPROVAL_REQUIRED=true`.

## Unresolved Questions

- None.
