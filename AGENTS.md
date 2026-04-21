# AGENTS.md

This file provides guidance to OpenCode when working with code in this repository.

## Project Overview

**Name:** claudekit-engineer  
**Type:** Node.js/TypeScript  
**Description:** A comprehensive boilerplate template for building professional software projects with **CLI Coding Agents** (**Claude Code** and **Open Code**). This template provides a complete development environment with AI-powered agent orchestration, automated workflows, and intelligent project management.

## Role & Responsibilities

Your role is to analyze user requirements, delegate tasks to appropriate sub-agents, and ensure cohesive delivery of features that meet specifications and architectural standards.

## Workflows

- Primary workflow: `./.claude/rules/primary-workflow.md`
- Development rules: `./.claude/rules/development-rules.md`
- Orchestration protocols: `./.claude/rules/orchestration-protocol.md`
- Documentation management: `./.claude/rules/documentation-management.md`
- And other workflows: `./.claude/rules/*`

**IMPORTANT:** Analyze the skills catalog and activate the skills that are needed for the task during the process.  
**IMPORTANT:** DO NOT modify skills in `~/.claude/skills` directory directly. MUST modify skills in this current working directory unless you are asked to do so.  
**IMPORTANT:** You must follow strictly the development rules in `./.claude/rules/development-rules.md` file.  
**IMPORTANT:** Before you plan or proceed any implementation, always read the `./README.md` file first to get context.  
**IMPORTANT:** Before fixing any bug, always read `./docs/common-issues.md` first. If the symptom matches, try the documented checks and recovery path before changing code.  
**IMPORTANT:** After every bug fix, update `./docs/common-issues.md` using this exact format: `Symptoms / Root Cause / Common Triggers / Solutions / Verification`.  
**IMPORTANT:** Do not consider bug-fix work complete until `./docs/common-issues.md` has been updated or the matching existing entry has been improved.  
**IMPORTANT:** Sacrifice grammar for the sake of concision when writing reports.  
**IMPORTANT:** In reports, list any unresolved questions at the end, if any.

## Plan Verification Rules

Apply before finalizing any multi-step implementation plan or bug-fix plan. Trust but verify between repo scan, assumptions, and final plan.

### Verification discipline

1. Verify factual claims against repo files - re-check every endpoint, request type, env var, path, port, and model-related claim from code or README. Do not copy assumptions from memory.
2. Trace behavior, not just filenames - if a plan mentions an existing field, route, or worker stage, verify when it changes and under what conditions it changes.
3. No fabricated APIs or symbols - do not invent route names, extension messages, request types, service helpers, or Google Flow concepts that do not exist in this repo.
4. Verify state lifetime before adding fields - confirm whether state lives in request scope, worker loop, SQLite row, extension storage, browser session, or runtime files before changing an existing structure.
5. Verify bug premise against `./docs/common-issues.md` first - if the issue already matches a known pattern, the plan must use the documented checks before proposing code changes.
6. Match config and payload shape exactly - if a plan reuses an existing request body, scene payload, or config object, verify field names and required values exactly as implemented.
7. Verify external or upstream-facing endpoints before adding them to a plan - FlowKit has internal API routes plus Google Flow behavior through the extension; do not conflate them.

### Scope and coverage

8. Scan backend and extension separately - `agent/` and `extension/` are different systems with different responsibilities. Do not assume a fix in one covers the other.
9. Enumerate all callers before changing shared contracts - if a route, model, or payload changes, list the API handler, worker code, extension usage, skills, and tests that must move with it.
10. Verify async pipeline dependencies - for image and video generation plans, confirm prerequisites like reference images, UUID `media_id` values, and downstream reset behavior before proposing changes.
11. Search delete and rename scope deeply - if removing or renaming a symbol, grep the whole repo and list every affected reference in the plan.

### Phasing and ordering

12. Re-scout when scope changes - if a deferred phase becomes active, re-check the current code instead of reusing stale assumptions from earlier notes.
13. Make phase gates explicit - each phase should state its verify condition, for example route tests pass, extension config still loads, or `/health` returns the expected state.
14. Bug fix plans need reproduction first - write down how to reproduce or test the failure before proposing the fix path.
15. Documentation updates are part of done - if a bug is fixed or a recurring issue is clarified, the plan must include updating `./docs/common-issues.md` before completion.

## Development Principles

- **YAGNI**: You Aren't Gonna Need It - avoid over-engineering
- **KISS**: Keep It Simple, Stupid - prefer simple solutions
- **DRY**: Don't Repeat Yourself - eliminate code duplication

## Documentation

Keep all important docs in `./docs` folder.

Bug triage knowledge and repeated bug fixes must be recorded in `./docs/common-issues.md`.
This file is the mandatory memory log for bug symptoms, proven causes, triggers, fixes, and verification.

```text
./docs
|- project-overview-pdr.md
|- code-standards.md
|- codebase-summary.md
|- common-issues.md
|- design-guidelines.md
`- system-architecture.md
```

## External Files

Reference external instruction files in `opencode.json`:

```json
{
  "instructions": ["docs/*.md", ".opencode/agents/*.md"]
}
```

---

*Generated by ClaudeKit OpenCode Generator*  
*Date: 2026-04-03*
