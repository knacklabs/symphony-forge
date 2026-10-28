# Guides and starters agree

4 parts · Risks: none one-way · New moving parts: none

## What changes for you

- The guides say what the starters do. Lists page with cursors, not page numbers. Money uses INR, not USD. The components page names the pinned shadcn version, not "latest". Environment names are lower case, as the code reads them. Workers copy what the guides say, so a guide that disagrees with the code makes wrong code. (Source: your decision, 28 Oct 2026)
- Prettier leaves both starters. No script ran it, and the guides said it ran. Ruff already formats Python. (Source: your decision, 28 Oct 2026)
- The FDE's default answers promise only what the starters build. Social sign-in, a message catalogue, in-app notices and file storage each say that they come with the story that needs them. Error alerts come from Mainline, which reads the app's error log lines with their error id. The app has no error-tracking service. (Source: your decision, 28 Oct 2026)
- The guides get three new rules, as text only. Background jobs and schedules: a worker entry in `services.toml`, a jobs table read with `FOR UPDATE SKIP LOCKED`, and clean-up of old sessions, reset tokens and invites as the first job when a story adds jobs. Outgoing web calls: a timeout, retries only for calls that are safe to repeat, the request's correlation id, and a logged duration, with a short example for each stack. Uploads: an S3-style bucket from settings that Mainline will supply later, private files, the file's key in the database, and download links that expire soon. (Source: your decision, 28 Oct 2026)
- Both starter READMEs get a "When something breaks" section: find the error by its id, roll back, restore data, and change a leaked secret. (Source: your decision, 28 Oct 2026)
- Starter containers run as a user that is not root. The deploy guide states this for every repo. (Source: your decision, 28 Oct 2026)
- The agent's guide says to turn on GitHub's Dependabot security alerts once in each repo, and to add no Dependabot update pull requests. GitHub keeps this as a repository setting, not a file, so the guide gives the agent the one command. (Source: your decision, 28 Oct 2026; how Forge states it is the planner's choice)
- A new client repo gets all of this at `forge init`. An existing client repo gets the guide text when it upgrades, and keeps its own Dockerfile, README and packages. (Source: your decision, 28 Oct 2026)

Design: none (no screen changes)

## Why

Workers and reviewers follow the guides. Today the guides disagree with the starters in five places, so a worker who follows them writes page-number lists, USD amounts or an unpinned shadcn install. The FDE's defaults promise five parts that do not exist. No guide says how to run a background job, call another service or store a file, so each story would choose again. The starter images run as root, the starters install a formatter that nothing runs, and a client repo gets no warning when a dependency has a known security flaw.

## Done when

1. **In a new repo, the guides and the starters agree on list paging, the default currency, the shadcn version and environment names, and no guide says that Prettier runs. A new app from either starter does not install Prettier. An existing repo gets the same guide text when it upgrades.**
2. **The FDE's default answers name only parts that the starters build, and they say which parts come with a later story. Error alerts come from Mainline reading error log lines. New and existing repos get this text.**
3. **The guides give one rule each for background jobs and schedules, outgoing web calls and file uploads. New and existing repos get these rules.**
4. **A new app from either starter runs its container as a user that is not root, and its README says what to do when something breaks. The deploy guide states the non-root rule. An existing app keeps its own Dockerfile and README.**
5. **The agent's guide says to turn on GitHub's security alerts for dependencies, with no update pull requests. New and existing repos get this text.**

## Risks

Risks: none one-way. Each part reverts with its pull request. No part changes a database.

Trade-off: an app container that runs as a user that is not root cannot write into its own app folder at run time. The starters write nothing there, and the uploads rule keeps files in a bucket.

Trade-off: Forge does not turn the security alerts on by itself. The agent runs one command from the guide, in new and existing repos.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-GUIDES-1"`. Tests run the forge command and never import forge. The guide tests use the setup of `tests/test_mcp_resources_guide.py::test_3`: `new init` through `_fresh_client`, and `previous release` from `tests/fixtures/adopted-v1.2.2/client` with `forge sync` in a fix worktree, after which `git status --porcelain -uall` lists only `LISTED` files from `tests/test_setup.py`. The brief's conventions folder is the one that the brief names (`re.search(r"how-to.*?is in `([^`]+)`", brief, re.S)`, as `tests/test_built_in_defaults_guide.py` does). Compare text with whitespace collapsed.

### What exists (evidence)

