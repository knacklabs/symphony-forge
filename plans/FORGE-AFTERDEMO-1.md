# After a demo: waiting items show in the app, notes become changes, and releases get a backup before Promote

3 parts · Risks: none one-way · New moving parts: one notifications module with one table in each starter (Done-when 1)

## What changes for you

- Each person in a new client app sees the records that wait for their action, such as an approval or an assignment, in a list with a count. The app's API gives the list and the count. The client's agent builds the screen in the client's design, as FORGE-NOSCREENS-1 requires for every API that a person uses. Forge ships no screen. A record leaves the list when the action is done. Email comes later through SNS and is not in this story. (Source: your decisions, 31 Oct 2026)
- The agent's guide and the builder brief tell the agent how to make a record wait for a person. The agent adds the waiting entry in the same save as the change, and removes it in the save of the action. (Needed by: the list)
- After a demo, the agent puts the notes or the call transcript in `docs/context/`, reads them all and shows one list of changes in plain words, one line for each change. The FDE gives one OK. Then the agent starts each change with `forge start`. Nothing starts before the OK. (Source: your decision, 31 Oct 2026)
- The guide says that Mainline takes a backup when a person presses Promote on a release that adds a migration file, and that one test restore runs before launch. Mainline checks the release itself, because git shows the added file, and does the backup and the restore. Forge adds no mark and no check. (Source: your decisions, 31 Oct 2026)
- The rule that every migration keeps the previous release working belongs to FORGE-EXPAND-1. This story cites it and does not rebuild it. (Source: your decision, 31 Oct 2026)
- A new client repo gets the API at `forge init --starter`, in either starter, and all the guide text. An existing client repo gets the guide text with `forge sync`. It keeps all its app code and gets no migration. Its agent adds the notifications module by hand when a feature first needs it, from the names in the guide. (Source: the Forge review rules)

