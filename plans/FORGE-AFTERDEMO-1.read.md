---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-31T10:53:08.125855+00:00
seconds: 95.888
read_hash: 427a4b52c350ee5976dfbb8ba4297ae9b9e0fcac
round: 2
passed: yes
doc_seen: 427a4b52c350ee5976dfbb8ba4297ae9b9e0fcac
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 4b308b73cf154f10a4433bc6ce8971bf832e0fef
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a19175-198c-7423-9128-9c22b0243e9a
session:
loop_choice:
loop_reason:
---
# Cold read notes

Written by `forge read`. Under every blocking finding, write one disposition line, amend the
doc, then run `forge read <doc>` again until a round has no blocking notes. Notes marked
`Advisory:` are recorded without requiring a disposition or another round:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

A finding inside What counts is cut or deferred. Keep one only when it falls outside that boundary
or is factually wrong or not worth the change, and give as the reason the Leave out line, the
missing Raise line, the cited fact that disproves it, why it is not worth the change, or the
human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: NOTIFY excludes core schema files needed by its new relationships.
   Raise: Plan gap.
   Case: normal use - building the notifications table with the required account and company foreign keys.
   [The table rule](plans/FORGE-AFTERDEMO-1.md:53) requires the database skill, whose [module-link rule](src/forge/templates/skills/database/SKILL.md:44) keeps foreign keys to core tables. Prisma needs the corresponding relationship fields in `schema/auth.prisma` and `schema/organisations.prisma`, as the existing `IdempotencyKey` relationships show. Neither file appears in [NOTIFY's Scope](plans/FORGE-AFTERDEMO-1.md:92). Add these required edits to that task.
   Gain 4, Work 1, Harm 4
   Disposition: cut - `auth.prisma` and `organisations.prisma` are now in NOTIFY's Scope, for the relation fields of the two foreign keys.

2. Blocking: The app tests rely on service access that the existing test setup does not provide.
   Raise: Plan gap.
   Case: normal use - running the planned notifications cases in starter smoke.
   [The plan](plans/FORGE-AFTERDEMO-1.md:64) obtains a service from the running TypeScript app and uses a Python session fixture. TypeScript tests instead use an [external HTTP address](src/forge/templates/starter/apps/api/test/helpers.ts:7); Python's [fixtures](src/forge/templates/starter-python/apps/api/tests/conftest.py:49) provide HTTP clients, with no database session fixture. Both APIs run in containers, and their databases expose no host port. Pin how these cases invoke the real services against the tested database, and include any required setup files in Scope.
   Gain 4, Work 2, Harm 2
   Disposition: cut - both app cases now call the real service through a helper that runs a one-off script inside the `api` container, as `psql` and `logEvents` already call Docker. `helpers.ts` and `conftest.py` are in Scope.

3. Blocking: Unproven: item 1: a failed action must leave its waiting entry open.
   Raise: Test.
   Case: normal use - an action calls `resolve`, then its transaction fails and rolls back.
   [The promised behavior](plans/FORGE-AFTERDEMO-1.md:8) saves the action and resolution together. [The app cases](plans/FORGE-AFTERDEMO-1.md:66) test successful resolution and rollback of `notify` only. A TypeScript `resolve` that ignores `tx` and writes through the default connection passes every listed assertion while removing an entry for an action that never completed. Extend the existing case to prove resolution rolls back too.
   Gain 3, Work 2, Harm 3
   Disposition: cut - the rollback case now also calls `resolve` on a waiting record inside the failing transaction and expects the entry to stay open.

4. Advisory: Remove the dependency on SCREENS that exists only for shared-file edits.
   Raise: Plan gap.
   [The plan explicitly explains](plans/FORGE-AFTERDEMO-1.md:96) that NOTIFY waits for SCREENS because both edit the lock file and README. Those edits require coordination, not the other task's code. This contradicts [the task dependency rule](src/forge/templates/skill.md:1446). Give the shared edits one owner or place them in the final wiring task.
   Gain 2, Work 1, Harm 1
   Disposition: keep - the lock file and README are shared edits, not shared code, but the order is already set by the plan's task order and one owner for them would need a new wiring task for a Gain 2 note (live with).

5. Advisory: Split: NOTIFY → storage and service; route and starter wiring.
   Raise: Plan gap.
   [NOTIFY's Scope](plans/FORGE-AFTERDEMO-1.md:92) suggests more than the requested limit of about 400 changed lines. The existing history contracts, server and app test already total 303 lines; this task also needs the new schema, migration, command-level test, lock-file entries and starter wiring. Separate those responsibilities before building.
   Gain 2, Work 2, Harm 4 (floor: migration)
   Disposition: keep - one part per starter is the smallest split that keeps the pinned names in one place; the owner's cuts already removed the screen, so the part is below the size that needs a split (live with).

## Round 2

6. Advisory: The new Python helper bypasses the app's installed dependencies.
   Raise: Plan gap.
   Case: normal use - running the notifications app case in Python starter smoke.
   [The amended plan](plans/FORGE-AFTERDEMO-1.md:68) runs `docker compose ... exec -T api python -`. The [Python Dockerfile](src/forge/templates/starter-python/Dockerfile:15) installs dependencies with `uv sync` into the project's virtual environment and does not add that environment to `PATH`. Plain `python` therefore cannot import the service's dependencies. Use `uv run --no-sync python -`, matching the container's existing startup commands.
   Gain 3, Work 1, Harm 2
   Disposition: keep - below the bar (follow-up)