- Paging. The starters use keyset cursors: `projectListQuerySchema` in `starter/libs/projects/contracts/src/index.ts` takes `limit`, `sortBy`, `sortOrder`, `after` and `before`, and `ProjectsService.list` in `starter/libs/projects/server/src/projects.service.ts` returns `paging: { limit, nextCursor, previousCursor, total, totalCapped }` with `TOTAL_CAP = 10_000`. Python has the same in `starter-python/apps/api/app/projects/schema.py` (`ProjectPaging`) and `service.py` (`TOTAL_CAP = 10_000`). The web shows "More than 10,000" (`projects-page.tsx`). The guides still say page numbers: `src/forge/standards.md` APIs ("Lists take `page` (from 1) and `limit` ... `data.pagination` (`page`, `limit`, `totalItems`, `totalPages`)"), `src/forge/templates/conventions/api.md` "Lists" (a `page`/`limit` schema and `pagination: { page, limit, totalItems, totalPages }`), `conventions/python.md` API ("Lists accept page from 1 ... `data.pagination` with page, limit, totalItems and totalPages"), and `conventions/frontend.md` (the `useOrders(page)` hook and "the page number of a list in the web address"). The database skill (`src/forge/templates/skills/database/SKILL.md`, List paging) says keyset, but caps the count at 1,000 while the code caps it at 10,000.
- Currency. `starter/libs/shared/util/src/format.ts` has `DEFAULT_CURRENCY = 'INR'`, and `starter-python/apps/api/app/core/config.py` has `DEFAULT_CURRENCY = "INR"`. The FDE defaults (`.codex/skills/forge/fde.md` and `.claude/skills/forge/fde.md`, `## Constitution defaults`) say "Currency uses USD with the currency code (USD 1,234.56)".
- Prettier. `"prettier": "3.6.2"` is a devDependency in `starter/package.json` and `starter-python/package.json`, with its entries in both `pnpm-lock.yaml` files. No script, config or ESLint rule runs it. `conventions/stack.md` says "| Lint | ESLint and Prettier | The usual pair; both run in the one `test` script |", and `conventions/python.md` Tests says "lint (ESLint, Prettier, `ruff check` and `ruff format --check`)". `tests/test_standards.py` `CARRIED_OVER_RULES["stack.md"]` pins "Prettier". `eslint-config-prettier` in the lockfile is only an optional peer of `@nx/eslint-plugin` and needs no change.
- shadcn. The app-baseline skill (`.codex/skills/app-baseline/SKILL.md` and `.claude/skills/app-baseline/SKILL.md`, shipped by `src/forge/app_baseline.py::ships`) says `npx shadcn@latest add <component>`. Everywhere else says `npx shadcn@4.21.4 add <name> --cwd libs/shared/ui` (`conventions/frontend.md`, `templates/brief.md`, `app_baseline.py`).
- Environment names. `standards.md` Errors and logs says "Environments are named `Local`, `Development`, `QA`, `UAT`, `Staging` and `Production`". The code reads `APP_ENV` in lower case and compares `development` and `test` (`starter/libs/core/server/src/mail/mail.module.ts`, `auth.controller.ts`, `session.guard.ts`; Python `app/core/mail.py`, `app/auth/routes.py`). `compose.test.yml` sets `test` and `production`, `.env.example` sets `development`, and `conventions/demo-data.md` uses `demo`.
- FDE defaults that promise unbuilt parts: "social sign-in through a hosted provider", "object storage for files", "in-app notices", "a message catalogue" and "error tracking". `tests/test_built_in_defaults_guide.py::test_6` pins the error-tracking line, the suffix " The date, time, number and money formats are built in when the app has libs/organisations or apps/api/app/organisations." and the three " Built in when ..." lines. The suffixes stay.
- Jobs. `skills/database/SKILL.md` "Job tables" says "Use a jobs table read with `SELECT ... FOR UPDATE SKIP LOCKED` ... Use pg_cron only for scheduled SQL." `conventions/deploy.md` describes `expose = "internal"` for a worker and an optional `command`. `conventions/stack.md` "Added later" says a job queue comes later and "until then the work happens inside the request". Sessions, reset tokens and invites are removed only on use, sign-out or reset.
- Outgoing calls. `conventions/backend.md` Providers says "Set a timeout on every call, retry only errors that can succeed on retry, and log each call's duration and outcome." `conventions/python.md` Errors says the same in one sentence. Neither has an example. The TypeScript correlation id lives in `correlationStorage` (`starter/libs/core/server/src/common/correlation.middleware.ts`), which `@app/core-server` does not export. Python keeps it on `request.state.correlation_id` (`app/core/security.py`) and logs through `log_event(request, level, message, module, context)` (`app/core/logging.py`). Python routes are plain `def`. `httpx` is in the Python dev group only.
- Uploads. `conventions/security.md` Uploads covers size, type from content and generated names. `conventions/python.md` Security points to it.
- Containers. `starter/Dockerfile` runs as root in one stage. `starter-python/Dockerfile` runs its second stage as root. `tests/test_starter_tree.py::test_1` pins "RUN corepack enable", "corepack pnpm install --frozen-lockfile && corepack pnpm run build" and "WORKDIR /app". `tests/test_python_starter.py::test_1` pins its lines, such as "uv sync --frozen --no-dev". The test stacks run `docker compose exec` into the API containers (`scripts/test.mjs` setup, `apps/api/test/database.e2e-spec.ts`, `one-company.e2e-spec.ts`), which then run as the same user.
- READMEs. `starter/README.md` and `starter-python/README.md` have run steps, one-company setup and "How it works", and nothing on what to do when something breaks. The members screen (`libs/organisations/web/src/pages/members-page.tsx`) revokes agent keys.
- Dependabot. GitHub turns security alerts on with `PUT /repos/{owner}/{repo}/vulnerability-alerts`. That is a repository setting, not a file. A `.github/dependabot.yml` file asks for version update pull requests, and the "Dependabot security updates" setting opens fix pull requests. Forge writes no Dependabot file and calls no Dependabot endpoint today. `forge init` already calls `gh api` for branch protection (`src/forge/init.py::protect`).
- Shipping. The standards page, the agent's guide, the FDE page, the app-baseline skill and the database skill reach a repo through `forge sync` as `.claude/` and `.codex/` copies (`LISTED` in `tests/test_setup.py`). The conventions pages are read from the installed Forge, in the folder that the brief names, so an existing repo gets them when it upgrades, with no file change. Starter files reach only a new repo, at `forge init --starter`.

