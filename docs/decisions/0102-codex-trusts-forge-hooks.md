---
status: proposed
confirmed_by: ""
date: 2026-10-02
stories: []
supersedes: "0082-codex-hook-trust-boundary"
---

# Forge trusts its own Codex hooks for each turn it starts

## Context

Codex runs a project hook only once the user has trusted it in Codex's /hooks, and any change to a
hook's definition makes it untrusted again. Codex skips an untrusted hook without a word. When
forge sync changed the hook launcher, every Forge hook in `.codex/hooks.json` became untrusted, so
Forge's Codex workers and readers ran with no Forge hooks at all, the destructive-command guard
included. Decision 0082 left that trust to the user's own review of the hook's hash.

## Decision

Before each Codex thread start or resume, Forge asks the app-server for the checkout's project
hooks. Each untrusted one whose whole definition (every field but where Codex found it, Codex's
defaults for what forge sync leaves out included) is exactly what forge sync writes is trusted for
that thread only, by passing its current hash in the
thread's `hooks.state` config. If any other project hook is untrusted, Forge starts no turn and
names the hook in one line, so the user reviews it in Codex's /hooks. Forge never writes the trust to the
user's Codex config. The owner chose this on 2026-10-02. It supersedes 0082 for Forge's own hooks.

## Consequences

- The guard and Forge's other hooks run on every Codex worker and reader turn, whatever the user's
  /hooks shows.
- A changed or new project hook that isn't Forge's still needs the user's review, and stops Forge's
  Codex turns until it gets one.
- The approval recorder's own checks from 0082 stand: the exact plan digest, the session and tool
  identity, replay refusal and one candidate. Forge still claims no signed host provenance.
- Interactive Codex sessions outside Forge still follow the user's own /hooks trust.
