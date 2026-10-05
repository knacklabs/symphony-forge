---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
date: 2026-10-05
stories: [FORGE-LANES-1]
supersedes: ""
---

# Stop a run with one person-only command

## Context

The machine lanes need one way for a person, including the Claude Code mod's confirmed stop
key, to cancel a waiting run or end a running process tree safely.

## Decision

Add `forge stop <item>` with optional `--repo <root>`, and `forge stop --id <id>` for one entry.
Raise the command ceiling from 21 to 22. The coordinator requested this on 2026-10-05.
There is no separate lanes command: `forge board --json` carries the machine-wide lane entries.
Forge-started agents cannot run stop; the host must ask its person first.

## Consequences

New and upgraded client repos receive the command and its synced guidance. Existing settings
stay unchanged. Stopping checks recorded process identity before terminating a tree; unknown
identity refuses without signalling any selected entry.