### Words this story pins

GUIDES pins the paging, environment, shadcn and FDE words. RULES pins the rule texts. STARTTS and STARTPY pin the Dockerfile and README text.

- **Paging (GUIDES).**
  - `standards.md` APIs: replace the `page`/`limit` bullet with "- Lists use keyset paging. They take `limit` (20 by default, at most 100) and one cursor, `after` (the `nextCursor` of the page before) or `before` (the `previousCursor` of the page after). They return `data.items` with `data.paging` (`limit`, `nextCursor`, `previousCursor`, `total`, `totalCapped`); `total` stops at 10,000 and `totalCapped` says so. Sorting uses `sortBy` and `sortOrder` (`asc` or `desc`). Numbered pages are only for small admin screens."
  - `api.md` Lists: the schema becomes the starter's: `const cursorSchema = z.string().regex(/^[\w-]{1,2048}$/);` and `limit`, `sortBy`, `sortOrder`, `after` and `before` with the starter's `.meta` text, `.strict()` and the `.refine` with "Use after or before, not both.". Replace the next sentence with "A list returns `{ items, paging: { limit, nextCursor, previousCursor, total, totalCapped } }` as its `data`. `ProjectsService.list` in the starter builds the cursors and the capped count." The `sortBy` sentence stays.
  - `python.md` API: replace "Lists accept page from 1, limit 20 by default and at most 100, sortBy from an allowed column list, and sortOrder asc or desc. Return `data.items` and `data.pagination` with page, limit, totalItems and totalPages." with "Lists take limit (20 by default, at most 100), one cursor (after or before), sortBy from an allowed column list, and sortOrder asc or desc. Return `data.items` and `data.paging` with limit, nextCursor, previousCursor, total and totalCapped, as `app/projects/service.py` does." The sentence after it belongs to FORGE-AGENTREADY-1/GUIDE.
  - `frontend.md`: the hook becomes ``export const useOrders = (after?: string) => useQuery({ queryKey: ['orders', { after }], queryFn: () => api.get(after ? `/orders?after=${after}` : '/orders') });``, and "the page number of a list" becomes "the page cursor of a list".
  - Database skill, List paging: "cap the count at 1,000 and show "1,000+" above the cap" becomes "cap the count at 10,000 and show "More than 10,000" above the cap".
