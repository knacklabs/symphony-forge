---
status: accepted
confirmed_by: "User"
date: 2026-09-08
stories: [FORGE-COORD-1]
---

# Enforce the declared static quality baseline

## Context
The plan grill requires automated lint, formatting and applicable type checking, but the harness leaves FACTORY_QUALITY_CMD optional and uses a scaffold check as its typecheck command. The user explicitly chose permanent enforcement on 2026-09-08 rather than deferring this pre-existing gap.

## Decision
Use Ruff for Python lint and formatting and Pyright for Python type checking: Ruff supplies both lint and format checks in one tool, and Pyright builds on the repository's existing import-resolution configuration. Pin the tools and run the same configured checks locally and in CI, with failures blocking completion. Missing required quality configuration must fail clearly. Generated clients declare checks for their own language; they must not inherit harness Python checks as product validation.

## Consequences
Implement the quality baseline as an explicit prerequisite to coordinator implementation. Fix existing violations; keep mechanical formatting separate from behavior changes and do not introduce blanket suppressions to obtain green results. Regression coverage must prove missing configuration and deliberate violations fail. Update the bounded plan and scope to include this prerequisite before implementation; this decision does not itself approve an as-yet-unsaved story or task plan. Existing verification, independent review, delegation and shipping gates remain in force for both coordinators.
