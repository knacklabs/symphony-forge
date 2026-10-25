# One-company client apps

4 parts · Risks: none one-way · New moving parts: none

## What changes for you

- When the agent writes a new app's constitution, it asks one question: is the app for one
  company, or for many customer companies? It writes the answer as one app setting.
- A one-company app keeps the same starter code and the same tables. One setup command makes its
  company and its first account. That first account is the admin.
- In a one-company app, nobody can sign up. The sign-in page shows no "Create an account" link.
  The sign-up page says that sign-up is closed, asks the person to get an invite from an admin,
  and links to sign in. The API refuses a sign-up. People join only from an admin's invite.
- The starters have no organisation screen and no organisation switch to hide. The Members and
  Change history screens stay, because admins invite people from Members.
- A one-company app can become a many-company app later. Change the setting to many: sign-up
  opens again, and the company and its people stay as they are, with no data migration.
- Both starters get this: TypeScript (NestJS, Prisma, React) and Python (FastAPI, SQLAlchemy, the
  same web app).
- Existing apps keep many-company behaviour. On upgrade, no app file changes.

Design: docs/design/FORGE-SINGLECO-1/ (ac29293912f99b314e54ca3488039afa66bbcd87)

## Why

Every client app makes a new organisation at each sign-up and shows open sign-up, also when it
serves one company. In a one-company app, a stranger can sign up and get an empty organisation
of their own, and the agent of each app must remove sign-up by hand.

## Done when

1. **In a new app, the constitution asks once whether the app is for one company or for many customer companies, and the agent writes the answer to the app's `APP_COMPANIES` setting. An existing app is not asked, and its files do not change on upgrade.**
2. **In a one-company app, one setup command makes the company and its first account as the admin.**
3. **In a one-company app, the API refuses a sign-up, the sign-in page shows no sign-up link, and the sign-up page says that sign-up is closed, asks for an invite from an admin and links to sign in. An admin's invite still lets a person join as a member.**
4. **An app with `APP_COMPANIES` not set or set to `many` keeps open sign-up. A one-company app that changes the setting to `many` opens sign-up, and its company, people and records stay, with no data migration.**
5. **Both starters pass the same API cases and the same browser flow for items 2 to 4.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request. No part adds a migration.

Trade-off: the setup command does not check for an existing company. Run it once. A second run
with a new email makes a second company with its own admin.

Trade-off: an existing app made from an earlier starter does not read `APP_COMPANIES`. To become
a one-company app, it needs its own story that copies this change from the starter.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

All paths under `starter/` mean `src/forge/templates/starter/`, and paths under
`starter-python/` mean `src/forge/templates/starter-python/`. The Python starter has no web app
of its own: `forge init --starter python` copies `starter/apps/web`, so the web part changes
both starters.

Each new test file starts with `STORY = "FORGE-SINGLECO-1"`. Forge's tests run the forge command
or, for starter behaviour, require case names from the starter's own live run
(`_require_cases` and `live_run` from `tests/test_starter_tree.py`, and the
`live_python_starter` fixture from `tests/test_python_starter.py`, as
`tests/test_defaults_organisations.py` does). They never import forge. Live tests carry
`@pytest.mark.platform` and a timeout, and skip unless `FORGE_STARTER_LIVE=1`.

### Why one environment value

The setting is the environment value `APP_COMPANIES`, with the values `one` and `many`. Each
starter already reads every runtime setting from the environment and checks it at start
(`starter/libs/core/src/config/environment.ts`, `starter-python/apps/api/app/core/config.py`).
A host sets it beside `APP_ENV` and `APP_ORIGIN`. A change needs a restart only: no rebuild, no
migration and no admin screen. A database row needs a migration and a screen to change it.
forge.toml is Forge's file, and the app does not read it. The web app is served by the API, so
it reads the setting from the API (below) and needs no build-time value.

`forge init` runs before the constitution interview, so init cannot know the answer. Init copies
`.env.example` with `APP_COMPANIES=many`. The agent writes the answer when it writes the
constitution (item 1).

### Shared names (pinned by COMPANYAPI)

- **The setting.** `APP_COMPANIES` is `one` or `many`. Not set or empty means `many`. Any other
  value stops the start with `APP_COMPANIES must be one or many.` Add it to `Environment` and
  `validateEnvironment` in TypeScript, and to `Settings` (field `companies`) and `load_settings`
  in Python. `.env.example` of each starter gets the line `APP_COMPANIES=many`.