- **Environment names (GUIDES).** `standards.md` Errors and logs: replace the `Local`, `Development` bullet with "- `APP_ENV` holds the environment's name in lower case: `development` on a developer's machine, `test` in the test stack, and `demo`, `qa`, `uat`, `staging` or `production` where a project has them. A project has only the ones it uses. The starters treat every name other than `development` and `test` as deployed. Logs go to the console locally and to the host's log service elsewhere."
- **Prettier (GUIDES text, STARTTS and STARTPY packages).** `stack.md` Lint row becomes "| Lint | ESLint | The usual linter; it runs in the one `test` script |". `python.md` Tests: "lint (ESLint, `ruff check` and `ruff format --check`)". `tests/test_standards.py` `CARRIED_OVER_RULES["stack.md"]` drops "Prettier".
- **shadcn (GUIDES).** App-baseline skill: "installed with its CLI (`npx shadcn@latest add <component>`)" becomes "installed with its pinned CLI (`npx shadcn@4.21.4 add <component>`, with `--cwd libs/shared/ui` when the app has that library)".
- **FDE defaults (GUIDES).** In both `fde.md` copies:
  - "- How do people sign in?: Email and password. Social sign-in comes with the story that needs it."
  - "- How much information will it hold in a year (rows, files)?: Postgres and server-side pages. File storage comes with the story that adds uploads."
  - "- Should the app send messages (email, text, push, in-app)? About what?: Transactional email. In-app notices come with the story that needs them. No text or push messages."
  - "- Which languages and currencies, date formats, time zones?: English. A message catalogue comes with the story that adds a second language. Dates use YYYY-MM-DD and times use 24-hour format in the user's time zone. Currency uses INR with the currency code (INR 1,234.56). Numbers use comma thousands separators and a decimal point (1,234.56). The date, time, number and money formats are built in when the app has libs/organisations or apps/api/app/organisations."
  - "- Who fixes problems, and how fast must it be back up if it breaks?: Daily managed backups and no uptime promise. Each error is logged with its error id, and Mainline alerts on the error log lines; the app has no error-tracking service."
- **Jobs and schedules (RULES).**
  - Database skill, Job tables, after its two lines: "A story that adds the first job also adds the worker. The worker is the same image as a second `[[service]]` in `services.toml`, with `expose = "internal"`, a `command` that starts the worker, and no port or health path. It claims one row at a time with `SELECT ... FOR UPDATE SKIP LOCKED` in a short transaction, and marks the row done or failed with its attempt count and last error. A schedule is a pg_cron entry that only inserts a job row; the worker does the work. The first job deletes expired sessions, password reset tokens and invites, because the starters remove these rows only on use, sign-out or reset. A job fills the audit fields with the system account."
  - `deploy.md`, after the `command` sentence: "A worker for a jobs table is an `internal` service from the same Dockerfile. It does not run migrations; the `main` service runs them:" then a `toml` block with `[[service]]`, `name = "worker"`, `dockerfile = "Dockerfile"`, `expose = "internal"` and `command = "corepack pnpm run start:worker"`, then "A Python app uses `command = "uv run --no-sync python -m app.worker"`."
  - `stack.md` Added later: the job-queue bullet becomes "- A queue server (for example BullMQ): add when a story's New moving parts names it. Until then, work that must outlive a request goes in a jobs table that a worker reads, as the database skill's Job tables section says."
- **Outgoing web calls (RULES).**
  - `backend.md` Providers: replace "Set a timeout on every call, retry only errors that can succeed on retry, and log each call's duration and outcome." with "Call the vendor with the platform's `fetch`. Every call has a timeout, sends the request's correlation id, and logs its duration and outcome. Retry only a call that is safe to repeat (GET, PUT, DELETE, or a POST with an idempotency key), and only after a network error, a 429 or a 5xx: at most two more tries, after 0.5 and 2 seconds. The story that adds the first provider exports `correlationStorage` from `@app/core-server`." Then this block:
    ```ts
    const started = Date.now();
    const response = await fetch(`${this.baseUrl}/rates`, {
      headers: { 'x-correlation-id': correlationStorage.getStore() ?? '' },
      signal: AbortSignal.timeout(10_000),
    });
    this.logger.log('Rates fetched', 'RatesProvider', { status: response.status, durationMs: Date.now() - started });
    ```
    "Payment and notification provider calls are idempotent." stays, because `CARRIED_OVER_RULES` pins "idempotent".
  - `python.md` Errors, after the provider sentence: "Call the vendor with httpx; the story that adds the first provider moves `httpx` from the dev group to the dependencies. Retry as backend.md says." Then this block:
    ```python
    started = time.monotonic()
    with httpx.Client(timeout=10.0) as client:
        response = client.get(f"{self.base_url}/rates",
                              headers={"x-correlation-id": request.state.correlation_id})
    log_event(request, "info", "Rates fetched", "rates",
              {"status": response.status_code, "durationMs": round((time.monotonic() - started) * 1000)})
    ```
