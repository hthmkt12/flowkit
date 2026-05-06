# Phase 03 Validate Doc Links And Safety Language

## Context Links

- Overview: `plan.md`
- Doc update phase: `phase-02-update-fbkit-canonical-docs.md`
- Active docs: `../../README.md`, `../../ARCHITECTURE.md`, `../../docs/codebase-summary.md`

## Overview

Priority: Medium

Status: Completed

This phase validates that documentation changes did not create broken guidance, unsafe wording, or accidental runtime edits.

## Requirements

- Verify active-vs-legacy wording.
- Verify Safety Gate defaults still appear.
- Verify no code/runtime files changed.
- Run only read-only validation commands.

## Related Files

- Read/validate: `README.md`
- Read/validate: `ARCHITECTURE.md`
- Read/validate: `docs/codebase-summary.md`
- Read/validate: `CLAUDE.md`
- Read/validate: `AGENTS.md`

## Implementation Steps

- [x] Step 1: Confirm FBKit is named as active in key docs.

Run:

```powershell
rg -n "FBKit is the active|active product|active system|Current Active Architecture" README.md ARCHITECTURE.md CLAUDE.md AGENTS.md
```

Expected: matches in `README.md`, `ARCHITECTURE.md`, `CLAUDE.md`, and `AGENTS.md`.

- [x] Step 2: Confirm legacy Google Flow is labeled archive/reference.

Run:

```powershell
rg -n "Legacy Google Flow Archive|legacy FlowKit|archive|reference use" README.md ARCHITECTURE.md docs/codebase-summary.md
```

Expected: matches in `README.md` and `ARCHITECTURE.md`; optional match in `docs/codebase-summary.md`.

- [x] Step 3: Confirm Safety Gate defaults remain visible.

Run:

```powershell
rg -n "LIVE_ACTIONS_ENABLED.*false|DRY_RUN_DEFAULT.*true|APPROVAL_REQUIRED.*true|Safety Gate|dry-run first|extension DOM-action guard" README.md ARCHITECTURE.md docs/codebase-summary.md CLAUDE.md AGENTS.md
```

Expected: all three env defaults and Safety Gate language are present.

- [x] Step 4: Confirm no runtime files changed.

Run:

```powershell
git diff --name-only
```

Expected changed files are limited to:

```text
ARCHITECTURE.md
README.md
docs/codebase-summary.md
plans/260506-2223-fbkit-active-legacy-doc-boundary/plan.md
plans/260506-2223-fbkit-active-legacy-doc-boundary/phase-01-audit-active-legacy-boundary.md
plans/260506-2223-fbkit-active-legacy-doc-boundary/phase-02-update-fbkit-canonical-docs.md
plans/260506-2223-fbkit-active-legacy-doc-boundary/phase-03-validate-doc-links-and-safety-language.md
```

If `README.md` or `docs/codebase-summary.md` were not needed, they should not appear.

- [x] Step 5: Optional markdown sanity check.

If the repo has markdown tooling, run it. If not, perform manual review of heading order and fenced code blocks in changed files.

Manual checklist:

```text
- ARCHITECTURE.md starts with current FBKit architecture.
- Legacy Google Flow section is visibly labeled archive/reference.
- README quick start commands still use safe defaults.
- docs/codebase-summary.md still says Safety Gate is canonical verified behavior.
- No instruction tells users to approve live tasks during dry-run validation.
```

## Success Criteria

- Validation commands match expected docs.
- Changed files are documentation and plan files only.
- No code, DB, extension runtime, or generated artifact changed.
- Final report states whether Google Flow usage remains unresolved.

## Validation Notes

- `rg` was unavailable in this PowerShell environment, so Grep tool searches were used for active/legacy and Safety Gate wording checks.
- Scoped validation passed for plan-owned files: `ARCHITECTURE.md`, `docs/codebase-summary.md`, and `plans/260506-2223-fbkit-active-legacy-doc-boundary/**`.
- Broader `git status` shows unrelated changes outside this plan, including code/test files. They were not modified or reverted by this plan.

## Risk Assessment

| Risk | Mitigation |
|---|---|
| False sense of safety after docs-only change | State clearly no runtime behavior changed. |
| Missed stale reference | Use `rg` commands above before completion. |
| Accidental code edit | Check `git diff --name-only`. |

## Security Considerations

- Do not run `agent.main`.
- Do not run smoke scripts.
- Do not approve tasks.
- Do not change env flags.

## Next Steps

- If user confirms Google Flow is unused, create a separate legacy inventory/archive plan.
- If user confirms Google Flow is still used, create a separate active dual-domain documentation plan.

## Unresolved Questions

- Is any current user or script still using legacy Google Flow behavior from this repo?