- **The options endpoint.** `GET /api/v1/auth/options`, public, no rate limit change. Response
  `200` with the usual envelope: `{ "data": { "signUpOpen": true } }`, `false` when
  `APP_COMPANIES=one`. `@app/shared` gets `authOptionsSchema` (zod object with `signUpOpen:
  boolean`) and its type `AuthOptions`; the Python starter's `libs/shared/src/index.ts` gets the
  same copy, and its `openapi.json` and `api-types.ts` are regenerated.
- **The sign-up refusal.** With `APP_COMPANIES=one`, `POST /api/v1/auth/sign-up` with a valid
  body answers `403` with code `SIGN_UP_CLOSED` and the message
  `This app is invite only. Ask an admin for an invite.` It makes no account. A body that fails
  validation still gets `400` first, as today.
- **The setup command.** It reads `ADMIN_EMAIL` and `ADMIN_PASSWORD` from the environment, checks
  them with the sign-up schema (`signUpSchema` in TypeScript, `CredentialsInput` in Python), and
  makes the account and its organisation with the code that sign-up uses, with no session. It
  prints `Made the company and its admin <email>.` and exits 0. A bad value or an email that
  already has an account prints the same message the API gives and exits 1.
  - TypeScript: root script `"setup:company": "node apps/api/dist/setup-company.js"`, from the new
    `starter/apps/api/src/setup-company.ts` (`NestFactory.createApplicationContext(AppModule)`,
    then `AuthService.setUpCompany(email, password)`). `setUpCompany` is the account and
    organisation half of today's `signUp` (`createAccount`, then
    `organisations.createForAccount`), and `signUp` calls it and then makes the session, so
    sign-up and setup share one path. The same `tsc -b` build emits the file.
  - Python: `uv run --no-sync python -m app.setup_company` in `apps/api` (the image's working
    folder), from the new `starter-python/apps/api/app/setup_company.py`. It calls a new
    `AuthService.set_up_company(credentials)` that `sign_up` also uses, as above.
  - Mark the trade-off with a `ponytail:` comment in each command: no check for an existing
    company; run it once.
- **The one-company test service.** Each starter's `compose.test.yml` gets the service
  `one-company-api`, a copy of `api` with `APP_COMPANIES: one`, its own port
  `${ONE_COMPANY_TEST_PORT:-3002}` and `APP_ORIGIN` on that port, on the same database. Its
  `depends_on` is `api` with `condition: service_healthy`, as `production-api` has it, so it
  starts only after `api` has run the migrations; its own migration step then finds nothing to
  do, and two services never migrate at the same time. Each
  starter's `scripts/test.mjs` picks a free port for it, sets `ONE_COMPANY_API_TEST_URL` and
  `ONE_COMPANY_BASE_URL`, and, after `docker compose up`, runs the setup command once in that
  service (`docker compose exec -T -e ADMIN_EMAIL -e ADMIN_PASSWORD one-company-api ...`) with
  `ONE_COMPANY_ADMIN_EMAIL=one-company-<uuid>@example.test` and a fixed test password, and passes
  `ONE_COMPANY_ADMIN_EMAIL` and `ONE_COMPANY_ADMIN_PASSWORD` to the suites. The `api` and
  `production-api` services set no `APP_COMPANIES`, so every existing case runs as many-company.
  The service shares the database, so the switch case (item 4) needs no second database.

### Done-when details

