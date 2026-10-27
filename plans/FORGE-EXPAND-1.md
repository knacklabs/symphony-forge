# Client migrations keep the previous release working

1 part · Risks: none one-way · New moving parts: none

## What changes for you

- In a client app, every database migration must work with the previous release. Mainline's
  Roll back puts the previous release's code live and keeps the database, so the old code must
  still find every table and column it uses. (Source: your decision, 27 Oct 2026)
- The database guide states expand then contract: add the new table or column first, and remove
  the old one two releases later, when no live release uses it. The agent's guide and the worker
  brief say the same. (Source: your decision, 27 Oct 2026)
- Close reads each migration that a change adds, in both starters: the SQL file of a Prisma
  migration and the Python file of an Alembic migration. A drop, a rename or a type change of a
  column or table stops close. (Source: your decision, 27 Oct 2026)
- To get past the stop, the worker writes a Contract line in that migration file, for example
  `-- Contract: the live release no longer reads "Project"."legacyName".` (`# Contract: ...` in
  a Python migration). Close then lets the migration pass, and the review reads the line.
  (Source: your decision, 27 Oct 2026; the place of the line is the planner's choice)
- A new client repo gets the check and the guide text from its first change. An existing client
  repo gets the check when it moves to this release, and the guide text with `forge sync`. Close
  reads only migrations that a change adds, so the migrations that are already in a repo never
  stop it. (Source: your request, 27 Oct 2026)
- Mainline's snapshot before each migration and its Restore action are Mainline's work, not this
  story's. (Source: your decision, 27 Oct 2026)

Design: none (no screens; it adds one close check and changes guide text)

## Why

A Mainline Roll back reverts the code only. The database stays at the new migration, so old code
that reads a removed or renamed column fails. Today the rule is only text: "Prefer additions" in
the Python guide, "Migrations only add" in the agent's guide and "Keep migrations additive" in
the deploy guide. Close reads no migration file, so nothing stops a destructive migration before
it merges.

## Done when

1. **In a new client repo and in a repo adopted on an earlier release, close refuses a change that adds a Prisma or Alembic migration that drops, renames or changes the type of a column or table. The refusal names the migration file and each statement, and names the Contract line as the way past it.**
2. **With a Contract line in that migration file, the same change passes close. Statements that keep the previous release working do not stop close: added tables and columns, index and constraint changes, and the drops in an Alembic `downgrade()`.**
3. **The database guide, the agent's guide (`src/forge/templates/skill.md`) and the worker brief (`src/forge/templates/brief.md`) state expand then contract and the Contract line, in the same change.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. The part reverts with its pull request.

Trade-off: close matches statements in the migration text. It does not compare schemas. A
hand-written `ALTER TABLE t DROP c` without the word `COLUMN` passes. Prisma always writes
`DROP COLUMN`, and the review reads every migration.

Trade-off: close does not check what the Contract line says. The review reads it, as it reads the
rest of the migration.

Trade-off: an edit to a migration that is already on the default branch is not read. The guides
already say never to edit a merged migration.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

The new test file starts with `STORY = "FORGE-EXPAND-1"`. Tests run the forge command and never
import forge.

### Where the Contract line lives

In the migration file itself, as a comment line: `-- Contract: <why>` in SQL, `# Contract: <why>`
in Python. The worker writes that file anyway. The line stays beside the drop in git and in the
pull request diff, it works the same in a fix and in a story task, and close reads no other file.
A commit message is lost when the pull request is squashed, and a line in the fix or story doc is
far from the statement it allows. One Contract line allows every statement in its file.

### The check (pinned)

- One function, `migrations(top, cfg, base)`, in `src/forge/app_baseline.py`, next to `check`
  and `services`, with one `REFUSALS["contract"]` entry. `close` calls it in
  `src/forge/close.py` on the line after `app_baseline.services(top, cfg)`, with the same
  merge-base that `app_baseline.check` gets. `close.py` grows by one line (1,143 today).
- It returns at once when `cfg.get("repo") != "client"` or `repo.is_prototype(top, cfg)`: a
  prototype has no live release to roll back to.
- Added files: `git diff --name-only -z --no-renames --diff-filter=A <base> HEAD --` with
  `:(glob)**/prisma/migrations/*/migration.sql` and `:(glob)**/migrations/versions/*.py`. The
  text is `git show HEAD:<path>`.
- A file with a line that matches `^\s*(?:--|#)\s*Contract:\s*\S` (multiline) passes.
- SQL (the `.sql` file, and each string constant in an Alembic `upgrade()`): drop comment lines
  that start with `--`, then match, case-insensitive, `DROP TABLE`, `DROP COLUMN`,
  `ALTER TABLE ... RENAME` (but not `RENAME CONSTRAINT`), and `ALTER COLUMN ... TYPE` or
  `ALTER COLUMN ... SET DATA TYPE`. `DROP INDEX`, `DROP CONSTRAINT`, `DROP TRIGGER` and
  `ALTER INDEX ... RENAME` pass.
- Python: `ast.parse` the file and walk only the body of the top-level `def upgrade`. A call whose
  attribute name is `drop_table`, `drop_column` or `rename_table`, or an `alter_column` call with a
  `type_` or `new_column_name` keyword, is a problem (this also covers `batch_op.`). Use `ast`,
  not a regex: autogenerate writes `existing_type=sa.INTEGER()` before `type_=`, and
  `drop_constraint(..., type_="foreignkey")` is not a type change.
- Each problem is `<path>: <statement>`, where the statement is the matched SQL line, stripped,
  or `op.<name>` for a Python call. Problems join with `; `.
- The entry:

  ```python
  "contract": ("Mainline's Roll back runs the previous release's code on this database, and "
               "this change's migrations remove or change what that code may still use: "
               "{problems}.",
               "make the migration only add (expand now, contract two releases later), or add a "
               "`-- Contract: <why the live release no longer uses it>` line (`# Contract:` in a "
               "Python migration) to the migration file, then forge close {item}"),
  ```

  `item` is `repo.current_branch(top).partition("/")[2]`, as `services` does it.

### The guide text (pinned)

- `src/forge/templates/skills/database/SKILL.md`: after the last paragraph (it ends
  `Never edit a merged migration.`), add:
  "Every migration must work with the previous release: Mainline's Roll back puts the previous
  release's code live and keeps the database. Expand, then contract. Add the new table or column
  first and let the code use both. Remove the old one two releases later, when no live release
  uses it. Close refuses a new migration that drops, renames or changes the type of a column or
  table. When the live release no longer uses it, put a `-- Contract: <why>` line in the SQL
  migration (`# Contract: <why>` in an Alembic migration). In a Prisma app, write the line before
  you apply the migration: `prisma migrate dev --create-only`, then edit the SQL."