- **Uploads (RULES).** `security.md` Uploads, after its paragraph: "Keep files in an S3-compatible bucket, never on the container's disk, because each release starts a new container. Read the bucket from settings: `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY`. Mainline will supply them later; until then, the FDE sets them for each client. Objects are private. Store the object's key in the database, never a URL. A download is a signed link that expires in 5 minutes or less, made after the record's permission check. Use `@aws-sdk/client-s3` with `@aws-sdk/s3-request-presigner` in a Node app, or `boto3` in a Python app. The story that adds uploads adds MinIO to the dev compose file."
- **Non-root rule (RULES).** `deploy.md`, after the `.dockerignore` sentence: "The image runs the app as a user that is not root. The starters switch to `USER node` (TypeScript) or a created `app` user (Python) before they install packages. Keep that order when you change the Dockerfile."
- **Security alerts (RULES).** `skill.md`, at the end of `## Refresh dependencies`: "GitHub's Dependabot security alerts tell the owner when a dependency has a known flaw. Turn them on once in each repo, after `forge init` or an upgrade: `gh api --method PUT repos/{owner}/{repo}/vulnerability-alerts`. Add no `.github/dependabot.yml`, and leave Dependabot security updates off, because their pull requests skip Forge's lanes. Fix an alert with a refresh fix or `forge start`."
- **TypeScript Dockerfile (STARTTS).** The lines before `ENV NODE_ENV=production` become:
  ```dockerfile
  FROM node:24-bookworm-slim

  RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/*
  ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
  RUN corepack enable && mkdir /app && chown node:node /app
  USER node
  WORKDIR /app
  COPY --chown=node:node . .
  RUN corepack pnpm install --frozen-lockfile && corepack pnpm run build
  ```
  The install runs as `node`, so Corepack's pnpm and the store are in the node user's home, and `start:prod` needs no download.
- **Python Dockerfile (STARTPY).** The second stage becomes:
  ```dockerfile
  FROM python:3.14-slim-bookworm
  COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /uvx /bin/
  RUN useradd --create-home --uid 10001 app && mkdir -p /app/apps/api && chown -R app:app /app
  USER app
  WORKDIR /app/apps/api
  COPY --chown=app:app apps/api/pyproject.toml apps/api/uv.lock ./
  RUN uv sync --frozen --no-dev
  COPY --chown=app:app apps/api/ ./
  COPY --from=web-build --chown=app:app /app/apps/web/dist /app/apps/web/dist
  ```
  The first stage is a build stage and stays as it is.
- **README section (STARTTS and STARTPY).** At the end of each starter README:
  ```markdown
  ## When something breaks

  1. Find the error. A failed request answers with an `errorId`, and the API's error log line has the same `errorId` and the request's `correlationId`. Search Mainline's logs for the `errorId`, then for the `correlationId` to see the rest of that request.
  2. Go back to the last good release. Roll back in Mainline. A rollback keeps the database, so each migration must work with the release before it.
  3. Restore data only when data is lost or wrong. Restore the newest good daily snapshot in Mainline. Changes made after that snapshot are lost, so tell the client first.
  4. Change a leaked secret. Make a new value where the secret comes from, set it in Mainline for each environment, redeploy, and then cancel the old value. An admin revokes a leaked agent key on the Members screen and makes a new one.
  ```
- **Prettier packages (STARTTS and STARTPY).** Remove `"prettier": "3.6.2"` from the starter's `package.json` and run `COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm install --lockfile-only` in the starter folder. The lockfile diff removes only the `prettier` entries.

### Done-when details

1. Guides agree (GUIDES), packages agree (STARTTS, STARTPY).
   - Test `tests/test_guides_agree.py::test_1_the_guides_say_what_the_starters_do`, parameters `new init` and `previous release`.
     - Both synced standards copies have the keyset bullet and the `APP_ENV` bullet, and have no `totalPages` and no `` `Local`, `Development` ``.
     - Both synced app-baseline copies have `npx shadcn@4.21.4 add <component>` and no `shadcn@latest`.
     - Both synced database skill copies have "More than 10,000" and no "1,000+".
     - Both synced FDE copies have "Currency uses INR" and no "USD".
     - The brief's conventions folder: `api.md` has `nextCursor` and no `totalPages`; `python.md` has `data.paging` and no `data.pagination`; `frontend.md` has no `?page=`; no conventions page has "Prettier".
   - `tests/test_standards.py`: drop "Prettier" from `CARRIED_OVER_RULES["stack.md"]`.
   - Packages: STARTTS adds to `tests/test_starter_tree.py::test_1` that the starter's `package.json` has no `prettier` key in any dependency group and `pnpm-lock.yaml` has no `prettier@`. STARTPY adds the same to `tests/test_python_starter.py::test_1` for the new client. The `adopted` case of that test checks that the adopted app's `package.json` is unchanged after upgrade and sync.