1. The question and its record (COMPANYGUIDE).
   - `src/forge/templates/skill.md`, section `## App constitution`, after the sentence that starts
     `In an app that has libs/organisations or apps/api/app/organisations`, adds:
     `In an app whose .env.example has APP_COMPANIES, ask once: "Is the app for one company, or for many customer companies?" Write the answer under ## Defaults, set APP_COMPANIES to one or many in .env.example and in the host's settings, and ask it again only when the person wants to change it.`
     And, as a second sentence: `When the answer is one company, also copy this line into ## Fixed rules: "- Built in: APP_COMPANIES=one makes a one-company app: corepack pnpm run setup:company (uv run --no-sync python -m app.setup_company in the Python starter) makes the company and its first admin, and people join only from an admin's invite."`
     The question has no default: it changes the sign-in flow, so the agent asks it at the start,
     with the other first-half answers, before the prototype.
   - Each starter's `README.md` gets one short paragraph under its settings text: what
     `APP_COMPANIES` does, the setup command with `ADMIN_EMAIL` and `ADMIN_PASSWORD`, and that a
     change to `many` needs no migration (COMPANYAPI and COMPANYPY, one README each).
   - The worker brief needs no change: workers do not write the constitution, and the README and
     the constitution's fixed rule tell a worker what the setting does.
   - `forge sync` rewrites `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`.
   - Test (new repo): `tests/test_one_company_guide.py::test_1_the_constitution_asks_one_or_many_companies_once`
     (platform mark), with the two cases of
     `tests/test_built_in_defaults_guide.py::test_6` (`new init` with `forge init --starter`, and
     the `tests/fixtures/adopted-v1.2.2/client` repo moved to this release and synced). New
     init: the synced guide has both sentences, and the new repo's `.env.example` has
     `APP_COMPANIES=many`. Adopted case: after `forge sync`, the guide has the sentences, no app
     file changed (the same byte check as `test_6`), and the repo has no `APP_COMPANIES` line, so
     the guide's condition asks the app nothing.
2. Setup (COMPANYAPI, COMPANYPY).
   - API case in the new `starter/apps/api/test/one-company.e2e-spec.ts`:
     `the setup command makes the company and its first admin`: sign-in on
     `ONE_COMPANY_API_TEST_URL` with the setup admin answers `200` with role `admin`;
     `GET /api/v1/members` lists that admin only; a second setup run with the same email exits 1
     and prints `An account already uses that email.`; a setup run with
     `ADMIN_EMAIL=not-an-email` exits 1, prints the sign-up schema's email message, and makes no
     account (a sign-in with that value gets `400` or `401`, and `psql` finds no account row for
     it).
   - Python twin in the new `starter-python/apps/api/tests/test_one_company.py`:
     `test_the_setup_command_makes_the_company_and_its_first_admin`, with the same bad
     `ADMIN_EMAIL` refusal.
   - Test: `tests/test_one_company.py::test_2_setup_makes_the_company_and_its_first_admin`
     requires both case names from the two live runs.
3. Invite only (COMPANYAPI, COMPANYPY, COMPANYWEB).
   - API case `a one-company app refuses sign-up and still takes invites`: on the one-company
     service, `GET /api/v1/auth/options` gives `signUpOpen: false`; a valid sign-up gets
     `403 SIGN_UP_CLOSED` with its message, and a sign-in with that email then gets `401`; the
     setup admin invites an email (the `invite` helper, reading the logged link from the
     `one-company-api` service's logs: give the helper's service argument that name), and the
     invited person joins with role `member` and sees the admin's project.
     Python twin: `test_a_one_company_app_refuses_sign_up_and_still_takes_invites`.
   - Web (COMPANYWEB): `useAuthOptions()` in `features/auth/hooks/auth-hooks.ts` reads
     `GET /auth/options` with `authOptionsSchema` and the app's normal query defaults (no
     `staleTime` of its own), so each page load reads the options again. The sign-in page shows
     the `New here? Create an account` line only when `signUpOpen` is `true` (not while loading,
     so it does not flash). When `signUpOpen` is `false`, the sign-up page does not redirect: it
     shows the closed sign-up page from `docs/design/FORGE-SINGLECO-1/` in the same
     `AuthPageFrame`, which says that sign-up is closed, asks the person to get an invite from an
     admin, and links to `/sign-in`. It shows no form. Follow the design's SCREENS.md for the
     words and components. The route in `app.tsx` stays, so a later switch to `many` needs no web
     change. No test covers a browser that stays open across an API restart.
   - Playwright flow in the new `starter/apps/web/e2e/one-company.spec.ts` with
     `test.use({ baseURL: process.env.ONE_COMPANY_BASE_URL })`:
     `a one-company app has no sign-up and the admin invites people`: the sign-in page has no
     `Create an account` link; opening `/sign-up` stays on `/sign-up`, shows that sign-up is
     closed with no email or password field, and its sign-in link opens `/sign-in`; the setup
     admin signs in
     and sees Members with the Invite person button; axe finds no serious problem on the sign-in
     page and on the closed sign-up page. The flow also checks the many-company app: on the default `BASE_URL`, the sign-in page
     still has the link.
   - Test: `tests/test_one_company.py::test_3_a_one_company_app_is_invite_only` requires the API
     case names from both live runs and the flow name from both browser reports.