- `src/forge/templates/skill.md` line 1110: replace
  "- Migrations only add, and work with the previous version of the app still running." with
  "- Migrations work with the previous release still running: expand, then contract. A drop,
  rename or type change waits two releases and carries a `Contract:` line (the database skill)."
- `src/forge/templates/brief.md`: after the paragraph that starts
  "In an app with a database, follow the database skill", add:
  "Every migration must work with the previous release: expand, then contract. Close refuses a
  new migration that drops, renames or changes the type of a column or table unless the
  migration file has a `-- Contract: <why>` line (`# Contract: <why>` in Python) that says the
  live release no longer uses it."
- `src/forge/templates/conventions/python.md` line 257: replace "Prefer additions; a drop or
  rewrite goes under the story's Risks with recovery steps." with "Expand, then contract, as the
  database skill says."
- `src/forge/templates/conventions/deploy.md` line 50: replace "Keep migrations additive so
  restarting a container cannot remove production data." with "Expand, then contract (the
  database skill), so a restart or a Roll back cannot lose data the running code needs."
- `src/forge/standards.md` line 198: replace "Prefer migrations that only add; a destructive one
  goes under the story's Risks." with "Expand, then contract: a drop, rename or type change waits
  until no live release uses it and carries a `Contract:` line."
- `forge sync` rewrites the copies in this repo: `.claude/skills/forge/SKILL.md`,
  `.codex/skills/forge/SKILL.md`, both `skills/forge/standards.md` copies and both
  `skills/database/SKILL.md` copies.
- `tests/test_live_skill.py::test_6_skill_adopts_a_live_app_and_repo_rules_win` pins
  "Migrations only add" and "previous version of the app". Change them to "Migrations work with
  the previous release still running" and "expand, then contract".

### Done-when details

1. and 2. `tests/test_migrations_keep_previous_release.py::test_1_close_holds_a_migration_the_previous_release_cannot_run`,
   parametrised `new-client-prisma`, `new-client-alembic` and `adopted-v1.2.2-prisma`. Setup:
   `_client_repo(env, tmp_path, previous)` from `tests/test_score_notes.py`, `env.checks(GREEN)`,
   and a fix through `env.start`, as `_fix` in `tests/test_shadcn_only.py` does.
   - `new-client-prisma` adds `apps/api/prisma/migrations/20261101000000_notes/migration.sql`
     with `ALTER TABLE "Project" ADD COLUMN "title" TEXT;`, `DROP INDEX "idx_Old";`,
     `ALTER INDEX "a" RENAME TO "b";`, `ALTER TABLE "Project" DROP COLUMN "legacyName";` and
     `DROP TABLE "LegacyNote";`.
   - `new-client-alembic` adds `apps/api/migrations/versions/0011_notes.py` whose `upgrade()`
     has `op.add_column(...)`, `op.drop_constraint("fk", "project", type_="foreignkey")`,
     `op.alter_column("project", "status", existing_type=sa.INTEGER(), type_=sa.Text())` and
     `op.rename_table("note", "memo")`, and whose `downgrade()` has `op.drop_column(...)` and
     `op.drop_table(...)`.
   - `adopted-v1.2.2-prisma` adds a Prisma migration with
     `ALTER TABLE "Project" RENAME COLUMN "name" TO "title";`.
   - Each case: `forge close` exits 1; the output names the file, each destructive statement,
     "Contract:" and `then forge close <item>`, and names no index or constraint statement and
     no `downgrade()` call. Then the test appends a Contract line to the file, commits,
     `env.reviews(CLEAN)`, and `forge close` exits 0.
