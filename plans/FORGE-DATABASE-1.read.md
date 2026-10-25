---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-25T17:52:52.858811+00:00
seconds: 164.416
read_hash: ee654d250f49f9da433c51b805414b89fe29c289
round: 2
passed: no
doc_seen: ee654d250f49f9da433c51b805414b89fe29c289
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 1e54cd6fe4eb5b9f8951fbd0a17be65410de3f64
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a17422-3f4d-7a10-aa5d-ba2e564cc0be
session:
loop_choice: more
loop_reason: The owner chose one more round: fix the member role types and export the currency setting
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

1. Blocking: The column-conversion tasks exclude service changes needed to keep authentication and invitations working.
   Raise: Plan gap.
   Case: normal use - building either starter and inviting a person.
   [The plan](/plans/FORGE-DATABASE-1.md:307) removes the email uniqueness declarations but limits TypeScript service edits to Prisma enum importers. Authentication still uses `findUnique({ where: { email } })` in `starter/libs/auth/src/auth.service.ts:69,105,122`; invitations still use `organisationId_email` in `starter/libs/organisations/src/organisations.service.ts:35`. Those generated selectors disappear. Python invitations still target `("organisation_id", "email")` in `starter-python/apps/api/app/organisations/service.py:64`, which cannot match the replacement expression index. Neither column task owns these repairs. PostgreSQL requires the conflict target to match the unique index’s columns or expressions. [PostgreSQL documentation](https://www.postgresql.org/docs/18/sql-insert.html).
   Gain 4, Work 3, Harm 4
   Disposition: cut Emails keep their plain unique keys plus a named lower-case check, so the services need no change.

2. Blocking: Trap: the prescribed Prisma index representation contradicts the required empty drift check.
   Raise: Plan gap.
   Case: normal use - generating a feature and then running the documented schema comparison.
   [The plan](/plans/FORGE-DATABASE-1.md:146) requires a partial SQL index and a “nearest” non-partial `@@index`, while item 5 requires no difference between them. Those declarations describe different indexes. The pinned Prisma version is 7.10.1 (`starter/package.json:26,52`); partial-index schema support already exists behind `partialIndexes` from 7.4. The specified fallback cannot satisfy the promised drift result. [Prisma release notes](https://github.com/prisma/orm/releases/tag/7.4.0).
   Gain 4, Work 2, Harm 4
   Disposition: cut The TypeScript starter turns on Prisma's partialIndexes preview, so the schema states each index in full.

3. Blocking: The shipped ID rule has no usable path for existing apps that retain Postgres 16 or 17.
   Raise: Functional.
   Case: normal use - adding a new table after upgrading Forge in an existing app.
   [The skill contract](/plans/FORGE-DATABASE-1.md:167) prescribes `DEFAULT uuidv7()` without a version condition. The adopted case explicitly retains Postgres 16 at line 265, and the owner decision forbids a forced database upgrade. Postgres 17 lacks that built-in function, so following the skill fails; choosing a different default conflicts with the new review rule. The adoption test checks unchanged files but never exercises a new table. [Postgres 17 UUID functions](https://www.postgresql.org/docs/17/functions-uuid.html).
   Gain 4, Work 2, Harm 3
   Disposition: cut The skill's id row says the app makes the uuidv7 id on Postgres 17 or older; test_1 checks it.

4. Blocking: The skill and review extend existing-app enforcement beyond the settled “new tables only” boundary.
   Raise: Not done.
   Case: normal use - adding a column or index to an existing client table.
   [The opening contract](/plans/FORGE-DATABASE-1.md:25) and owner decision at line 471 restrict existing-app rules to new tables. However, the skill’s opening at line 160 and review rule at line 389 independently cover every added column, constraint and index. A compliant change to an old table can therefore receive a blocking finding under a policy the owner explicitly excluded.
   Gain 4, Work 1, Harm 2
   Disposition: cut The skill and the review rule now cover only tables a change adds and extensions it turns on.

5. Blocking: Unproven: the database-specific live checks are never selected by CI.
   Raise: Test.
   Case: normal use - CI validates the completed story.
   [Item 5](/plans/FORGE-DATABASE-1.md:373) places generated-feature execution and drift checks inside `tests/test_database_kinds.py` under `LIVE`; item 3 similarly gates its drift checks. The only workflows setting `FORGE_STARTER_LIVE=1` select explicit test files at `.github/workflows/starter-smoke.yml:34,48`, excluding `test_database_*.py`. No task owns that workflow update. The ordinary suite leaves `LIVE` false (`tests/test_starter_tree.py:20`), so these promised checks can remain unexecuted while CI passes.
   Gain 3, Work 2, Harm 4
   Disposition: cut PG18 adds tests/test_database_*.py to both starter-smoke jobs.

6. Blocking: Design: none omits the changed money-entry flow.
   Raise: Gate.
   Case: normal use - creating or editing a generated feature with a money field.
   [KINDS](/plans/FORGE-DATABASE-1.md:368) adds a required currency input beside the amount, despite “no screens” at line 29 and `User-facing: no` at line 440. The referenced feature story’s current design (`story/FORGE-FEATURE-1:docs/design/FORGE-FEATURE-1/SCREENS.md:134-149`) specifies one amount input with a fixed `USD` prefix and no currency-entry state. The new required interaction is outside that design.
   Gain 4, Work 2, Harm 2
   Disposition: cut The currency is not entered; the API fills it from DEFAULT_CURRENCY, so the form and design stay as they are.

7. Blocking: The field-kind indexes target creation time while the consuming feature lists sort by last update.
   Raise: Scale.
   Case: normal use - repeatedly paging an organisation’s 100,000 invoices in the default order.
   [The pinned list and filter indexes](/plans/FORGE-DATABASE-1.md:137) use `{created}`. The consuming story explicitly defaults to Updated descending (`story/FORGE-FEATURE-1:plans/FORGE-FEATURE-1.md:143-150`) and records this unresolved mismatch at lines 561-565. These indexes cannot supply that ordering, leaving each default page query to scan and sort matching rows instead of reading its next indexed page.
   Gain 3, Work 1, Harm 3
   Disposition: cut The list and filter indexes use {updated}.

8. Blocking: Trap: enabling the extension and redeploying does not recover the documented Prisma failure.
   Raise: Functional.
   Case: normal use - the first deployment fails because the application user cannot create `pg_stat_statements`.
   [The recovery instructions](/plans/FORGE-DATABASE-1.md:55) say an administrator enables the extension and deployment is retried. The TypeScript starter runs `prisma migrate deploy` (`starter/Dockerfile:12`), which records the failed migration and requires reconciliation before retrying it. Installing the extension does not clear that failure record. No task or test covers this recovery path. [Prisma failed-migration recovery](https://docs.prisma.io/docs/orm/v7/prisma-migrate/workflows/patching-and-hotfixing#failed-migration).
   Gain 3, Work 2, Harm 4
   Disposition: cut The trade-off and the skill add prisma migrate resolve --rolled-back before the new deploy.

## Round 2

9. Blocking: Converting membership roles to text leaves the TypeScript starter unbuildable.
   Raise: Plan gap.
   Case: normal use - building or type-checking a new TypeScript starter.
   [COLUMNS’s scope](/plans/FORGE-DATABASE-1.md:461) permits service edits only where files import Prisma enum types. Changing `Membership.role` to `String` also widens its generated type to `string`. Existing consumers require `'admin' | 'member'`: `starter/libs/organisations/src/organisations.service.ts:9-10`, `starter/libs/auth/src/auth.service.ts:48,65`, and `starter/libs/auth/src/session.guard.ts:36`. None imports a Prisma enum, so their required repairs remain outside scope. This is a separate type failure from note 1’s repaired email selectors.
   Gain 5, Work 3, Harm 4
   Disposition: cut One shared roleSchema in @app/shared; the services narrow stored roles with it, and COLUMNS's scope names them.

10. Advisory: The new Python currency constant has no public export for generated features.
   Raise: Plan gap.
   Case: normal use - generating a Python feature with a money field.
   [MONEY’s scope](/plans/FORGE-DATABASE-1.md:463) adds `DEFAULT_CURRENCY` to `app/core/config.py`, while KINDS requires generated APIs to use it. However, `starter-python/apps/api/app/core/__init__.py:2` exports only `Settings` and `load_settings` from that file. Direct imports from `app.core.config` violate the protected-module contract in `starter-python/apps/api/pyproject.toml:27-30`. Neither task owns the missing public export.
   Gain 3, Work 1, Harm 2
   Disposition: cut app/core/__init__.py exports DEFAULT_CURRENCY, and MONEY's scope names it.
