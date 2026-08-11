---
status: proposed
confirmed_by: ""
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

Registered hook commands must be host-portable — PATH-resolved interpreter
(`"$(command -v python3 || command -v python)"`), sh-compatible, preserving
the literal `factory/scripts/<name>.py` token — and their executability must
be machine-proven: `forge doctor` executes every registered hook command
verbatim on every platform, and a hook that cannot run is a named red check,
never silence. A fast, subprocess-free resolution check backs the
`forge next` Windows preflight.

## Consequences

- Rejected: pinned absolute interpreter (today's defect); a committed shim
  script or `forge hook` subcommand (both drop the literal script token that
  `check_dual_runtime.check_hook_registration` keys its protection on);
  `$CLAUDE_PROJECT_DIR` (ambiguous across worktrees vs `git rev-parse`).
- Accepted residue: the one-substitution chain has no `py -3` leg and no
  version gate; doctor's verbatim-execution check plus `doctor --fix`
  (real Python on PATH) own that residue.
- `.codex/hooks.json` stays outside vendor-integrity `GATE_FILES` for now —
  adding it changes the client gate surface, a separate decision if wanted;
  its health is covered by the doctor check instead.
- Any future hook must ship in the portable form; doctor red is the tripwire
  for regressions.
