# FBKit Active Legacy Doc Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make FBKit the explicit active product while preserving legacy Google Flow material as archive/reference only.

**Architecture:** Documentation-first boundary lock. No runtime behavior, Safety Gate code, extension guard, database schema, or live-action settings change in this plan. `docs/codebase-summary.md` remains the canonical verified FBKit safety source.

**Tech Stack:** Markdown docs, Python/FastAPI project context, Chrome extension context, SQLite task queue context, Windows PowerShell validation commands.

---

## Status

| Phase | File | Status |
|---|---|---|
| 1 | `phase-01-audit-active-legacy-boundary.md` | Completed |
| 2 | `phase-02-update-fbkit-canonical-docs.md` | Completed |
| 3 | `phase-03-validate-doc-links-and-safety-language.md` | Completed |

## Key Dependencies

| Dependency | Why it matters |
|---|---|
| `README.md` | First operator-facing entry point; already says FBKit active but contains long legacy archive. |
| `ARCHITECTURE.md` | Currently mostly Google Flow architecture; highest confusion risk. |
| `docs/codebase-summary.md` | Verified current FBKit Safety Gate and runtime behavior. |
| `CLAUDE.md` and `AGENTS.md` | Agent safety/development rules; should not be weakened. |

## Non-Goals

- Do not change runtime code.
- Do not move or delete legacy files.
- Do not enable live Facebook actions.
- Do not call task approval endpoints.
- Do not commit unless user explicitly requests it.

## Success Criteria

- A reader can identify FBKit as the active product within the first screen of core docs.
- Legacy Google Flow docs are clearly marked as archive/reference, not current operational guidance.
- Safety Gate defaults remain prominent: `LIVE_ACTIONS_ENABLED=false`, `DRY_RUN_DEFAULT=true`, `APPROVAL_REQUIRED=true`.
- Documentation validation finds no stale wording that presents Google Flow as the active architecture.

## Execution Order

1. Complete Phase 1 audit before editing docs.
2. Complete Phase 2 doc updates with smallest possible edits.
3. Complete Phase 3 validation and only then report completion.

## Execution Notes

- `rg` was unavailable in this PowerShell environment, so validation used the Grep tool equivalent and scoped `git diff` commands.
- The broader working tree contains unrelated preexisting changes outside this plan, including code/test and legacy docs files. This plan-owned work is limited to `ARCHITECTURE.md`, `docs/codebase-summary.md`, and `plans/260506-2223-fbkit-active-legacy-doc-boundary/**`.
- `docs/codebase-summary.md` already had unrelated uncommitted readiness endpoint edits before this plan's cross-reference and active/legacy wording changes.

## Unresolved Questions

- Is any current user or script still using the legacy Google Flow pipeline from this repo?