2. FDE defaults (GUIDES).
   - Test `tests/test_guides_agree.py::test_2_the_fde_defaults_promise_only_built_parts`, parameters `new init` and `previous release`. Both synced FDE copies have the five pinned lines, and no copy has "social sign-in through", "object storage for files", "and in-app notices", "and a message catalogue" or "error tracking,".
   - `tests/test_built_in_defaults_guide.py::test_6`: its error-tracking assert becomes the new "Who fixes problems" line. Its suffix checks keep passing.
3. The three rules (RULES).
   - Test `tests/test_guides_agree.py::test_3_the_guides_hold_the_jobs_calls_and_uploads_rules`, parameters `new init` and `previous release`.
     - Both synced database skill copies have the worker sentence, "FOR UPDATE SKIP LOCKED" and the clean-up sentence.
     - The brief's conventions folder: `deploy.md` has the worker block; `stack.md` has the new queue bullet; `backend.md` has `AbortSignal.timeout(10_000)` and `x-correlation-id`; `python.md` has `httpx.Client(timeout=10.0)`; `security.md` has `S3_BUCKET`, "never a URL" and "5 minutes or less".
   - `_logger_example_writes_the_documented_fields` in `tests/test_standards.py` runs the documented TypeScript logger from `backend.md`. It takes the first `this.logger.log(` line, which is the existing one in Logs. Keep the new block in Providers, after it, so the check keeps passing.
4. Containers and READMEs (STARTTS, STARTPY), the deploy rule (RULES).
   - TypeScript app case, in `starter/apps/api/test/api.e2e-spec.ts`: `the API container runs as a user that is not root`. It runs `docker compose -f compose.test.yml exec -T api id -u` with `spawnSync`, as `database.e2e-spec.ts` does, and expects status 0 and an output that is not `0`. STARTTS adds the name to `API_SECURITY_TESTS` in `tests/test_starter_tree.py`, so the live run requires it.
   - Python app case, in `starter-python/apps/api/tests/test_api.py`: `test_the_api_container_runs_as_a_user_that_is_not_root`, with `subprocess.run` as `tests/conftest.py` does. STARTPY adds the name to `API_SECURITY_TESTS` in `tests/test_python_starter.py`.
   - The live runs also prove that the images build, migrate and serve as that user, because `compose.test.yml` builds the Dockerfile for all three API instances and `scripts/test.mjs` runs the one-company setup through `docker compose exec`.
   - Static checks: STARTTS adds to `tests/test_starter_tree.py::test_1` that the Dockerfile has `USER node` before the `pnpm install` line and has `COPY --chown=node:node . .`, and that `README.md` has `## When something breaks` and its four steps. STARTPY adds to `tests/test_python_starter.py::test_1` that the new client's Dockerfile has `USER app` before `uv sync --frozen --no-dev` and that its README has the section. The existing pinned lines keep passing.
   - Existing repos (RULES): `tests/test_guides_agree.py::test_4_an_existing_repo_gets_the_non_root_rule_and_keeps_its_app_files`, parameter `previous release`. After sync, the fixture's `Dockerfile`, `README.md` and `package.json` are unchanged, and the brief's `deploy.md` has the non-root sentence. The new-repo side of this item is the starter tests above.
5. Security alerts (RULES).
   - Test `tests/test_guides_agree.py::test_5_the_guide_turns_on_security_alerts_only`, parameters `new init` and `previous release`. Both synced agent's guide copies have the alerts paragraph with `repos/{owner}/{repo}/vulnerability-alerts`, and the repo has no `.github/dependabot.yml`.

### New and existing repos

