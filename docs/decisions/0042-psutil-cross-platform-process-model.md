---
status: superseded
superseded_by: 0093-lean-forge-rebuild
confirmed_by: "Ravi"
date: 2026-08-13
stories: [FORGE-WIN-3]
---

# Psutil Cross Platform Process Model

## Context

`forge delegate` — the sole sanctioned write path (0037) — supervises Codex
workers with a POSIX-only process model: `subprocess.Popen(start_new_session=
True, preexec_fn=…)`, process discovery by shelling out to `ps` (`_process_
table`, `_process_start_identity`, `_process_is_zombie`, `_tagged_processes`),
and tree termination by `os.killpg`. None of this exists on Windows, so
delegation cannot launch or reap a worker there. The `ps -o lstart=` identity
comparison is also fragile on POSIX: it once went red for nine days a month
because `ps` pads the day-of-month and two code paths normalized whitespace
differently (lesson `normalize-ps-derived-identity`). The harness is currently
pure stdlib + node with no cross-platform process abstraction.

AC2 as written ("injected sandbox flags unelevated, workspace-write on
Windows") is only half-achievable: the installed companion's `task` verb has
no sandbox/config passthrough; `--write` already selects `workspace-write`
internally, and no "unelevated" concept exists in the companion. Driving
`~/.codex/config.toml` is forbidden by 0040.

## Decision

psutil is the harness's cross-platform process abstraction. The `ps`-shelling
and `os.killpg` are replaced on BOTH platforms — not merely Windows-branched —
with `psutil.Process.children(recursive=True)`, `create_time()`/`status()`
identity, and `terminate()`/`kill()` tree teardown. On Windows the companion
is launched with `creationflags=CREATE_NEW_PROCESS_GROUP`; on POSIX
`start_new_session=True` is kept; `preexec_fn` is dropped. This retires the
ps-lstart fragility entirely (create_time is a float, no whitespace parsing).
psutil is the first runtime Python dependency in the harness: `forge doctor`
gates its presence with a required, honest red row and `doctor --fix` installs
it; it vendors to every client through the machinery. AC2 is narrowed to its
achievable half — assert the recorded invocation carries `--write`
(→ workspace-write); the unelevated/config-level tightening stays deferred
(D-0021).

## Consequences

- Rejected: per-function `os.name` branching (two code paths across ~9
  functions, subtle Windows process-tree logic, and it keeps the ps-lstart
  fragility on POSIX); Windows-only job objects via ctypes (more native code,
  no POSIX simplification, no fragility retirement).
- Accepted: a runtime dependency footprint the harness did not previously
  have. Mitigated by doctor's presence gate + `--fix` install and the WIN-2
  init/adopt/upgrade propagation tests confirming the dep manifest ships.
- POSIX behavior stays byte-identical in observable terms (launch, supervise,
  reap, lock release); the ps-monkeypatch unit tests migrate to psutil fakes.
- The unelevated sandbox remains unshipped and deferred (D-0021), consistent
  with 0040's no-user-global-config boundary.