3. In the same test, before the first close: `install_claude(repo)`, `forge work <item>`, and
   `calls(log)[-1]["brief"]` has "Every migration must work with the previous release: expand,
   then contract." Both synced `.claude` and `.codex` copies of `skills/database/SKILL.md` have
   "Expand, then contract." and both `skills/forge/SKILL.md` copies have "Migrations work with
   the previous release still running: expand, then contract." Compare text with its whitespace
   joined (`" ".join(text.split())`).

### New and existing repos

- **New repos** (`forge init`, `forge init --starter react` or `python`, and a repo adopted with
  `forge init` on this release): the close check from their first change; the forge skill,
  standards and database skill from init's sync; the brief and conventions from the installed
  release. The starters' own migrations are in init's first commit on the default branch, so
  close never reads them. Tested in the two `new-client` cases.
- **Existing repos** (on upgrade with `forge upgrade` or `forge sync`): the close check and the
  brief with the release; the skill, standards and database skill text with `forge sync`. Their
  migrations on the default branch are not read. Tested in the `adopted-v1.2.2-prisma` case.

## Tasks

<!-- One row per task. Covers: the Done-when numbers it delivers, at most three. Scope: the paths
it may change. Tests: the tests it adds or changes. After: the tasks it waits for. When two tasks
share a function, field, file format or command, the first task pins it: it commits the shared
names and stubs plus one test that crosses both sides, and the tasks that use it list it under
After. Split tasks so each owns its files; shared lines (command table, guide list, registry) go
to one task or a small last wiring task; After only when a task needs another task's code. The
Developer column is optional: the lead fills or changes a GitHub username here, below For the
builders, without another approval. Leave it blank for an unassigned part. Forge next uses
the caller's GitHub login; another developer may start it with a warning. Existing tables
without Developer still work. The moving-parts line stays last: "none", or each new dependency, service, datastore,
queue, background job or abstraction layer, with the Done-when item that needs it. -->

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| EXPAND | Migrations keep the previous release working | The close check on added Prisma and Alembic migrations with the Contract line, and expand then contract in every guide, on new and existing repos | 1, 2, 3 | `src/forge/app_baseline.py` (`REFUSALS["contract"]`, `migrations`), `src/forge/close.py` (one call in `close`), `src/forge/templates/skills/database/SKILL.md`, `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `src/forge/templates/conventions/python.md`, `src/forge/templates/conventions/deploy.md`, `src/forge/standards.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md`, `.claude/skills/forge/standards.md`, `.codex/skills/forge/standards.md`, `.claude/skills/database/SKILL.md`, `.codex/skills/database/SKILL.md` (rewritten by `forge sync`), `tests/test_migrations_keep_previous_release.py` (new), `tests/test_live_skill.py` | `tests/test_migrations_keep_previous_release.py` (`test_1`), `tests/test_live_skill.py` (`test_6` strings) | | no | |

One part: the refusal names the Contract line that the guides describe, and the whole change is
about 60 lines, so a split only adds a wait.

New moving parts: none

## Notes

- Owner decision (27 Oct 2026, settled): Mainline's Roll back puts the previous release's code
  live and keeps the database, so every client migration must work with the previous release.
  The guide states expand then contract (add first, remove two releases later). Close reads each
  new migration in both starters (Prisma migration SQL, Alembic Python migrations). A drop,
  rename or column type change stops close unless a Contract line says the live release no
  longer uses that column or table. Accepted cost: about 60 lines plus one test in both starters.
  Mainline's snapshot before each migration and its Restore action are Mainline's work.
- Planner choices the owner did not make: (1) the Contract line is a comment in the migration
  file; (2) client repos in the prototype stage skip the check, because they have no live
  release; (3) close reads only migrations added since the merge-base, never edited ones; (4) a
  table or column drop, rename or type change is refused, and index, constraint and trigger
  changes pass; (5) the check runs at close only, not in the pull request check.