4. Many stays the default, and the switch needs no migration (COMPANYAPI, COMPANYPY).
   - API case `a one-company app becomes many-company by its setting alone`: after the item 3
     case's join, on the `api` service (no `APP_COMPANIES`, the same database), the setup admin
     signs in as `admin`, `GET /api/v1/members` lists the admin and the invited member, the
     admin's project is there, `GET /api/v1/auth/options` gives `signUpOpen: true`, and a new
     sign-up answers `201` with a new organisation and role `admin`.
     Python twin: `test_a_one_company_app_becomes_many_company_by_its_setting_alone`.
   - The start check: a unit case beside each config test (TypeScript: a vitest case for
     `validateEnvironment` in the API suite; Python: a pytest case for `load_settings`):
     `APP_COMPANIES=some` stops the start with `APP_COMPANIES must be one or many.`, and not set
     gives `many`.
   - Existing many-company cases (sign-up, organisations, invites) keep passing unchanged on
     `api`: this is the existing-app proof inside the starter.
   - Test: `tests/test_one_company.py::test_4_many_stays_the_default_and_the_switch_needs_no_migration`
     requires the names from both live runs. Existing-repo case: `test_1`'s adopted case proves
     an upgrade changes no app file and adds no setting.
5. Both starters (COMPANYPY, COMPANYWEB): items 2 to 4 each require the TypeScript and the Python
   case names, so a missing twin fails them. `tests/test_one_company.py::test_5_both_starters_pass_the_one_company_cases`
   runs `forge init --starter` and `forge init --starter python` in new repos (no live run) and
   checks that each new repo has `one-company-api` in `compose.test.yml`, `APP_COMPANIES=many` in
   `.env.example`, and its setup command file (`apps/api/src/setup-company.ts` or
   `apps/api/app/setup_company.py`) plus `apps/web/e2e/one-company.spec.ts`.

### New and existing repos

- **New repos** (`forge init --starter` and `forge init --starter python`): the starter reads
  `APP_COMPANIES`, has the setup command, the options endpoint, the sign-up refusal and the web
  changes, with `APP_COMPANIES=many` in `.env.example`. The guide's question arrives with setup.
  Plain `forge init` gets the guide text, and its condition (`.env.example` has
  `APP_COMPANIES`) asks such an app nothing.
- **Existing repos** (on upgrade to this release, after `forge sync`): no app file changes and
  no setting is added. The guide sentences arrive with sync; the app has no `APP_COMPANIES`, so
  the agent does not ask. Tested on the adopted earlier-release fixture (item 1).

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
| COMPANYAPI | One-company setting in the TypeScript API | `APP_COMPANIES` and its start check, the options endpoint, the sign-up refusal, `setUpCompany` and the setup command, the shared `authOptionsSchema`, the one-company test service and its setup run | 2, 3, 4 | `starter/libs/core/src/config/environment.ts`, `starter/libs/auth/src/auth.controller.ts`, `starter/libs/auth/src/auth.service.ts`, `starter/libs/auth/src/auth.dto.ts`, `starter/apps/api/src/setup-company.ts` (new), `starter/libs/shared/src/index.ts`, `starter/package.json`, `starter/.env.example`, `starter/compose.test.yml`, `starter/scripts/test.mjs`, `starter/apps/api/test/helpers.ts`, `starter/apps/api/test/one-company.e2e-spec.ts` (new), the API suite's config unit case, `starter/README.md`, `tests/test_one_company.py` (new) | `tests/test_one_company.py` (`test_2`, `test_3`, `test_4` with the TypeScript names); the three API cases of items 2 to 4 and the start check case | | no | |
| COMPANYPY | One-company setting in the Python API | The same contract as COMPANYAPI in the Python starter: the setting and its start check, the options endpoint, the sign-up refusal, `set_up_company` and the setup command, the shared schema copy and regenerated types, the test service and its setup run | 2, 3, 4 | `starter-python/apps/api/app/core/config.py`, `starter-python/apps/api/app/auth/routes.py`, `starter-python/apps/api/app/auth/service.py`, `starter-python/apps/api/app/auth/schema.py`, `starter-python/apps/api/app/setup_company.py` (new), `starter-python/libs/shared/src/index.ts`, `starter-python/libs/shared/openapi.json` and `starter-python/libs/shared/src/api-types.ts` (regenerated), `starter-python/.env.example`, `starter-python/compose.test.yml`, `starter-python/scripts/test.mjs`, `starter-python/apps/api/tests/test_one_company.py` (new), the config unit case, `starter-python/README.md`, `tests/test_one_company.py` (Python names only) | the Python twins of the three API cases and the start check case, required by `test_2` to `test_4` | COMPANYAPI | no | |
| COMPANYWEB | No sign-up in a one-company web app | `useAuthOptions()`, the sign-in page without the sign-up link, the closed sign-up page as the design shows it, and the browser flow, in both starters through the shared web app | 3, 5 | `starter/apps/web/src/features/auth/hooks/auth-hooks.ts`, `starter/apps/web/src/features/auth/pages/sign-in-page.tsx`, `starter/apps/web/src/features/auth/pages/sign-up-page.tsx`, `starter/apps/web/e2e/one-company.spec.ts` (new), `tests/test_one_company.py` (`test_3` flow name, `test_5`) | the flow `a one-company app has no sign-up and the admin invites people` in both live runs, required by `test_3`; `tests/test_one_company.py::test_5` | COMPANYAPI, COMPANYPY | yes | |
| COMPANYGUIDE | The constitution's one question | The two sentences in the App constitution section, the synced skill copies, on new and existing repos | 1 | `src/forge/templates/skill.md`, `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`) | `tests/test_one_company_guide.py` (`test_1`, new) | COMPANYAPI | no | |

