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

## Amendment (2026-09-14, GATES-1-T3 read)

The decision as written binds every task immediately: implement the baseline as a
prerequisite, update the bounded plan and scope to include it before
implementation, failures blocking completion. That has not happened in any story
since, and the result is worse than the gap it was meant to close — tasks either
silently skip it or contract checks that cannot pass, which is how GATES-1-T1's
seal failed. T1 named it out of scope and passed it to T3; T3 deferred it again.
A requirement everything quietly violates is not enforcement.

The repository state it would bind to: `ruff format --check` reformats 97 files,
the ruff errors in a touched harness file are identical on `origin/main`, and a
new pytest suite's errors are all F811 against pytest's own fixture-argument
pattern, which ruff is not configured for here. Enforcing that as-is fails
everything for reasons unrelated to any change under review.

**Amended:** the baseline binds a task only once the tooling is CONFIGURED — Ruff
and Pyright pinned, their configuration committed, existing violations fixed or
explicitly justified, and both wired into `verify.py` and CI. Until that
configuration lands, a task verifies with its suite and MUST NOT contract Ruff or
Pyright commands, because an unrunnable verify command fails at the seal, after
implementation and review have already passed.

Configuring it remains required work, not optional: it is the prerequisite this
decision always described, now stated as a piece of work with an owner rather
than an obligation on every unrelated task. The rest of the decision — Ruff for
lint and format, Pyright for types, the same checks locally and in CI, no blanket
suppressions, generated clients declaring their own language's checks — is
unchanged.

## Consequences
Implement the quality baseline as an explicit prerequisite to coordinator implementation. Fix existing violations; keep mechanical formatting separate from behavior changes and do not introduce blanket suppressions to obtain green results. Regression coverage must prove missing configuration and deliberate violations fail. Update the bounded plan and scope to include this prerequisite before implementation; this decision does not itself approve an as-yet-unsaved story or task plan. Existing verification, independent review, delegation and shipping gates remain in force for both coordinators.
