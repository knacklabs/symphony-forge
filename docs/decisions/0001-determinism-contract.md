---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "Ravi"
date: 2026-07-10
stories: []
---

# Determinism contract: pinned skills, schema-validated recorders

## Context

Devs kept facing the same open choices: which skill to use per phase, what
shape an evidence artifact should have, and whether the process stays
deterministic when someone brings a new tool. Artifact shapes lived as prose
bullet lists in prompt files, recorders accepted any JSON, and the gate
duck-typed fields — so a nonconforming reviewer output could silently pass.

## Decision

`harness.yaml` is the per-phase skill ALLOWLIST; every externally-authored
artifact has a schema in `.agents/schemas/` carrying the pinned
`generated_by` values; recorders validate payloads against the schema and
hard-refuse nonconforming fields or unpinned generators, with no override.
Prompts are the interface, recorder commands are the contract.

## Consequences

- Adopting a new tool is a PR to `harness.yaml` + the schema file, propagated
  by `forge upgrade` — never a local dev choice.
- A dev mid-task with a genuinely better tool is blocked until that PR lands
  (accepted trade for uniformity).
- `generated_by` is declared by the recording agent: falsifiable, but only
  deliberately, and auditable — the same trust model as `plan assume`.
- The dual-runtime linter keeps schemas and the allowlist from diverging.