- **New repos** (`forge init --starter`, `forge init --starter python`): the guide text, the FDE defaults, the non-root Dockerfile, the README section and no Prettier. Plain `forge init` gets the guide text only.
- **Existing repos** (on upgrade, after `forge sync`): the standards, agent's guide, FDE, app-baseline and database skill copies, and the conventions text from the installed release. Their Dockerfile, README, `package.json` and lockfile do not change. The deploy guide's non-root sentence tells a worker the rule when it changes the Dockerfile. Each item has a `previous release` case on the adopted earlier-release fixture.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| GUIDES | The guides match the starters and name only built parts | The cursor paging text, the lower-case environment names, the pinned shadcn command, the Prettier lines gone from the guides, the 10,000 cap in the database skill, and the five FDE default lines, with the synced copies. | 1, 2 | `src/forge/standards.md`, `src/forge/templates/conventions/api.md`, `src/forge/templates/conventions/python.md` (API paging and Tests lines), `src/forge/templates/conventions/frontend.md`, `src/forge/templates/conventions/stack.md` (Lint row), `src/forge/templates/skills/database/SKILL.md` (List paging), `.codex/skills/app-baseline/SKILL.md`, `.claude/skills/app-baseline/SKILL.md`, `.codex/skills/forge/fde.md`, `.claude/skills/forge/fde.md`, `.claude/skills/forge/standards.md`, `.codex/skills/forge/standards.md`, `.claude/skills/database/SKILL.md`, `.codex/skills/database/SKILL.md` (rewritten by `forge sync`), `tests/test_guides_agree.py` (new), `tests/test_standards.py`, `tests/test_built_in_defaults_guide.py` | `tests/test_guides_agree.py::test_1`, `test_2` (new); `tests/test_standards.py` (`CARRIED_OVER_RULES`); `tests/test_built_in_defaults_guide.py::test_6` (assert) | FORGE-AGENTREADY-1/GUIDE | no | |
| RULES | Rules for jobs, outgoing calls, uploads, non-root images and security alerts | The jobs, outgoing-call and uploads rules with their examples, the worker entry and non-root sentence in the deploy guide, the queue bullet, and the security-alerts paragraph in the agent's guide, with the synced copies. | 3, 4, 5 | `src/forge/templates/skills/database/SKILL.md` (Job tables), `src/forge/templates/conventions/deploy.md`, `src/forge/templates/conventions/stack.md` (Added later), `src/forge/templates/conventions/backend.md` (Providers), `src/forge/templates/conventions/python.md` (Errors), `src/forge/templates/conventions/security.md`, `src/forge/templates/skill.md` (Refresh dependencies), `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md`, `.claude/skills/database/SKILL.md`, `.codex/skills/database/SKILL.md` (rewritten by `forge sync`), `tests/test_guides_agree.py` | `tests/test_guides_agree.py::test_3`, `test_4`, `test_5` | GUIDES | no | |
| STARTTS | The TypeScript starter runs as non-root, says what to do when it breaks, and drops Prettier | The non-root Dockerfile, the README section, Prettier gone from the package and the lockfile, and the app case. | 1, 4 | `src/forge/templates/starter/Dockerfile`, `src/forge/templates/starter/README.md`, `src/forge/templates/starter/package.json`, `src/forge/templates/starter/pnpm-lock.yaml`, `src/forge/templates/starter/apps/api/test/api.e2e-spec.ts`, `tests/test_starter_tree.py` | `tests/test_starter_tree.py::test_1` (static checks and `API_SECURITY_TESTS`), `apps/api/test/api.e2e-spec.ts` (the non-root case, through the live run) | | no | |
| STARTPY | The Python starter runs as non-root, says what to do when it breaks, and drops Prettier | The same in the Python starter. | 1, 4 | `src/forge/templates/starter-python/Dockerfile`, `src/forge/templates/starter-python/README.md`, `src/forge/templates/starter-python/package.json`, `src/forge/templates/starter-python/pnpm-lock.yaml`, `src/forge/templates/starter-python/apps/api/tests/test_api.py`, `tests/test_python_starter.py` | `tests/test_python_starter.py::test_1` (static checks and `API_SECURITY_TESTS`), `tests/test_api.py` (the non-root case, through the live run) | | no | |

GUIDES waits for FORGE-AGENTREADY-1/GUIDE, because both change `standards.md` (APIs), `api.md`, the same `python.md` API paragraph and the synced standards copies. RULES waits for GUIDES, because they share `python.md`, `stack.md`, the database skill and `tests/test_guides_agree.py`. RULES also changes `backend.md`, `python.md` and `skill.md`, which FORGE-AGENTREADY-1/GUIDE changes; GUIDES already waits for it. STARTTS and STARTPY share no file with each other or with FORGE-AGENTREADY-1, so they can start now.

New moving parts: none. The jobs, calls and uploads rules are text; the story that first needs one adds its worker, provider or bucket.

## Notes

