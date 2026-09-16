---
status: accepted
confirmed_by: "Nandu (chat, 2026-09-12)"
date: 2026-09-12
stories: []
---

# The worker's commands may reach the network

## Context

Decision 0041 set the worker's mode to `workspace-write`, which confines its
writes to the worktree. Codex's default for that mode also switches network off
for every command the worker runs, and nothing in this repo ever chose that:
the key was never set, discussed or recorded. The Codex process itself keeps
its connection to the model; only the shell commands it launches lose theirs.

On WF-1 T2 and T3 (20 delegate runs, 9-11 September) the worker ran 180
verification commands; 41 died on the environment rather than the code. It
could not install the packages a task declared (`pdf-lib`, `qrcode`), could not
reach the local PostgreSQL, and reported the tests it wrote as "host verification
remains required" in every run. Eleven of the forty signals it raised were
this block. The human then ran the tests, and the fix loop paid a round trip
per finding. On Windows the offline sandbox account is denied all outbound
traffic AND loopback by firewall rules, so a database on 127.0.0.1 is as
unreachable as the registry.

## Decision

`[sandbox_workspace_write] network_access = true` in the vendored
`.codex/config.toml`. The worker's commands may reach the network; its writes
stay confined to the worktree exactly as 0041 set them. The rule that a worker
must say what it could not verify is unchanged.

## Consequences

- A task can install what it declares, run its own DB-backed tests and hand the
  human a verified diff instead of a promise. The host-exception window remains
  for what the environment still cannot do (Docker, a folder the sandbox account
  cannot read).
- Network is the one boundary this loosens. Writes, approvals (`never`) and the
  brief's contract are untouched. A client wanting the old behaviour edits the
  value knowingly, as 0041 already provides; `forge upgrade` restores this one.
- The file is vendored whole, so clients receive it on their next upgrade. The
  setting applies only to workspace-write threads: read-only runs (grill,
  review, exploration) stay offline.
- Windows: the per-user caches (`%LOCALAPPDATA%\node\corepack`,
  `%LOCALAPPDATA%\pnpm\store`) and the profile root are still unreadable to
  the sandbox account. That is an OS ACL, not a Codex setting, and is documented
  in `docs/windows.md` rather than changed here.
