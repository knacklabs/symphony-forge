---
status: accepted
confirmed_by: "User (explicit main coordinator model-selection instruction, Codex conversation 2026-09-13)"
date: 2026-09-13
stories: [FORGE-COORD-1]
supersedes: 0070-sol-specialized-workflow-models
---

# User selects the main coordinator model

## Context

Decision 0070 made the project-level Codex configuration select Sol/medium for
the main coordinator and high reasoning whenever that session entered Plan
mode. The user has now explicitly required the main coordinator's model and
reasoning effort to remain their choice. Forge still needs deterministic model
routing for every delegated worker, specialist, grill, review and Lite run that
the harness launches itself.

## Decision

The repository must omit the top-level `.codex/config.toml` keys `model`,
`model_reasoning_effort` and `plan_mode_reasoning_effort`. The host and user
therefore select the main coordinator model and reasoning, including Plan mode;
the repository places no model restriction on that main session.

Forge-managed execution remains pinned. Read-only exploration uses
`gpt-5.6-sol`/low. Planning, decomposition, architecture, plan validation and
grills use `gpt-5.6-sol`/high. Ordinary implementation, technical verification
and autoreview fixes use `gpt-5.6-sol`/medium. Formal autoreview and functional
checking use `gpt-5.6-sol`/high. Formal Lite uses `gpt-5.6-luna`/max. These
lanes continue to be selected by `harness.yaml`, `.codex/explore.config.toml`,
the `[agents]` defaults and named `.codex/agents/*.toml` profiles, and the
review launcher. No Forge-managed delegated or subagent lane may select Terra.

All remaining Decision 0070 contracts stay in force: First owns this bounded
model-policy correction and the complete 15-agent registry; init copies the
complete registry and root config; upgrade refreshes harness-owned same-name
profiles while preserving distinct client-added agents; Claude uses the same
plugin route; Luna/max doctor validation remains fail-closed; historical launch
evidence retains the model that produced it; and the amendments to Decisions
0031, 0057 and 0065 preserve their other lifecycle, graph and scope clauses.

## Consequences

First removes only the three root selector keys, aligns live guidance and
selector/distribution tests, and proves every Forge-owned lane is still pinned.
It amends and re-grills the active story and task contracts before delegation.
No launcher, copier, agent profile, harness selector, review selector, Lite
selector, migration mechanism or task-graph change is introduced.
