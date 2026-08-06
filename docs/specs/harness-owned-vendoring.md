---
slug: harness-owned-vendoring
title: Harness-owned vendoring
status: confirmed
saved: 2026-08-06T17:41:21+00:00
---

# Harness-owned vendoring

## Why

`forge init` and `forge adopt` vendor the harness machinery into a repo. Today
both copy `.claude` and `.codex/skills` **wholesale from the repo the command
runs in** (`repo_root()`). In symphony-forge that is harmless — its `.claude` is
all harness-owned. But when a **client** repo that carries its own Claude/Codex
skill runs the vendored gate tests in CI, `repo_root()` is the client, so `init`
copies the client's `.claude/skills/<client>/SKILL.md` into a scaffold whose
`<!-- canon: skills/<client>/... -->` target lives in a root `skills/` that is
never vendored — a dangling canon marker that fails `check_dual_runtime`. First
seen in knacklabs/cadence: `factory-scaffold` red, ~13 and ~6 test failures,
~8 of them from this one cause. `upgrade` already filters `.claude` to a
harness-owned set; `init` and `adopt` never got the same treatment.

Separately, the vendored `factory-scaffold` workflow runs the harness's own
regression suite (`pytest factory/tests`) in every client repo, but a few tests
assert on symphony-forge's private fixtures (the `FORGE-INIT-1` history and
roadmap) and can never pass elsewhere — so the vendored CI is red in a client
even once the vendoring bug is fixed.

## Behaviour

- `init` and `adopt` vendor **only harness-owned paths** from `.claude` and
  `.codex`: `.claude/{CLAUDE.md, settings.json, skills/forge}` and the harness's
  own `.codex/agents/*` and `.codex/skills/forge` — never the source repo's other
  `.claude/skills/*` or `.codex/skills/*` content. The harness-owned set is
  defined in ONE place and shared by `init`, `adopt` and `upgrade`.
- A client repo's own `.claude/skills/*` / `.codex/skills/*` are therefore never
  copied into a scaffold, so a scaffold never carries a dangling canon marker to
  a path the harness does not vendor.
- The harness regression tests that assert on symphony-forge's own history and
  roadmap fixtures **skip when those fixtures are absent**, so the vendored
  `factory-scaffold` workflow passes in a client repo while still running every
  portable check (structural scaffold, dual-runtime, and the rest of the suite).
- `init`/`adopt`/`upgrade` of symphony-forge itself, and the suite in
  symphony-forge's own CI, behave exactly as before.

## Acceptance criteria

- `forge init` from a source repo carrying an extra
  `.claude/skills/<client>/SKILL.md` (with a root-level canon target) produces a
  scaffold that does NOT contain that client skill, and `check_dual_runtime` is
  clean on the scaffold.
- The harness-owned `.claude`/`.codex` set is defined once and used by `init`,
  `adopt` and `upgrade` — a test proves the three agree.
- The fixture-bound tests (`FORGE-INIT-1` history / precontract-stories /
  shipped-roadmap) skip when their fixture is absent and still run in
  symphony-forge.
- A simulated client-repo run of the vendored `factory-scaffold` checks (init +
  dual-runtime + the gated suite) passes with no dangling canon and no
  symphony-forge-fixture failure.
- `forge init`/`adopt`/`upgrade` of symphony-forge behave exactly as before —
  every existing test stays green.
