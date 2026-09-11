---
status: accepted
confirmed_by: "User (explicit CI-only Linux/Windows ruling, Codex conversation 2026-09-10)"
date: 2026-09-10
stories: [FORGE-COORD-1]
---


# CI evidence for unavailable native platforms

## Context
On 10 September 2026 the user confirmed that no Linux or Windows computers
are available and directed Forge to rely on CI for those platforms. The
available Mac continues to supply local observations.

## Decision
Amend only Decision 0064's six-live-cell acceptance condition and its
platform-proof-substitution restriction. Require real local macOS native CLI
and Desktop observations plus passing Ubuntu 24.04 x64 and native Windows
CI regressions. Preserve the existing full suite and native Windows gates;
exercise launcher, admission, hooks, recovery and portable delivery on the
actual runner OS. Install an explicitly pinned real Codex CLI package and
record version/help smoke results. An authenticated runtime exercise uses
only existing authorized CI authentication, when available.

CI proves only the commands and behavior it executes. Package/help smoke
and harness subprocess tests do not certify an authenticated task or Desktop
interaction. Keep all six platform observation labels and clearly state the
kind of evidence, exact tested revision, runner/runtime versions, commands,
logs and unavailable live observations. Unavailable Linux/Windows live
CLI/Desktop observations are accepted limitations and do not block this
CI-backed delivery. WSL cannot satisfy native Windows. Observed failures,
missing required CI results and missing required local Mac proof still block.

Use the existing implementer automated-test report and recorder. Required
results must pass before normal readiness, review, markers, shipping and
closeout. State accepted limitations in remaining_gaps; put failures and
missing required evidence in both remaining_gaps and blocking_findings.
A passing aggregate may include only the explicitly accepted unavailable
observations, never a suppressed failure or an unrun check presented as passed.

## Consequences
All other 0064 rules remain active. Preserve the eight-task graph, the first
native task's existing write scope and source/target transition, full quality,
real local Mac probe, independent review, separate Task tracker lifecycle,
client migrations and normal PR/CI. No new computers, credential export,
fabricated event, matrix schema, registry or bootstrap exception is authorized.
Later live observations may extend evidence through the normal task route.