COMPANYAPI pins the setting, the endpoint, the refusal, the setup command and the test service;
COMPANYPY and COMPANYWEB follow it. COMPANYWEB waits for COMPANYPY too, because its flow must
pass in the Python starter's live run, which needs the Python endpoint. COMPANYGUIDE waits for
COMPANYAPI only for its new-init check of `.env.example`. Each part keeps to about five code
files; its tests, compose and README lines are extra.

New moving parts: none

## Notes

- Owner decisions (25 Oct 2026, settled): the constitution asks once, one company or many; the
  answer is one setting the app reads; one code path with the same organisation table and
  `organisation_id` columns; setup makes the one organisation; the first account is the admin
  and everyone else joins only from an admin's invite; public sign-up is off in a one-company
  app; organisation screens and the switch are hidden; a later switch to many needs no data
  migration; both starters; existing apps keep many-company behaviour and nothing changes on
  upgrade.
- Planner choices the owner did not make: (1) the setting is the environment value
  `APP_COMPANIES` (`one` or `many`), not set means `many`; (2) the agent sets it when it writes
  the constitution, not at `forge init`, because init runs before the interview; (3) setup is an
  explicit command with `ADMIN_EMAIL` and `ADMIN_PASSWORD`, not an automatic first start, so no
  stranger can be first on a new deploy; (4) the setup command does not check for an existing
  company; (5) the web app learns the setting from the new public `GET /api/v1/auth/options`;
  (6) the question has no default and is asked at the start, before the prototype; (7) the
  one-company test service waits for `api` to be healthy, so only one service migrates at a
  time.
- Found while planning: the starters have no organisation screen and no organisation switch.
  Each person belongs to one organisation, and the only company screens are Members and Change
  history. This plan keeps both, because an admin invites people from Members.
- Cold read round 1:
  1. Design gate (closed sign-up changes a flow). Disposition: cut - the sign-up page now shows
     a closed sign-up page from the design in docs/design/FORGE-SINGLECO-1/, with no redirect,
     and the Design line names that folder.
  2. Concurrent migrations in the one-company test service. Disposition: cut - the service
     depends on `api` being healthy, as `production-api` does, so its migration step runs after
     `api`'s and finds nothing to do.
  3. Infinite options cache. Disposition: cut - `useAuthOptions()` uses the app's normal query
     defaults and reads the options again on each page load; no test for a browser kept open
     across a restart.
  4. Advisory: no refusal case for a bad `ADMIN_EMAIL`. Disposition: cut - each starter's setup
     case now also runs the command with `ADMIN_EMAIL=not-an-email` and expects exit 1, the
     schema's message and no account.