- **Order with other work.**
  - FORGE-AGENTREADY-1/GUIDE changes `standards.md` APIs and Data, `backend.md`, `python.md`, `api.md`, `skill.md`, `brief.md` and `docs/guide.md`. GUIDES and RULES wait for it, as the Tasks table says. Its `python.md` change ("Follow the standards page's versioning and Idempotency-Key rules.") is the sentence right after the paging sentence that GUIDES changes.
  - FORGE-MAIL-1 changes both starter READMEs (local run steps and the mail text), the TypeScript `package.json` and `pnpm-lock.yaml` (nodemailer), the compose files and the mail settings. The part that merges later runs `corepack pnpm install --lockfile-only` again and keeps both README changes. FORGE-MAIL-1 owns the "Transactional email" default; GUIDES keeps those two words.
  - FORGE-REQLOG-1 changes `standards.md` Errors and logs (where the `APP_ENV` bullet sits), the Logs sections of `backend.md` and `python.md`, and may change the FDE's "Who fixes problems" line. GUIDES owns that FDE line with the text above, so FORGE-REQLOG-1 does not change it again. The `backend.md` logger example reads `process.env.NODE_ENV`, while the code reads `APP_ENV`. That is in the Logs section, so it is left to FORGE-REQLOG-1.
- **Scores (F x H >= 2 x C).**
  - Guide contradictions (paging, currency, Prettier text, shadcn, environment names): 3 x 2 = 6 >= 2. Kept.
  - The database skill's 1,000 cap against the code's 10,000: part of the same fix, with no extra cost. Kept.
  - FDE defaults that promise unbuilt parts: 3 x 2 = 6 >= 2. Kept.
  - Prettier removed from both starters: 3 x 1 = 3 >= 2 (one line and a lockfile in each). Kept.
  - Jobs rule: 2 x 2 = 4 >= 2. Kept. A jobs table, a worker or the clean-up job in the starters now: cut; the first story with a job adds them.
  - Outgoing-call rule with an example for each stack: 2 x 2 = 4 >= 2. Kept. A shared fetch helper in the starters: cut; the first provider adds it.
  - Uploads rule: 2 x 2 = 4 >= 2. Kept. MinIO in the dev compose file now: cut; the uploads story adds it.
  - Non-root containers: 3 x 1 = 3 >= 2. Kept. The skeleton Dockerfile for plain `forge init`: cut, because the owner named the starter containers, and the deploy guide's sentence covers other apps.
  - README "When something breaks": 1 x 2 = 2 >= 2. Kept for new apps. The same section for existing apps: cut, because Forge does not change an app's own files on upgrade.
  - Security alerts as one paragraph in the agent's guide: 2 x 2 = 4 >= 2. Kept. `forge init` calling the alerts endpoint: cut, because the text covers new and existing repos with no code, and a second GitHub write at init adds a failure path (choose the simplest option).
- **Owner decisions (28 Oct 2026, settled).** Cursor paging in the guides; INR; remove Prettier and its claims; the app-baseline skill names the pinned shadcn version; environment names match the code; the FDE defaults that promise unbuilt parts say that they come with the story that needs them; text-only rules for jobs and schedules, outgoing calls and uploads, with bucket settings that Mainline will supply later; a "When something breaks" section in both starter READMEs; non-root starter containers; Dependabot security alerts only, with no update pull requests.
- **Planner choices the owner did not make.**
  1. The environment fix is on the guide side: lower-case names as the code reads them, with `development` for a developer's machine. No code changes.
  2. The database skill's count cap changes from 1,000 to 10,000 to match the code.
  3. Security alerts are one agent step in the agent's guide (`gh api --method PUT repos/{owner}/{repo}/vulnerability-alerts`), not a `forge init` call. Dependabot security updates stay off, and no `dependabot.yml` is added.
  4. The bucket setting names are `S3_ENDPOINT`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY`. Signed links last 5 minutes or less. The libraries are `@aws-sdk/client-s3` with its presigner, and `boto3`.
  5. Retries: at most two more tries, after 0.5 and 2 seconds, only for GET, PUT, DELETE or a POST with an idempotency key, and only after a network error, a 429 or a 5xx. The example timeout is 10 seconds.
  6. The worker rule keeps the attempt count and last error on the job row, and a schedule only inserts job rows.
  7. The Python image's user is `app` with uid 10001; the TypeScript image uses the image's `node` user.
  8. The README section has four steps: find the error by its id, roll back, restore a snapshot, and change a leaked secret, including an agent key.
  9. The FDE's "Transactional email" words stay, for FORGE-MAIL-1. The uploads default ("No uploads; if a story needs them, set a 10 MB limit and use S3-compatible storage.") already says that a story adds them, so it stays.
  10. The skeleton Dockerfile for plain `forge init` stays as it is.
  11. The non-root proof is one app case in each starter that runs `id -u` in the API container.
- No client repo is named in this story's code, tests, texts or commits.
