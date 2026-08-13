---
status: superseded
confirmed_by: ""
date: 2026-08-12
stories: [FORGE-WIN-2]
superseded_by: 0040-windows-user-scope-first-elevation-deferred
---

# Windows Remediation Via Winget

## Context

The zero-setup spec obliges `forge doctor --fix` to install Git for Windows
and Python ≥ 3.10 on a bare Windows machine with no user-typed commands and
at most ONE consolidated UAC confirm (spec grill, 2026-08-11). Doctor's
existing installers are all user-scope and never elevate; the only
privilege-escalation precedent in the codebase is `_install_direnv_linux`'s
per-command sudo — exactly the per-package prompting the settlement forbids.
The direnv Windows installer downloads a single static binary via urllib;
Git and Python are full installers with dependencies, signatures, and update
cadence that pattern cannot carry safely.

## Decision

winget is the sole installer for Windows prerequisites. `--fix` attempts
user-scope installs first when the package manifest does not self-elevate
(`winget install --scope user --silent
--accept-package-agreements --accept-source-agreements`, no prompt at all);
only when the OS or policy refuses user scope does it fall back to ONE
elevated PowerShell invocation (`Start-Process -Verb RunAs`) whose argument
list carries every pending install — a single UAC confirm per doctor run,
never per package. winget absent (LTSC/Server/old images) is a named
required red row carrying the manual installer URLs. Installs run via
direct `subprocess.run` with an installer-scale timeout, not `run_quiet`
(hardcoded 15s, ~15 shared call sites).

The elevated invocation starts one administrator PowerShell process. That
process resolves `winget` by name from its own elevated context and runs the
fixed, allowlisted package IDs sequentially; package IDs are never built from
user input. The unelevated parent never enumerates the protected Program
Files\WindowsApps package directory and never selects or passes a winget
binary across the UAC boundary. It requests machine scope and attempts every
queued package, returning failure if any install failed. Known user-scope
refusals are classified by winget exit code, never localized output. An
unknown non-zero exit is ambiguous and joins the same single batch; this
preserves the one-confirm ceiling without treating English diagnostic text as
control flow. Launch errors and timeouts do not start a second installer.

User-scope installs may use the per-user WindowsApps APPEXECLINK alias, trusted
by canonical location without resolving its reparse point. The elevated path
never passes that user-writable alias: the only executable path crossing the
boundary is PowerShell from the `GetSystemDirectory` System32 path. The
already-elevated PowerShell resolves machine-wide winget by bare name from its
administrator PATH. Every install pins `--source winget`, preventing
configured or corporate sources from shadowing the allowlisted package IDs. A
known-scope table sends manifests that self-elevate — `Git.Git` today —
directly to the consolidated elevated batch. Python uses the current
security-patched `Python.Python.3.14` manifest (3.14.7 verified in the winget
repository on 2026-08-12) and tries user scope first. PowerShell's rethrown
`InvalidOperationException` takes the wrapper's fixed cancellation exit,
other launch exceptions take a generic failure exit, and child installer
failures use the child's exit code. Classification is type/control-flow based
and locale-independent, and a cancelled prompt is never retried.

## Consequences

- Rejected: bundled urllib installer downloads (attack and maintenance
  surface — the direnv single-binary precedent does not scale to full
  installers); per-package elevation (the linux sudo shape); elevating
  when user scope suffices for a non-self-elevating manifest; any winget
  policy-evasion on managed machines.
- The one-confirm invariant is machine-proven by argv-recording fakes
  (exactly one elevation-shaped invocation, both package ids); the real
  UAC path is proven once on the affected client's machine as functional
  evidence — CI runners are already admin and cannot exercise it.
- Convergence is same-run: after installs, doctor refreshes the process
  PATH with known install locations and re-probes, so the run that fixed
  the machine is the run that reports green.
