# Degraded Mode

`forge delegate` is the normal validation and brief boundary for product and
canon writes. Under Claude it launches the protected `codex-plugin-cc`
companion. Under native Codex it records the prepared task, worktree, and
effective-scope binding and returns dispatch information for a configured host role; a
narrowed scope is recorded in that preparation row. Native close requires this
prepared binding but no launch-process proof.

Raw, direct, or nested `codex exec` and direct plugin shell launches are
off-contract and hook-denied for general or manual delegation in both runtimes.
Forge-managed autoreview is an authenticated external black box and may invoke
Codex or agents internally; this ban does not constrain that helper. Native
writes still require the approved plan, active stage, matching worktree, and
effective scope, without a PID, session, token, foreground, status, cancel,
resume, or background lock.

Repair the Claude delegated-writer path first. `codex-plugin-cc` can be repaired
with:

```bash
./forge doctor --fix
```

Claude read-only discovery remains available through `/codex:rescue`. Native
Codex uses host role subagents without installing or launching Claude. The
companion guard may admit its documented read-only diagnostic invocations, but
no direct shell invocation becomes an implementation route.

## Claude companion outage exception

If the Claude plugin path remains broken and product work cannot wait,
explicitly open a degraded window with a reason:

```bash
./forge mode degraded start --reason "delegated writer outage blocks the active task"
```

The window is recorded on the quickfix ledger with `kind: degraded`. It may
claim at most five distinct locked files toward its budget. Test files (under a
`test` or `tests` path segment, or named `test_*.py`, `*_test.py`, `*.test.*`,
or `*.spec.*`) and `*.md` files are still recorded but do not use a slot. Each
direct Edit, Write, NotebookEdit, or recognized Bash write claims its locked
target before the tool runs; a sixth budget-counted file is denied. Recursive
or globbed operations whose file set cannot be bounded are denied. The
repository-kind marker is never eligible. The separate degraded stage-close
fallback still requires no more than five total in-scope files, including test
and Markdown files.
`docs/`, `plans/`, `prototype/`, `.gstack/`,
recorders, scratchpad, and git operations keep their normal routing.

The window is a Claude plugin outage valve, not approval or a second
implementation mode. Native Codex does not use this valve for ordinary host
subagent delivery.

Keep the active task scope, tests, verification, and review contract unchanged.
Close it as soon as the bounded work is complete:

```bash
./forge mode done
```

`mode done` writes the claimed files to the ledger's done record and removes
the active window. Declare its `Q-...` id in the PR body (`Ticket: Q-...`).
Gate A still requires every completed story and window record in the PR to be
declared; the degraded record gets no special exemption.

Restore the Claude plugin path and return to `./forge delegate <task-id>` for
any remaining protected write.

## PR-link fallback when CI is unavailable

Gate B normally links a completed story to its pull request automatically
through `.github/workflows/pr-link.yml`. Use the manual command only when that
workflow cannot run:

```bash
./forge pr-link <STORY> <PR-REFERENCE>
```

This is a CI-unavailable fallback, not the normal PR-linking path.
