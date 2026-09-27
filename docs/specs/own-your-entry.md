---
slug: own-your-entry
title: Each Forge behaviour owns its own entry
status: draft
saved: 2026-09-27T16:42:06+00:00
---

# Each Forge behaviour owns its own entry

## Why

Forge is split into one module per behaviour, but three shared lists make every new feature wait
for the others. Every command adds a row to `src/forge/cli.py`'s command table; every shipped file
is listed in `src/forge/sync.py`; and every command gets a hand-written row in `docs/guide.md`'s
command table. On 2026-09-27 these three files queued most of the day's work: tasks that changed
different behaviours could not start together because each also needed one line in a shared file,
and Forge's rule that a task owns its files turned those lines into waits. When each behaviour
owns its own entry, tasks on different behaviours no longer share a file.

## Behaviour

**Commands declare themselves.** Each command's module declares, next to the function that runs
it, its command words, whether it changes state, its one-line help, its arguments, its position in
the command list and, for the command list page, its fuller description and example where it has
one today. A command group that spans modules (such as `spec`) declares its own help once, in the
module that owns the group's first command. `cli.py` collects the declarations from a fixed list
of Forge's modules, orders them by their declared position, and builds the parser from them; it
keeps no table of its own. `forge --help` and every command's help, usage and refusals read exactly
as before, and the contract test that reads the table today reads the declarations instead, keeping
its check of which commands change state.

**Modules list what they ship.** Each file `forge sync` writes is declared once, by the module
that owns it: the skill module for the Forge skill and its pages, the review module for the
test-audit skill, the approval module for the Remote Control skill, the hook module for the host
adapters and git hooks, and the init module for the CI workflow. A declaration is a path and a
function that renders the file's text for a repo, so merged files, the conditional `CLAUDE.md`,
repo-dependent CI text and template folders keep their rules. `sync.py` gathers the declarations
and writes them as today, and `doctor`, `init` and `migrate` read the same gathered list; `sync`'s
own list goes. `forge sync` writes the same files, byte for byte, as before.

**The command list is its own generated page.** The command table moves out of `docs/guide.md`
to `docs/commands.md`, which `forge sync` writes from the commands' declarations in today's table
format, and the guide links to it. A test fails when the page differs from what the declarations
produce and says to run `forge sync`. Nobody edits the page by hand, a task never lists it in its
Scope, and a merge conflict in it is settled by running `forge sync` again. The guide keeps its
hand-written prose.

**Nothing else changes.** No command, flag, refusal, generated file or behaviour changes. Big
modules are not broken up for size.

## Acceptance criteria

- `cli.py` holds no command table; every command's words, state flag, help and arguments are
  declared in its own module, and `forge --help` plus each command's `--help` output is unchanged.
- `sync.py` holds no list of shipped files; each shipping module declares its paths and sources,
  and `forge sync` writes the same files as before, byte for byte.
- The command list is `docs/commands.md`, written by `forge sync` from the declarations in
  today's table format, linked from the guide, and a test fails when it is stale.
- Adding a command or a shipped file changes only the module that owns it, its tests and the
  regenerated `docs/commands.md`, shown by a test that adds one in a fixture.
- The full test suite passes.

## Success measure

- Metric: tasks that wait on another task only because of a shared file in `src/forge/cli.py`,
  `src/forge/sync.py` or the command table.
- Baseline: most of the day's waits on 2026-09-27 (at least six tasks queued on these files).
- Target: none.
- Check date: 2026-12-15

## Out of scope

- Breaking up large modules (migrate, codex, story) for size.
- Changing any command, flag, refusal or generated file.
- Generating any part of the guide other than its command table.

## Roadmap

- FORGE-SPLIT-1: Each Forge behaviour owns its own entry
