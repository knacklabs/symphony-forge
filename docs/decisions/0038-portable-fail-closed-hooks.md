---
status: accepted
confirmed_by: "Ravi"
date: 2026-08-11
stories: [FORGE-WIN-1]
---

# Portable Fail Closed Hooks

## Context

Every hook command vendored in `.claude/settings.json` and `.codex/hooks.json`
pinned `/usr/bin/python3` — a path that exists on macOS/Linux but never on
Windows (Git Bash ships no Python). A hook whose command cannot spawn exits
non-2, which Claude Code treats as non-blocking: on Windows the always-armed
write lockout (0037) silently disarmed, session context never loaded, and
per-call hook errors drove sessions to stop using the Bash tool. Nothing in
the gate tests could see it — they invoke hook scripts via `sys.executable`,
never the registered command string. The fail-open hole is latent on every
platform; Windows merely exposed it.

## Decision

Registered hooks route through one shared `forge hook <name>` entrypoint. The
`forge` launcher owns interpreter resolution in the fixed `py -3` → `python3`
→ `python` order and exits 2 when no supported interpreter resolves. That
blocking exit is deliberate: resolution failure must never become an exit-127
fail-open hole. Every registered command has the double guard
`sh -c '"$(git rev-parse --show-toplevel)/forge" hook <name> || exit 2' || exit 2`.
The inner guard preserves success and a genuine hook exit 2 while normalizing
a missing launcher, missing entrypoint, or any other nonzero launch result.
The outer guard closes the earlier spawn boundary when `sh` itself is missing
or cannot run, so that failure also becomes blocking exit 2.

The hook name maps deterministically to `factory/scripts/<name>.py` in the
entrypoint. `check_dual_runtime.check_hook_registration` understands that
mapping and still proves every registered script exists; the passthrough does
not trade away token or extraction protection.

Executability is machine-proven: `forge doctor` executes every registered hook
command verbatim on every platform with `FACTORY_HOOK_HEALTH=1`, bytecode
writes disabled, and a read-only-shaped payload. Hooks that otherwise write
for every payload must return successfully before that write while health mode
is set. A hook that cannot run is a named red check, never silence. A fast,
subprocess-free prerequisite check makes `forge next` name doctor first when
the hook launcher is broken.

## Consequences

- Rejected: pinned absolute interpreter (the original defect).
- Rejected: inline `command -v python3 || command -v python`. When neither
  command resolves, the shell attempts an empty command and returns 127;
  Claude Code treats that non-2 exit as non-blocking, recreating the fail-open
  defect. It also omits Windows' standard `py -3` launcher.
- Rejected: `$CLAUDE_PROJECT_DIR` (ambiguous across worktrees vs
  `git rev-parse`).
- Accepted: `forge.cmd` is the native cmd/PowerShell entrance. It discovers
  Git Bash through `CLAUDE_CODE_GIT_BASH_PATH`, `PATH`, and the standard
  Git-for-Windows install locations, and only prefers a candidate after proving
  it can execute the shared `forge` launcher. An incompatible shell such as WSL
  falls through to the native chain. It then probes `py -3` and `python` for
  Python 3.10+ before bootstrapping `forge.py`, falling through whenever a
  candidate fails its probe. Hook interpreter policy remains owned by the
  `forge` entrypoint.
- `.codex/hooks.json` stays outside vendor-integrity `GATE_FILES` for now —
  adding it changes the client gate surface, a separate decision if wanted;
  its health is covered by the doctor check instead.
- Any future hook must ship in the portable form; doctor red is the tripwire
  for regressions.
