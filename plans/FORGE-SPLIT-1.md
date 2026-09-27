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
| COLLECTOR | Commands declare themselves | The declaration format, the collector that discovers every module's declarations, the contract test reading them, and the first modules' commands moved: init, sync, doctor, migrate, nextstep, board | 2 | `src/forge/cli.py`, `src/forge/init.py`, `src/forge/sync.py`, `src/forge/doctor.py`, `src/forge/migrate.py`, `src/forge/nextstep.py`, `src/forge/board.py`, `tests/test_contracts.py` | `tests/test_split_commands.py` | none | no |
| COMMANDS | The rest of the commands | Every remaining command's declaration moved into its module and the table removed from `cli.py` | 2 | `src/forge/cli.py`, `src/forge/approval.py`, `src/forge/ask.py`, `src/forge/close.py`, `src/forge/deny.py`, `src/forge/githooks.py`, `src/forge/payback.py`, `src/forge/prcheck.py`, `src/forge/records.py`, `src/forge/story.py`, `src/forge/task.py`, `src/forge/worker.py` | `tests/test_split_commands_rest.py` | COLLECTOR | no |
| SHIPS | Modules list what they ship | The shipped-file declaration format, each shipped file declared by its owning module, and `sync.files` gathering them | 3 | `src/forge/sync.py`, `src/forge/story.py`, `src/forge/review.py`, `src/forge/approval.py`, `src/forge/githooks.py`, `src/forge/prcheck.py` | `tests/test_split_ships.py` | COMMANDS | no |
| PAGE | The command list page | `docs/commands.md` written by `forge sync` in Forge's own repo, the guide's link replacing its table, the staleness test, and the fixture test adding a command and a shipped file in new modules | 4, 5 | `src/forge/sync.py`, `docs/commands.md`, `docs/guide.md`, `tests/test_standards.py` | `tests/test_split_page.py` | SHIPS | yes |

New moving parts: none

## Risks

Risks: none

## Notes

- The tasks run one after another because each shares files with the next; COLLECTOR starts once
  the in-flight tasks that change its files have merged, and Forge's Scope overlap rule enforces it.
- COLLECTOR pins the command declaration: each module may define `COMMANDS`, a list of dicts with
  `words` (the command words, such as "story new"), `run` (the function, resolved when the command
  runs), `changes_state` (bool), `help` (the one-line help as today), `args` (today's `_arg` tuples),
  `position` (an int; today's order becomes 10, 20, 30... so later commands can fit between) and
  `listing` (the exact text of that command's row in today's guide table). A module may define
  `GROUP_HELP`, mapping a group word such as "spec" to its help; each group's help must be declared
  exactly once across all modules, and a test fails on none or two. The collector discovers every
  module in the `forge` package with `pkgutil`, with no fixed list, so a command in a new module
  needs no `cli.py` edit. Until COMMANDS finishes, `cli.py` builds from the declarations plus the
  rows still in its table.
- SHIPS pins the shipped-file declaration: a module may define `ships(top, cfg) -> dict[str, str]`
  returning each path it writes and its text, so conditional files (`CLAUDE.md`), files written
  for both hosts and files found by a template folder keep their rules inside their owner. Owners:
  `story.py` the Forge skill and its FDE page; `review.py` the test-audit skill; `approval.py` the
  Remote Control skill; `githooks.py` the host adapters and the git hooks' files; `prcheck.py` the
  CI workflow. `sync.files` returns the union and keeps its signature, so `doctor`, `init` and
  `migrate` stay as they are.
- `docs/commands.md` is not a shipped file: `forge sync` writes it only in Forge's own repo
  (`repo = "forge-source"`), outside `sync.files`, so client repos get exactly the same files and
  messages as before; in Forge's own repo `sync` may add one line naming the page it wrote.
- Each test file starts with `STORY = "FORGE-SPLIT-1"`, and its `test_<n>_` names cite the Done-when
  items its task covers.
