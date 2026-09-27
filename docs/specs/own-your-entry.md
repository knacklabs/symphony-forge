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

**Commands declare themselves.** Each command's module declares its command words, whether it
changes state, its one-line help and its arguments, next to the function that runs it. `cli.py`
collects the declarations from Forge's modules and builds the parser from them; it keeps no table
of its own. `forge --help` and every command's help, usage and refusals read exactly as before.

**Modules list what they ship.** Each module that ships a file into a repo (the Forge skill, the
FDE guidance, the test-audit and Remote Control skills, the adapters, the hooks, the CI workflow)
declares the paths it writes and where each one's text comes from. `sync.py` gathers the
declarations and writes them as today; its own list goes. `forge sync` writes the same files,
byte for byte, as before.

**The guide's command table is generated.** `docs/guide.md` keeps its hand-written prose; its
command table sits between two marker comments and is written from the commands' declarations.
A test fails when the table between the markers differs from what the declarations produce, and
names the command to regenerate it. Nobody edits the table by hand.

**Nothing else changes.** No command, flag, refusal, generated file or behaviour changes. Big
modules are not broken up for size.

## Acceptance criteria

- `cli.py` holds no command table; every command's words, state flag, help and arguments are
  declared in its own module, and `forge --help` plus each command's `--help` output is unchanged.
- `sync.py` holds no list of shipped files; each shipping module declares its paths and sources,
  and `forge sync` writes the same files as before, byte for byte.
- `docs/guide.md`'s command table sits between markers, a named command rewrites it from the
  declarations, and a test fails when it is stale.
- Adding a command or a shipped file changes only the module that owns it (plus its tests), shown
  by a test that adds one in a fixture.
- The full test suite passes.

## Success measure

- Metric: tasks that wait on another task only because of a shared file in `src/forge/cli.py`,
  `src/forge/sync.py` or `docs/guide.md`'s command table.
- Baseline: most of the day's waits on 2026-09-27 (at least six tasks queued on these files).
- Target: none.
- Check date: 2026-12-15

## Out of scope

- Breaking up large modules (migrate, codex, story) for size.
- Changing any command, flag, refusal or generated file.
- Generating any part of the guide other than its command table.

## Roadmap

- FORGE-SPLIT-1: Each Forge behaviour owns its own entry
