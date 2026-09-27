---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "Ravi"
date: 2026-07-22
stories: []
---

# The vendored gate surface is frozen between vendorings

## Context

Every gate in the harness — schemas, recorders, verify, the ship gate, the
hooks — is vendored into client repos as editable files. An agent (or dev)
under delivery pressure can lower a score threshold, weaken `verify.py`, or
soften a prompt contract, and nothing notices: the gates would keep passing
while measuring nothing. An optimizing loop must never tune its own held-out
set. `constitution/VENDORED_FROM` already says "do not edit in place" — but
a rule nothing checks is not frozen, it is polite.

## Decision

`forge init`, `forge adopt`, and `forge upgrade` freeze the gate surface —
`.agents/scripts/**`, `.agents/schemas/**`, `.agents/prompts/**`, `forge`,
`.claude/settings.json` — into `constitution/VENDOR_MANIFEST.json`
(path → sha256). `check_vendor_integrity.py` compares; the SessionStart hook
warns on drift, and `pr_ready` REFUSES it: a tampered gate invalidates every
other gate's evidence, so this is the one audit finding that blocks a ship.
No manifest (a pre-manifest vendoring) is unarmed and advisory until the
next upgrade.

## Consequences

- Fix direction is always outward: re-vendor via `forge upgrade`, or
  upstream the change to the harness repo — never patch gate machinery in
  the client repo, even for a genuine harness bug.
- Client-owned surfaces stay tunable by design: `harness.yaml`,
  `.agents/skills/` (client-installed), `.claude/` additions, all project
  docs — the manifest deliberately excludes them.
- A legitimate mid-task `forge upgrade` rewrites the manifest with the new
  hashes, so upgrades never trip the gate; hand-added files under the gate
  surface do ("unexpected"), which is the point.
