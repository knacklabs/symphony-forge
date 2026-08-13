---
status: accepted
confirmed_by: "Ravi"
date: 2026-08-12
stories: [FORGE-WIN-2]
supersedes: 0039-windows-remediation-via-winget
---

# Windows User-Scope-First; Orchestrated Elevation Deferred

## Context

Decision 0039 committed `doctor --fix` to a harness-orchestrated single
elevated PowerShell batch (`Start-Process -Verb RunAs` running winget) as the
one sanctioned elevation. Implementing it triggered the same class of
autoreview finding four times (WIN-2.1 review rounds 3, 4, 6, 8): every
mechanism for the elevated process to locate a trusted winget was refuted —
PATH-selected binary, per-user WindowsApps alias (TOCTOU), machine-dir
enumeration (unlistable unelevated), and finally an elevated PowerShell that
still inherits the caller's user-controllable PATH. The irreducible problem:
an auto-elevated process that must resolve a winget binary living in a
user-writable location, while inheriting a user-controllable environment,
is a local privilege-escalation surface that cannot be closed by blind
iteration — only real-Windows validation can settle the elevation-boundary
semantics. Decision 0005 forbids a fourth patch to a recurring class.

## Decision

`doctor --fix` on Windows installs prerequisites in USER SCOPE only:
`winget install --scope user --source winget --silent
--accept-package-agreements --accept-source-agreements`, run as the user with
no privilege gain and no harness-orchestrated `RunAs`. A package whose own
installer self-elevates raises the OS's own single UAC prompt — that honest,
OS-driven prompt is the "at most one UAC confirm" the spec allows, not a
harness-built elevation. Git.Git's installer is known to self-elevate even
with `--scope user`; declining or failing that installer-owned prompt produces
a named red Git row with the manual installer URL, never a crash or a false
success claim. On every return path, `doctor` refreshes PATH from the
canonical known-folder identity used to locate winget. For installed tools it
collects every available native and x86 Program Files source:
`ProgramW6432`, `ProgramFiles`, `ProgramFiles(x86)`,
`FOLDERID_ProgramFiles`, and `FOLDERID_ProgramFilesX86`; nonexistent
directories are ignored. These environment values are safe here because PATH
candidate discovery is unelevated and is not an installer trust boundary. It
then re-probes the tools. That probe is authoritative: a usable tool suppresses
a provisional winget error such as "already installed" or "no applicable
upgrade". When a user-scope install genuinely cannot complete, `doctor` prints
a named red row with the manual installer URL. The
harness-orchestrated elevation batch is DEFERRED (D-0021) to be built and
validated against a real Windows environment.

## Consequences

- Everything in WIN-2.1 is now CI-verifiable: no `RunAs` to fake, no
  elevation-boundary trust to assert blind. The user-scope path, winget-absent
  red row, and same-run PATH-refresh convergence are the whole testable
  surface.
- Honest limitation, stated in docs/windows.md: on a machine where a
  prerequisite truly requires machine-scope admin install and winget cannot
  self-elevate it, remediation stops at a named manual step rather than
  driving elevation itself — until D-0021 lands the validated batch.
- 0039's winget-only, no-bundled-download, no-user-global-config,
  Python.Python.3.14 (per A-0010) decisions all carry forward unchanged;
  only the orchestrated-elevation mechanism is withdrawn and deferred.
