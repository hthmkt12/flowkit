# Phase 05: Docs, Validation, And Rollout Gates

## Context Links

- [Plan overview](./plan.md)
- `README.md`
- `docs/codebase-summary.md`
- `docs/system-architecture.md`
- `docs/project-roadmap.md`
- `docs/code-standards.md`

## Overview

Priority: P1  
Status: Complete

Keep documentation, tests, and rollout gates aligned with each safety or scale change. This phase runs alongside all other phases.

## Key Insights

- Safety behavior that is not documented will be misused.
- Scale work without rollout gates will create false confidence.
- FBKit needs explicit progression gates: dry-run, one account, 2 profiles, 5 profiles, 10 profiles, then distributed planning.

## Requirements

Functional:

- Update docs after verified runtime changes.
- Maintain dry-run smoke tests.
- Add rollout checklist for live tests and multi-profile pilots. **Done:** `docs/rollout-gates.md`.
- Keep operator warnings prominent in README. **Done:** README links rollout gates and keeps live warning.

Non-functional:

- Docs must describe verified behavior, not aspirational features.
- Avoid documenting 50-account support until validated.

## Architecture

Documentation should track the runtime truth:

```text
code change -> tests -> verification result -> docs update -> roadmap status update
```

## Related Files

Likely modify as phases complete:

- `README.md`
- `docs/codebase-summary.md`
- `docs/system-architecture.md`
- `docs/project-roadmap.md`
- `docs/code-standards.md`
- `docs/common-issues.md`
- `docs/rollout-gates.md`

Optional create only when verified:

- `docs/deployment-guide.md`
- `docs/api-reference.md`

## Implementation Steps

1. After Phase 01, document live arming and status fields. **Done.**
2. After Phase 02, document account queue/quota behavior. **Done.**
3. After Phase 03, document multi-profile pilot gates and limits. **Done in `docs/rollout-gates.md`.**
4. After Phase 04, document distributed worker readiness only as implemented. **Done.**
5. Keep roadmap status honest: planned, pilot, validated, or not ready. **Done.**

## Todo List

- [x] Define rollout gates.
- [x] Keep README safety warning current.
- [x] Update architecture docs after each verified change.
- [x] Add rollout/runbook gates only for verified behavior.
- [x] Keep docs under source-of-truth `docs/`.

## Success Criteria

- A new operator can tell whether FBKit is dry-run, armed, live-ready, or not ready.
- Docs do not claim 50-account support before validation.
- Verification commands are listed and current.

## Completion Evidence

- `docs/rollout-gates.md` defines Gate 0 local dry-run, Gate 1 one dedicated test account, Gate 2 two-profile dry-run pilot, Gate 3 five-profile dry-run pilot, Gate 4 ten-profile dry-run pilot, Gate 5 distributed readiness review, and optional controlled-live test gate.
- README links `docs/rollout-gates.md` and keeps live action warnings prominent.
- `docs/project-roadmap.md` links rollout gates and keeps 50-account/distributed/live claims explicitly unvalidated.
- Static regression tests in `tests/unit/test_rollout_gates_docs.py` verify the rollout gates doc and links.

## Risk Assessment

- Risk: docs drift from code. Mitigate by making docs update part of every phase completion.
- Risk: users overestimate safety. Mitigate with explicit warnings and rollout gates.

## Security Considerations

- Documentation must never imply main-account live automation is safe.
- Live action instructions must require dedicated test/business assets and explicit approval.

## Next Steps

Keep this phase as a continuous guardrail after completion. Update rollout gates whenever runtime safety, status, or validation behavior changes.