Design: none (the API ships no screen; each client app's own design covers the list)

## Why

After a demo, the FDE has no single way to turn notes into separate changes with one approval. A person who waits on an approval or an assignment does not see it in the app, so work stalls. A Mainline rollback changes only the code. A migration can destroy data, and the guide does not say who takes a backup before a release that carries one.

## Done when

1. **In a new app from either starter, a signed-in person's list shows the records that wait for them, with a count. The count drops when the action is done. No other person and no other company sees the entry.**
2. **The agent's guide and the builder brief say how a feature makes a record wait for a person and clears it. A new repo gets the text at init. An existing repo gets it with forge sync and its app code does not change.**
3. **The guide tells the agent how to turn demo notes or a transcript into one list of changes, how to get one FDE OK, and to start each change with forge start only after that OK.**
4. **The guide says that Mainline takes a backup at Promote when the release adds a migration file, and that one test restore runs before launch. It names both as Mainline's work.**

## Risks

Risks: none one-way. Each part reverts with its pull request.

Trade-off: a person has no way to mark an entry as read and no way to delete it. An entry goes away only when the action is done. A list that grows stale is a sign that the feature forgot to clear its entries, and the review reads that.

Trade-off: Forge does not check that the backup or the test restore happened. Mainline owns both.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-AFTERDEMO-1"`. Tests run the forge command and never import forge. For app behaviour they name the cases that the app's own run reports, through `live_run` (`tests/test_starter_tree.py`), `live_python_starter` (`tests/test_python_starter.py`) and `_require_cases`, as `tests/test_mcp.py` does. Live tests carry `@pytest.mark.platform` and `@pytest.mark.timeout(1800)`. `.github/workflows/starter-smoke.yml` lists and runs `tests/test_notifications.py` in both jobs. Guide tests use `_adopted_files_after_sync` from `tests/test_mcp.py` and the setup of `tests/test_mcp_resources_guide.py::test_3`. TS means `src/forge/templates/starter`, PY means `src/forge/templates/starter-python`.

### What exists (evidence)

- No assignee or approval exists in the starters. The field kinds are text, long-text, number, money, date, yes-no, email, status and link (`src/forge/templates/feature/kinds.toml`), so a "waiting" list cannot be derived from a feature's rows. One table holds it.
- History is the model: TS `libs/history/contracts/src/service.ts` (`HISTORY_API`, `record(..., tx?: unknown)`), `libs/history/server/src/history.{service,controller,module}.ts`, `apps/api/prisma/schema/history.prisma`, with a `@Global()` module exporting the token. PY `app/history/{__init__,models,routes,schema,service}.py`, where `record` adds a row to the caller's session and the caller's one commit saves it.
- `src/forge/feature.py` lines 195-220 lists every file a new TS module touches: `apps/api/package.json`, `apps/api/tsconfig.json` references, the `eslint.config.mjs` scope line, `scripts/test-build.mjs`, `apps/api/test/database.e2e-spec.ts` (schema list), `pnpm-lock.yaml`.
- Migrations run at container start (`prisma migrate deploy` in the starter Dockerfile; Alembic in PY). The Python chain ends at `0013_via_agent.py`.

### Words this story pins

NOTIFY pins the names. NOTIFYPY follows them. GUIDE quotes them.

- **Table.** `Notification` in schema `notifications`: `id` (uuidv7), `organisationId`, `recipientAccountId`, `subjectId`, `subjectName`, `message`, `createdAtUtc`, `resolvedAtUtc` (null while the record waits). Follow the database skill and the history migration for columns, indexes and the schema list (`apps/api/prisma/schema/base.prisma`). An index on `recipientAccountId` for open rows serves the list.
- **Service.** TS `NotificationsApi` in `libs/notifications/contracts/src/service.ts`, token `NOTIFICATIONS_API`, `NotificationsPrincipal = { id: string; organisationId: string }`:
  - `notify(principal, recipientAccountId, subjectId, subjectName, message, tx?)` adds one open entry.
  - `resolve(principal, subjectId, tx?)` closes every open entry of that record in the principal's organisation.
  - A reassignment is `resolve` then `notify` in one transaction. PY `NotificationsService.notify(account, recipient_account_id, subject_id, subject_name, message)` and `resolve(account, subject_id)` add and change rows in the caller's session and never commit. The name is `notify`, not `raise`, which is a Python keyword.
- **Route.** `GET /api/v1/notifications`, any signed-in person, own entries only, no permission name and no admin check. It answers `data: { count, items }`. `items` holds at most 100 open entries, newest first, each `{ id, subjectId, subjectName, message, createdAtUtc }`. `count` is the number of all open entries of the person. TS: `NotificationsController` with `@Controller('notifications')`, `@ApiOperation({ summary: 'List the records that wait for you.' })`, `@ApiErrors(401)`. PY: `router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])` included in `app/main.py`.

### Done-when details

1. The list (NOTIFY, NOTIFYPY).
   - TS app case in `apps/api/test/notifications.e2e-spec.ts`: `a person sees the records that wait for them, with a count`.
     - An admin invites a member, who joins (the `invite` helper and accept-invite). The test calls `notify` twice for two records, for the member, on the real service and the tested database. A new helper `callNotifications` in `apps/api/test/helpers.ts` does this: it runs a one-off script inside the `api` container (`docker compose -f compose.test.yml exec -T api node ...`), the way `psql` and `logEvents` already call Docker. The script starts the app context from the built app (`NestFactory.createApplicationContext`), takes `NOTIFICATIONS_API`, and calls it. The tests import no app code.
     - The member's `GET /api/v1/notifications` answers `count` 2 and two items, newest first. The admin's answers `count` 0. A second company's person gets `count` 0. A signed-out call gets 401.
     - `resolve` for one record makes the member's count 1.
     - A transaction that calls `notify` for a new record and `resolve` for a record that already waits, then fails, leaves the new entry absent and the old entry open (the member's count is unchanged). A `resolve` that ignores `tx` fails this case. This runs through the same helper, with the script opening the transaction and throwing.
   - PY app case in `apps/api/tests/test_notifications.py`: `test_a_person_sees_the_records_that_wait_for_them_with_a_count`, with the same steps, including the failed-transaction case, on the real service. A new helper in `apps/api/tests/conftest.py` runs a one-off script inside the `api` container (`docker compose -f compose.test.yml exec -T api python -`) that opens a session on the app's own database settings, the way the `psql` helper in `test_soft_delete.py` calls Docker.
   - Test `tests/test_notifications.py::test_1_a_waiting_record_shows_in_the_persons_list` (repo level), parameters `typescript`, `python` and `earlier adopted`. Live: the reports hold the app case. `earlier adopted`: after upgrade and sync, the files under `libs/` and `apps/` are unchanged.
   - Not built: mark as read, delete, "any admin" broadcast, an agent tool for the list. Notes has the scores.
2. Guide text for the list (GUIDE).
   - `src/forge/templates/skill.md`: a section "Waiting records" with the pinned names above and these rules: add `notify` in the same transaction as the change that makes a record wait; add `resolve` in the transaction of the action; a reassignment is both; the agent builds the list and the count in the client's design by the rule in FORGE-NOSCREENS-1; no email until the SNS story. In both constitution "Built in" outlines, add one line that the API lists each person's waiting records with a count. An app without the module gets it by hand, from the names above, when a feature first needs it.
   - `src/forge/templates/brief.md`: the same rule for builders in one short paragraph.
   - `docs/guide.md`: one sentence. `forge sync` rewrites `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`.
   - Test `tests/test_after_demo_guide.py::test_2_the_guide_says_how_a_record_waits_for_a_person`, parameters `new init` and `previous release`. Both synced copies and the brief hold the sentences, compared with whitespace collapsed. `previous release`: after `forge sync`, `git status --porcelain` lists only synced files, no app file.
3. After a demo (GUIDE).
   - `src/forge/templates/skill.md`: a section "After a demo", linked from journey step 7. The agent saves the notes or transcript in `docs/context/`, reads them all, and shows one list. One line per change, in the client's words, with who asked and which screen or record it touches. Two ideas in one sentence become two lines. Questions the notes leave open go below the list as "Need an answer". A change the FDE says can wait goes to the later list with `forge start "Do this later: <idea>"`. The FDE answers once: OK, or edits. After that the agent runs `forge start "<change>"` for each line. Forge picks a fix or a story for each. Nothing starts before the OK. The OK is the FDE's reply. Forge stores no record of it.
   - Test `tests/test_after_demo_guide.py::test_3_the_guide_turns_demo_notes_into_one_list`, same parameters and setup as test_2.
4. Backup and test restore (GUIDE).
   - `src/forge/templates/conventions/deploy.md`, after the "Expand, then contract" paragraph, and journey step 6 in `skill.md`: when a release adds a migration file, Mainline takes a backup at Promote; one test restore runs before the first launch; Mainline checks the release for the file itself and does both; the agent does neither and writes no mark; the migration rule itself is FORGE-EXPAND-1's.
   - Test `tests/test_after_demo_guide.py::test_4_the_guide_names_the_backup_and_the_test_restore`, same parameters as test_2.

### New and existing repos

- **New repos** (`forge init --starter`, `forge init --starter python`): the notifications API, its table and tests, the guide text. Plain `forge init` gets the guide text only.
- **Existing repos** (after upgrade and `forge sync`): the guide text. No app file and no migration. Each rule has a test on the adopted earlier-release fixture.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| NOTIFY | The waiting list in the TypeScript API | The `notifications` module: table and migration, `NotificationsApi.notify` and `resolve`, `GET /api/v1/notifications`, its wiring and the app case. | 1 | `src/forge/templates/starter/libs/notifications/**` (new), `starter/apps/api/prisma/schema/notifications.prisma` (new), `starter/apps/api/prisma/schema/base.prisma`, `starter/apps/api/prisma/schema/auth.prisma` and `starter/apps/api/prisma/schema/organisations.prisma` (the relation fields for the two foreign keys), `starter/apps/api/prisma/migrations/<timestamp>_notifications/**` (new), `starter/apps/api/src/app.module.ts`, `starter/apps/api/package.json`, `starter/apps/api/tsconfig.json`, `starter/eslint.config.mjs`, `starter/scripts/test-build.mjs`, `starter/pnpm-lock.yaml`, `starter/apps/api/test/notifications.e2e-spec.ts` (new), `starter/apps/api/test/helpers.ts`, `starter/apps/api/test/database.e2e-spec.ts`, `starter/README.md`, `tests/test_notifications.py` (new), `.github/workflows/starter-smoke.yml` | `tests/test_notifications.py` (`test_1`: `typescript`, `earlier adopted`) | FORGE-NOSCREENS-1/SCREENS | no | |
| NOTIFYPY | The waiting list in the Python API | The same table, service and route in the Python starter, with an Alembic migration and its case. Regenerate `libs/shared/api-types`. | 1 | `src/forge/templates/starter-python/apps/api/app/notifications/**` (new), `starter-python/apps/api/app/main.py`, `starter-python/apps/api/migrations/versions/<next>_notifications.py` (new), `starter-python/apps/api/migrations/env.py`, `starter-python/apps/api/pyproject.toml`, `starter-python/apps/api/tests/test_notifications.py` (new), `starter-python/apps/api/tests/conftest.py`, `starter-python/apps/api/tests/test_module_schemas.py`, `starter-python/libs/shared/api-types/**` (regenerated), `tests/test_notifications.py` | `tests/test_notifications.py` (`test_1`: `python`) | NOTIFY, FORGE-NOSCREENS-1/AUTHPY | no | |
| GUIDE | The guide covers the list, the demo notes and the backup | "Waiting records" and "After a demo" in the skill, the builder rule, the deploy paragraph, the guide sentence and the synced copies. | 2, 3, 4 | `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `src/forge/templates/conventions/deploy.md`, `docs/guide.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_after_demo_guide.py` (new) | `tests/test_after_demo_guide.py::test_2`, `test_3`, `test_4` (new) | NOTIFY, NOTIFYPY, FORGE-NOSCREENS-1/RULES, FORGE-EXPAND-1/EXPAND | no | |

NOTIFYPY follows NOTIFY because NOTIFY pins the names. GUIDE is the last, small wiring part: the three guide texts share `skill.md`, so one part owns them. NOTIFY waits for NOSCREENS' SCREENS because both regenerate the lock file and edit the starter README. NOTIFYPY waits for AUTHPY because both add an Alembic revision, and the chain must stay in one line.

New moving parts: the `notifications` module with its table in each starter (Done-when 1).

## Notes

- **Scores (F x H >= 2 x C).** Each part's model-cost effect is stated.
  - Waiting list API, both starters: F 3 (every app with an approval or an assignment), H 2 (a missed approval stalls work), C 3 (a new table, in two starters). 6 >= 6. Kept. Cost: two worker rounds on the build model; no model call at run time.
  - The guide text (list rule, after-a-demo, backup): F 2 (every demo or release), H 2, C 1. 4 >= 2. Kept. Cost: `skill.md` grows by about 40 lines, which every agent reads once per session (a few hundred tokens), and the builder brief by about 6 lines.
  - Mark as read or delete an entry: F 3, H 1, C 2. 3 < 4. Cut.
  - An agent tool for the list: F 1, H 1, C 2. 1 < 4. Cut. The list is the person's own, and each feature's tools already cover its records.
  - A broadcast "any admin" entry: F 1, H 2, C 2. 2 < 4. Cut. One person is the recipient.
  - A mark on releases that add a migration, and a Forge check that the backup or the test restore happened: Mainline reads the added file from git itself and owns both, and principle 4 says to add no gate only to police a rule. Cut by the owner's choice (31 Oct 2026).
  - Email through SNS: waits for its own story (owner decision, 31 Oct 2026).
- **Planner choices the owner did not make.**
  1. One entry is for one record and one person, and it closes when the action is done. There is no read mark.
  2. The list and the count come from one route, so a screen needs one call.
  3. `notify` and `resolve` take flat arguments, and `notify` is the Python name too, because `raise` is a Python keyword.
  4. The backup and the test restore are guide text only, as the owner chose.
  5. The demo notes go in `docs/context/`, as journey step 1 already says. The FDE's OK is a chat reply, and Forge stores no record.
- **Owner's choice (31 Oct 2026).** Forge adds no mark to a release. Mainline checks whether a release adds a migration file, because git already shows it, and takes the backup at Promote. One test restore runs before launch. Both are Mainline's work.
- **Order with other work.**
  - FORGE-NOSCREENS-1 removes the starter screens and owns the rule that every person-facing API gets a screen. This story builds no screen and says the agent builds the list's screen by that rule. Its SCREENS, AUTHPY and RULES parts are listed under After.
  - FORGE-EXPAND-1 (the two-step change rule: add first, remove a release later) is approved and not merged. GUIDE cites it and does not copy it. Its text also edits `deploy.md` and `skill.md`, so merge it first or resolve the clash.
  - FORGE-MAIL-1's guide part and FORGE-GUIDES-1 edit `skill.md` and `docs/guide.md` on other lines. These are merges, not code needs.
- No client repo is named in this story's code, tests, texts or commits.
