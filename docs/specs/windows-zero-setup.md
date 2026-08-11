---
slug: windows-zero-setup
title: Windows is a first-class host: the harness self-heals, no user setup
status: confirmed
saved: 2026-08-10T20:01:06+00:00
---

# Windows is a first-class host: the harness self-heals, no user setup

> Captured 2026-08-11 from operator report: Windows client sessions degrade —
> Claude stops executing shell commands and asks the human to run them.
> Investigation traced it to harness breakage on Windows, not user error.
> Operator directive: users must never perform setup; the agent remediates
> for new AND existing clients, then continues.

## Why

Three concrete breakages compound on Windows:

1. **The write lock fails open.** Every hook in the vendored
   `.claude/settings.json` pins `/usr/bin/python3` — a path that does not
   exist on Windows (Git Bash ships no Python). SessionStart, PreToolUse and
   Stop hooks all fail; a non-2 hook exit is non-blocking in Claude Code, so
   the always-armed write lockout (strict-role-split) silently disarms, no
   session context loads, and the per-call hook error noise trains the model
   out of using the Bash tool — the reported "drops the shell command"
   symptom. The fail-open hole is latent on every platform; Windows merely
   exposes it.
2. **The entrypoint is sh-only.** `./forge` supports Git Bash, but without
   Git for Windows, Claude Code shells out via PowerShell where `./forge`
   cannot run at all — and Claude Code's own Bash tool requires Git Bash.
3. **Codex CLI native Windows is unstable.** Elevated-sandbox spawn
   failures (openai/codex #24098, #26158 — os error 740 /
   CreateProcessAsUserW), cmd/PowerShell command breakage (#2549, #12496).
   Known-good practice: `windows.sandbox="unelevated"` +
   `--sandbox workspace-write`.

## Behaviour

All four boundaries below were grilled and human-settled 2026-08-11.

- **Portable hooks.** Template hook commands resolve their interpreter at
  runtime (`python3`, falling back to `python`); no absolute interpreter
  path. One file, identical on macOS/Linux/Windows-Git-Bash, vendored to
  clients unchanged.
- **Fail-closed detectability.** Hook health is a named `forge doctor`
  check on every platform: doctor executes each hook command registered in
  `.claude/settings.json` exactly as Claude Code would; a hook that cannot
  run is a red check naming the fix — never silence.
- **Agent-handled remediation, zero user setup.** On Windows,
  `forge doctor --fix` detects and installs the missing toolchain (Git for
  Windows, Python ≥ 3.10) without user-typed setup. Anything the OS forces
  through elevation is batched into ONE consolidated UAC confirm — zero
  typed commands, one OS-forced click — never a manual checklist (grilled:
  honest reading of "zero setup").
- **Codex Windows config rides the delegation, not a global file.**
  `forge delegate` injects the pinned known-good flags
  (`windows.sandbox="unelevated"`, workspace-write) into its fixed argv on
  Windows. Repo-owned, applies to every run including upgraded old clients;
  the harness never mutates `~/.codex/config.toml` (grilled).
- **Both client classes, no manual steps.**
  - New clients: `forge init` / `forge adopt` run doctor remediation as part
    of the flow.
  - Existing clients: `forge upgrade` ships the fixed settings and doctor,
    then runs remediation. The vendor-integrity gate flags a stale pinned
    hook command, so an un-upgraded Windows clone is visibly red, not
    silently unlocked.
  - Because a broken client runs NO hooks, self-heal cannot ride a hook:
    `forge next` — the mandated first command, sh-runnable under Git Bash
    even with hooks dead — runs the fast hook-health check on Windows and
    prints `doctor --fix` as step 1; the agent continues automatically
    (grilled: skill instructions alone may never load when hooks are dead).
- **Windows behavior is machine-checked.** CI gains a `windows-latest` job
  running the lockout gate tests and the doctor hook-health check (grilled:
  without it, regressions ship and clients discover them).
- **WSL2 stays a documented escape hatch**, never a prerequisite.

## Acceptance criteria

- On a Windows host with Git Bash, every registered hook executes: session
  context loads, and `pre_tool_use.py` denies a product write exactly as on
  macOS/Linux (the lockout gate tests pass on Windows).
- `forge doctor` on any platform executes every registered hook command
  verbatim and reports a named red check when one cannot run.
- On a Windows host missing Git or Python, `forge doctor --fix` converges
  to green with no user-typed setup commands and at most one consolidated
  elevation confirm.
- On Windows, the recorded `forge delegate` invocation shows the injected
  sandbox flags; delegate either launches or refuses with a named reason —
  never a silent hang. `~/.codex/config.toml` is untouched.
- `forge next` on a hook-broken Windows clone names `doctor --fix` as its
  first action.
- CI runs the lockout gate tests and doctor hook-health on
  `windows-latest` green.
- `forge init`, `adopt`, and `upgrade` each leave a client repo
  hook-healthy on Windows; upgrading a pre-fix client replaces the
  pinned-interpreter settings file.
- `check_dual_runtime.py` and vendor integrity stay green.

## Boundaries

- No cmd/PowerShell port of `./forge`: Git Bash is the supported shell —
  Claude Code itself requires it for its Bash tool.
- WSL2 installation is out of scope (admin + reboot); documented
  alternative only.
- Codex CLI upstream bugs are not ours to fix; we pin known-good config
  and surface named failures.
- The harness never writes user-global files (`~/.codex/config.toml`
  included) — config rides the delegate argv.

## Decomposition (epic -> stories; split recorded 2026-08-11)

Planning exploration (Codex rescue) widened the known breakage: delegate.py
is POSIX-only (fcntl/ps/killpg), so the spec's single story split by the
independence rule, human-ruled at the FORGE-WIN-1 plan gate:

1. **FORGE-WIN-1 - the fail-open core**: one interpreter-resolution point
   for all hooks (fail-closed within a working shell), forge.cmd shim,
   doctor hook-health that EXECUTES hooks, windows-latest CI proof.
2. **FORGE-WIN-2 - prerequisites**: doctor --fix auto-install (Git/Python,
   at most one UAC); init/adopt/upgrade leave repos hook-healthy.
3. **FORGE-WIN-3 - delegation on native Windows**: cross-platform process
   machinery + injected sandbox flags.
4. **FORGE-WIN-SBX - sandboxed workers by default**: workspace-write
   default in vendored .codex/config.toml (found shipping
   danger-full-access), verified against a real delegation; hooks.json
   joins vendor-integrity hashing.
