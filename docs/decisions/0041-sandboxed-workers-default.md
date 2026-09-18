---
status: superseded
confirmed_by: "Ravi (vrknetha)"
date: 2026-08-13
stories: [FORGE-WIN-SBX]
superseded_by: 0081-full-access-for-forge-managed-codex-chats
---

# Sandboxed Workers Default

## Context

The vendored `.codex/config.toml` shipped `sandbox_mode =
"danger-full-access"` to every client, granting full machine access to
any Codex session run against the repo config. The delegation path was
already safer than the config implied: `forge delegate` passes no
sandbox flag, and the installed companion hardcodes `--write` →
`workspace-write` with read-only as the thread default — so the
dangerous default was a dormant liability in the vendored surface, not
live delegation behavior. Separately, `.codex/hooks.json` — the
fail-closed hook wiring decision 0038 armed — was not part of the
frozen vendor surface, so a client edit disarming a vendored hook was
invisible to the 0009 integrity audit.

## Decision

The vendored sandbox default is `workspace-write`, and
`.codex/hooks.json` joins the hashed vendor surface. `config.toml` is
deliberately NOT hashed: a client needing genuinely broader access
edits it knowingly — that diff-visible, history-recorded edit is the
ledgered escape hatch, and every `forge upgrade` restores the safe
default. Per-task sandbox escalation through `forge delegate` is
deferred until the companion grows a sandbox override flag (it accepts
only `--write` today).

## Consequences

- Clients receive the safer default and the hooks freeze on their next
  upgrade; pre-existing hooks.json customizations will fail vendor
  integrity by design — re-vendor or upstream the change.
- This flip does not change delegated-worker behavior (already
  workspace-write via the companion mapping); reading it as having
  closed a live delegation hole would be wrong, and this record exists
  partly to prevent that reading.
- Enforcement of the escape hatch is visibility, not prevention — the
  same drift-defense ceiling as 0030, not an adversarial sandbox.
- Deferral: sandbox-exception plumbing through `launch_companion()`
  with mode + rationale in the protected delegation record, when the
  companion supports it.
