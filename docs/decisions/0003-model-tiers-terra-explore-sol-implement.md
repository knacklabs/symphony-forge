---
status: accepted
confirmed_by: "Ravi"
date: 2026-07-14
stories: []
---

# Model tiers: Terra@high explores, Sol@medium implements

## Context

OpenAI's GPT-5.6 family is tiered (Sol flagship, Terra mid, Luna fast).
An earlier draft of this record pinned implementation to Luna@xhigh; the
platform owner revised it same-day: exploration deserves the mid tier at
high effort, implementation the flagship at medium. Codex profiles
(overlay TOML files, `--profile`) allow per-context pins in one repo.

## Decision

- Code exploration (planning phase): `/codex:rescue --model gpt-5.6-terra
  --effort high` (read-only by default; the explore profile serves
  Codex-native sessions).
  Claude Code NEVER explores application code itself.
- Implementation (/codex:rescue): gpt-5.6-sol @ medium
  (.codex/config.toml); effort escalates to high for migrations,
  cross-domain refactors, concurrency, and security-sensitive work.

See decision 0031 for Lite mode's bounded Terra@high write extension.

## Consequences

- Exploration is thorough without flagship cost; implementation gets the
  flagship where its output is the product.
- Per-agent TOMLs (planner-high, docs-decomposer, functional-checker)
  keep their own pins.
- Changing tiers again is an edit to two TOML files + this record —
  watch fix-after-review rates in retro to validate the medium default.
