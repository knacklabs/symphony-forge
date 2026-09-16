# Windows support

## Supported native path

Use Windows with Git for Windows (including Git Bash) and Python 3.10 or
newer. From Command Prompt or PowerShell, `forge.cmd` is the entry point. It
checks `py -3`, `python`, then `python3` for a supported interpreter before
handing off to Git Bash; when Git Bash is unavailable, it runs Forge with the
interpreter it found.

## Remediation

If no suitable Python is available, `forge.cmd` uses winget from its canonical
WindowsApps location to install Python in user scope, refreshes PATH from the
known per-user install location, and retries once. `forge init`, `forge adopt`,
and `forge upgrade` also run the fast hook check on Windows. When it is red,
they run the same user-scope prerequisite remediation and print a named
`doctor --fix` or manual-installer step if the check remains red.

Forge never launches an elevated process with `RunAs`. A package installer
may show its own Windows prompt. If winget or a prerequisite cannot complete
in user scope, install Git for Windows or Python from the URL printed in the
red row and rerun the command.

## Delegation

Native Windows delegation is supported. `forge delegate` launches, supervises,
and reaps the Codex worker tree on Windows. Forge-managed native Codex chats
and committed agent profiles use `danger-full-access`; write capability still
comes from the active Forge stage, scope, admission, and hooks rather than the
OS sandbox policy.

An explicitly unelevated sandbox is deferred. The companion does not expose an
unelevated sandbox option, and Forge does not change user-global Codex
configuration to simulate one. Run Forge from a normal, unelevated prompt.

Full access avoids the Codex sandbox account and its process-discovery,
psutil, sysctl, profile, and per-user-cache boundaries for trusted
Forge-managed native chats. Forge does not treat host access as task authority:
the lifecycle, hooks, write scope, worker admission, proof, and review gates
still enforce what the chat may do.

The official Claude `codex-plugin-cc` 1.0.6 route still hardcodes its own
workspace-write/read-only app-server policies. Upstream PR 742 is unreleased
and task-only; do not patch installed plugin files or claim that route is fixed.

## Encoding

Forge repository text and machine-consumed text use explicit UTF-8 on every
I/O boundary. Diagnostic output may replace undecodable bytes so a status or
doctor command can still explain the failure; evidence and canonical records
decode strictly, and byte-exact paths remain bytes. This convention is recorded
in decision 0043 and enforced by `check_encoding_hygiene.py`.

Deferral D-0026 parks the same sweep for inline Python in the roadmap-gate and
PR-link workflows until a gate log shows mojibake or a decode failure, or a new
inline workflow parser is added. Those snippets are outside the harness-script
surface enforced by the current checker.

## WSL2 escape hatch

WSL2 is optional, not a prerequisite. Use it as an escape hatch when policy or
machine configuration prevents the supported native Windows path from
converging; inside WSL2, follow the normal Linux setup.

## Review lenses read the worktree

`forge review` starts each lens inside the review worktree, read-only, through
a launcher that also carries `[windows] sandbox = "elevated"` and the real
`CODEX_HOME` past the skill's isolation (decision 0076). It needs the elevated
sandbox set up once on the machine (the `.sandbox` folders under
`~/.codex`); until then the lens's shell commands fail with "blocked by
policy" or error 1223, and the fix is to run one interactive Codex session
with the sandbox enabled so it completes set-up. Each run appends the exact
Codex command it started to `.git/forge/review-launcher/<task>/bin/launch.log`.
