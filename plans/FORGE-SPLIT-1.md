# Each Forge behaviour owns its own entry

## What changes for you

- Forge's own work stops queueing: two changes to different behaviours no longer wait on each
  other just because both add a line to the same shared file.
- The command list moves to its own page, `docs/commands.md`, kept up to date by Forge itself; the
  guide links to it.
- Nothing you run changes: every command, its help, its messages and the files Forge writes into
  your repos stay exactly as they are.

## Why

On 2026-09-27 most of the day's waits came from three shared lists: the command table in
`cli.py`, the list of shipped files in `sync.py`, and the guide's command table. This story builds
the confirmed spec `docs/specs/own-your-entry.md`.

## Done when

1. `docs/specs/own-your-entry.md` is confirmed by the owner and on the roadmap as FORGE-SPLIT-1.
2. `cli.py` holds no command table: each command's words, state flag, help, arguments, position
   and command-list description are declared in its own module, a group spanning modules declares
   its help once, and `forge --help` plus every command's `--help` output is unchanged; the
   contract test reads the declarations and still checks which commands change state.
3. `sync.py` holds no list of shipped files: each file `forge sync` writes is declared once by its
   owning module as a path and a render function, `doctor`, `init` and `migrate` read the same
   gathered list, and `forge sync` writes the same files as before, byte for byte.
4. `docs/commands.md` is written by `forge sync` from the declarations in today's table format,
   the guide links to it instead of carrying the table, and a test fails when the page is stale
   and says to run `forge sync`.
5. Adding a command or a shipped file changes only its owning module, its tests and the
   regenerated `docs/commands.md`, shown by a test that adds one of each in a fixture; the full
   test suite passes.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| A-FEW-SHARED-FILES-THE-COMMAND-TABLE-THE | The spec | The confirmed spec and its roadmap item | 1 | `docs/specs/own-your-entry.md`, `docs/specs/own-your-entry.read.md`, `plans/roadmap.json` | | none | no |
| COMMANDS | Commands declare themselves | The declaration format and collector, every command's declaration moved into its module, and the contract test reading declarations | 2 | `src/forge/cli.py`, `src/forge/approval.py`, `src/forge/ask.py`, `src/forge/board.py`, `src/forge/close.py`, `src/forge/deny.py`, `src/forge/doctor.py`, `src/forge/githooks.py`, `src/forge/init.py`, `src/forge/migrate.py`, `src/forge/nextstep.py`, `src/forge/payback.py`, `src/forge/prcheck.py`, `src/forge/records.py`, `src/forge/story.py`, `src/forge/sync.py`, `src/forge/task.py`, `src/forge/worker.py`, `tests/test_contracts.py` | `tests/test_split_commands.py` | none | no |
| SHIPS | Modules list what they ship | The shipped-file declaration format, each file declared by its owning module, `sync` gathering them, and `doctor`, `init` and `migrate` reading the gathered list | 3 | `src/forge/sync.py`, `src/forge/doctor.py`, `src/forge/init.py`, `src/forge/migrate.py`, `src/forge/review.py`, `src/forge/approval.py`, `src/forge/githooks.py` | `tests/test_split_ships.py` | COMMANDS | no |
| PAGE | The command list page | `docs/commands.md` written by `forge sync`, the guide's link replacing its table, the staleness test, and the fixture test adding a command and a shipped file | 4, 5 | `src/forge/sync.py`, `docs/commands.md`, `docs/guide.md`, `tests/test_standards.py` | `tests/test_split_page.py` | SHIPS | yes |

New moving parts: none

## Risks

Risks: none

## Notes

- COMMANDS runs alone: it touches every command module. It starts after the in-flight tasks that
  change those modules have merged (FORGE-TRIM-1, FORGE-MERGE-1/READY, FORGE-STEER-1's open tasks,
  FORGE-ONECHAT-1/REGISTRY); Forge's Scope overlap rule enforces the order.
- COMMANDS pins the names: a module-level `COMMANDS` list of declarations with `words`, `run`,
  `changes_state`, `help`, `args`, `position` and `listing`, and a `GROUP_HELP` mapping in the
  module that owns a group's first command; `cli.py` imports a fixed tuple of module names.
- SHIPS pins a module-level `SHIPS` list of `(path, render)` pairs, where `render(top, cfg)`
  returns the file's text; `sync.files` becomes the gathering of every module's `SHIPS`.
- Each test file starts with `STORY = "FORGE-SPLIT-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
