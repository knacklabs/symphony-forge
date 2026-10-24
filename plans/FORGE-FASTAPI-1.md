# FastAPI starter for Python backends

2 parts · Risks: none one-way · New moving parts: FastAPI, SQLAlchemy, Alembic, uv, import-linter, Pydantic, ruff and mypy in the new Python starter; openapi-typescript for its web app's API types

## What changes for you

- A new client app whose backend is Python starts from a runnable FastAPI app with the TypeScript starter's fixed rules: one app split into modules, each module owning its tables, other modules using it only through its public service, uv, SQLAlchemy with Alembic on Postgres, and tests end to end first (pytest HTTP tests on a real database, Playwright for the React UI).
- The agent sets up the repo with `forge init --starter python`. `forge init --starter` still gives the TypeScript starter.
- The Python app uses the same React web app as the TypeScript starter, with the same screens and browser tests. The repo keeps the Python API in `apps/api` as a uv project, and the web app and its shared types in a pnpm workspace next to it. One test command runs both, and one image holds both.
- The web app gets its API types from the API's OpenAPI schema, so the tests fail when the two sides do not agree. The API checks its input with Pydantic, and the web forms keep zod.
- An import-linter contract fails the tests when one module imports another module's internals, as Nx's module-boundary lint does in the TypeScript starter.
- The one test command also runs ruff (lint and format check) and mypy in strict mode on the Python code, as ESLint, Prettier and the type check do in the TypeScript starter.
- The app deploys as the TypeScript starter does: one image, `GET /health`, port 3000, and migrations before the server starts.
- forge init picks this starter only when the owner asks for a Python backend, and the constitution lists the fixed rules without asking about them.
- Workers in a Python app read one Python page with the same rules as the NestJS and Prisma pages, in Python terms.
- An existing client app keeps its stack, Dockerfile and test command on upgrade or sync.

Design: none (no new screens; the Python starter uses the TypeScript starter's web app as it is)

## Why

A Python backend has no starter today, so each Python client app starts from nothing and its module, database and test rules depend on the agent that builds it. The shipped convention pages show only NestJS and Prisma code, so a worker in a Python app has no example to follow. On 24 October 2026 the owner chose a FastAPI starter with the same fixed rules as the TypeScript starter, on uv, SQLAlchemy, Alembic and Postgres, with an import-linter contract, end-to-end tests first, and the TypeScript starter's web app.

## Done when

1. **A new client app whose owner asks for a Python backend gets from `forge init --starter python`, in its first commit, one app split into modules: a FastAPI API on uv, with sign-in and the example records as separate modules that each own their tables, SQLAlchemy models and Alembic migrations on Postgres, and the TypeScript starter's React web app. This works from an installed Forge as from its source. The app's test command runs lint, format and strict type checks, API tests against the running API and a real database, browser tests and the module check, and they pass. One account never sees or changes another account's records, and a deployed app never writes a password-reset link or token to its log. Its image runs the migrations, then answers `GET /health` on port 3000. The guide tells the agent to use this starter only when the owner asks for a Python backend, and to copy its fixed rules into the constitution without a question about them. New repos get the guide at init, and existing repos on upgrade and sync.**
2. **In that app, the tests fail when one module imports another module's internal files, and the failure names the module rule.**
3. **In that app, the web app's API types come from the API's OpenAPI schema, and the tests fail when the API changes a field that the web app uses.**
4. **The worker brief tells a worker in a Python app to read one Python page. The page gives the shipped rules in Python terms: the layout, public module services, Pydantic validation, the error envelope and codes, JSON logs with the correlation id, SQLAlchemy models with UUID ids, `_at_utc` times, money in the smallest unit, soft delete, Alembic migrations, ruff and mypy, and end-to-end pytest tests. New repos get this at init, and existing repos on upgrade and sync.**
5. **An existing client app keeps its stack, Dockerfile and test command after upgrade and sync, and gets no starter file.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request. A client app owns its copy of the
starter after set-up, so no existing app changes.

Allowance: the part that adds the Python starter goes over the 400-line part limit. Most of its
lines are the two lockfiles (uv and pnpm) and the API code that matches the TypeScript starter's
API. Approving this story gives that one part permission to go over the limit. When close asks
the size question for it, the answer is this approval. The other part keeps the limit.

Trade-off: the Python starter keeps its own copy of the web app's root files (its package list,
lockfile and lint settings). When the TypeScript starter changes a web dependency, a fast test
fails until the Python starter's copy has the same version.

Trade-off: a developer machine for a Python app needs Node 24, uv and Docker, because the web app
is the TypeScript starter's.

Trade-off: the starter's limit on sign-in attempts counts in each running instance, not across
instances. A story that runs more than one instance adds a shared limit when it names Redis.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-FASTAPI-1"`. One test per Done-when item, named
`test_<n>_...`. Each test runs the forge command or, for the starter's own behaviour, reads the
starter's files or runs the starter's own commands, and never imports forge. Forge-command tests
run on a new repo (`_fresh_client` in `tests/test_setup.py`) and on
`tests/fixtures/adopted-v1.2.2` moved to this release (the `client` fixture of
`tests/test_notes_first_discovery.py`). Only the existing stubs are faked: GitHub (`gh`) and the
Claude worker (`install_claude`, `calls` from `tests/test_worker.py`).

**Plan against the merged React defaults starter.** STARTER starts after
FORGE-REACTDEFAULTS-1/STARTER merges. That part changes `apps/web` (React Compiler, the data
router, the route error page, two new browser flows), the root `package.json`, `pnpm-lock.yaml`,
`eslint.config.mjs` and `BROWSER_FLOWS` in `tests/test_starter_tree.py`. Read the merged starter
first; where a path below differs from the merged tree, follow the merged tree.

**No network in the main CI.** The fast halves read files only, and test 1's wheel case builds the
wheel offline with `uv build`, as `tests/test_starter_app.py` test_3 does. The live halves
(`uv sync`, `pnpm install`, Postgres, Playwright, the Docker build) run only when
`FORGE_STARTER_LIVE=1`, read at collection time as `LIVE` in `tests/test_starter_tree.py`.
`.github/workflows/starter-smoke.yml` gets a second job, `python-starter-smoke`, the same shape as
`starter-smoke` (Node 24, `astral-sh/setup-uv@v6`, `timeout-minutes: 30`), which runs
`tests/test_python_starter.py`. Its `paths` add `src/forge/templates/starter-python/**`,
`src/forge/templates/skeleton/.dockerignore`, `src/forge/init.py` and
`tests/test_python_starter.py`. `src/forge/templates/starter/**` is already there, and it also
starts the new job, because the Python starter uses the React starter's `apps/web`.

**Words this story pins.**

- The tree lives in `src/forge/templates/starter-python/`. `forge init --starter python` writes,
  from the React starter, `apps/web/**`, `tsconfig.base.json` and `.npmrc`, then every file of
  `starter-python/`. The two sets do not overlap. Init still writes a file only where none is
  there, in the one first commit, and the Dockerfile of `starter-python/` replaces the
  skeleton's, as the React starter's does today.
- Layout of `starter-python/`:

  ```
  package.json            web scripts and the root test script; pnpm pinned; no Nx, NestJS or Prisma
  pnpm-lock.yaml
  pnpm-workspace.yaml     packages: apps/web, libs/shared
  eslint.config.mjs       the React starter's, without the @nx block
  libs/shared/            @app/shared: the zod form schemas (as the React starter's) and the API
                          types: openapi.json and src/api-types.ts, both generated and committed
  apps/api/
    pyproject.toml        uv project: exact pins, [tool.importlinter], [tool.ruff], [tool.mypy],
                          [tool.pytest.ini_options]
    uv.lock
    .python-version       3.14
    alembic.ini
    migrations/           env.py, script.py.mako, versions/0001_initial.py
    app/main.py           the FastAPI app: middleware, error handlers, routers, /health, the web build at /
    app/openapi.py        writes the app's OpenAPI schema to the path it is given
    app/core/             config, database (Base, the session dependency), errors, envelope, JSON logs,
                          correlation id, security headers, rate limit
    app/auth/             sign-in: models.py (account, session, password_reset_token), schema.py,
                          routes.py, service.py, mail.py
    app/projects/         the example records: models.py (project), schema.py, routes.py, service.py
    tests/                conftest.py and test_api.py, against the running API
  compose.test.yml        database, api, production-api, as the React starter's
  scripts/test.mjs        the one test command
  Dockerfile
  .gitignore              the React starter's, plus .venv/, __pycache__/ and .pytest_cache/
  .env.example
  README.md
  ```

  Each module's `__init__.py` is its public entry. `app.auth` exports `router`,
  `current_account` and `AccountPrincipal`; `app.projects` exports `router` and
  `ProjectService`; `app.core` exports what the modules use. Nothing imports another package's
  other files.
- The import contracts, in `apps/api/pyproject.toml`: `root_package = "app"`, and one `protected`
  contract for each of `app.core`, `app.auth` and `app.projects`, named `<name> internals`
  (`core internals`, `auth internals`, `projects internals`), with
  `protected_modules = ["app.<name>.*"]`, `allowed_importers = ["app.<name>"]` and
  `broken_contract_guidance = "A module uses another module only through its public service in its __init__.py, never through its internal files."`
  (import-linter 2.14 or later has `broken_contract_guidance`).
- Root scripts in `package.json`: `api-types` (`uv --directory apps/api run python -m app.openapi
  ../../libs/shared/openapi.json`, then `openapi-typescript libs/shared/openapi.json -o
  libs/shared/src/api-types.ts`); `build` (the web app only, with Vite); `lint` (ESLint and
  Prettier as in the React starter, then `uv --directory apps/api run ruff check` and
  `uv --directory apps/api run ruff format --check`); `typecheck` (the web app and `libs/shared`,
  then `uv --directory apps/api run mypy`); `test:imports` (`uv --directory apps/api run lint-imports`);
  `test:api` (`uv --directory apps/api run pytest --junitxml=../../test-results/api.xml`);
  `test:hooks`; `test:browser`; and `test`, which runs `api-types`, `lint`, `typecheck`,
  `test:imports`, `test:api`, `test:hooks` and `test:browser` in that order through
  `corepack pnpm run`.
- `apps/api/pyproject.toml`: `[tool.mypy]` has `strict = true`, `plugins = ["pydantic.mypy"]`
  and `files = ["app", "tests"]`; `[tool.ruff]` keeps ruff's default rules and sets only
  `target-version = "py314"`. The starter's own code passes both with no `# type: ignore` and no
  `# noqa`.
- forge.toml's `test` for both starters is `node scripts/test.mjs`.
- The option (STARTER): `--starter` takes `nargs="?"`, `const="react"`,
  `choices=["react", "python"]`, help `start a new app from a starter: react (the default) or
  python (a FastAPI backend)`. `forge init --starter` behaves as today, and so do its two
  refusals.
- Python page (GUIDE): `src/forge/templates/conventions/python.md`. The brief sentence:
  `In an app with a FastAPI backend, open python.md there for the backend, API, database,
  security, test and deploy concerns. The rules of the other pages apply to it, and their NestJS
  and Prisma code does not.`
- Dependencies, exact, each the newest stable release that was at least two weeks old on
  24 October 2026: `fastapi` 0.143.0, `pydantic` 2.14.0, `sqlalchemy` 2.1.4, `alembic` 1.20.0,
  `uvicorn` 0.54.0, `psycopg[binary]` 3.3.6; dev `pytest` 9.1.1, `httpx` 0.28.1, `import-linter`
  2.15, `ruff` 0.17.0, `mypy` 2.4.0; npm dev `openapi-typescript` 7.13.0; uv 0.13.0 in the Dockerfile. Python 3.14, not 3.15:
  3.15 is three weeks old, and its binary wheels may be missing. If uv cannot resolve this set,
  take the newest older release that resolves and say so in the pull request. Every other web
  package has the React starter's version.

### Done-when details

1. The Python starter, set up by init (STARTER).
   - The HTTP contract is the React starter's API, so `apps/web` and its Playwright flows run
     with no change: the same paths under `/api/v1` (`auth/sign-up`, `auth/sign-in`, `auth/me`,
     `auth/sign-out`, `auth/forgot-password`, `auth/reset-password`, `projects`,
     `projects/{id}`), `GET /health` outside the prefix, the same status codes, the envelope
     `{ success, data, error }` with `errorId` on errors, `VALIDATION_ERROR` as 400 with
     `details.fieldErrors` of `{ field, reason }`, `CSRF_CHECK_FAILED` as 403, 404 for another
     account's project, the `starter_session` and `starter_csrf` cookies and the `x-csrf-token`
     and `x-correlation-id` headers, the list query (`page`, `limit`, `sortBy` on the allowed
     columns, `sortOrder`) and its `{ items, pagination }` result, camelCase JSON field names,
     Swagger at `/api/docs`. Read the React starter's API code for each rule.
   - Pydantic models in each module's `schema.py`: `extra="forbid"`, `str_strip_whitespace=True`,
     `alias_generator=to_camel`, `populate_by_name=True`, and a maximum length on every string.
     The `schema.py` name also matches the fix lane's `**/schema.*` interface glob.
   - SQLAlchemy 2 typed models with sync sessions over psycopg. Tables and columns are
     snake_case and singular (`project`, `created_at_utc`), so no name needs a mapping. UUID ids,
     the audit fields, soft delete on `project`. Foreign keys across modules name the table as a
     string and import nothing. One Alembic history in `apps/api/migrations/`, which matches the
     `**/migrations/**` interface glob; `0001_initial.py` creates the four tables and their
     indexes. `env.py` imports `app.auth` and `app.projects` and uses `Base.metadata` from
     `app.core`.
   - Config: `app/core/config.py` reads `DATABASE_URL`, `APP_ENV`, `APP_ORIGIN` and `PORT`
     once, at start-up (FastAPI lifespan), and stops the app with a clear message when one is
     missing. It turns a `postgresql://` URL into `postgresql+psycopg://`, because the platform
     supplies the first. Importing `app.main` reads no variable and opens no connection, so
     `python -m app.openapi` runs with no database.
   - Passwords with `hashlib.scrypt`. Sign-up, sign-in, forgot and reset password are limited to
     30 requests a minute for each client address, in memory
     (`# ponytail: per instance; a shared limit comes with Redis`). The mail provider writes the
     reset link to the log only when `APP_ENV` is `development` or `test`, as in the React
     starter. A middleware sets the headers that helmet 8 sets by default in the React starter.
     CORS allows only `APP_ORIGIN`.
   - The app serves `apps/web/dist` at `/`, with `index.html` for a `GET` that accepts HTML and
     is not under `/api` or `/health`.
   - `Dockerfile`: a Node 24 stage runs `corepack pnpm install --frozen-lockfile && corepack pnpm
     run build`; a `python:3.14-slim-bookworm` stage copies uv 0.13.0 from its image, runs
     `uv sync --frozen --no-dev` in `/app/apps/api`, copies the web build to
     `/app/apps/web/dist`, has `EXPOSE 3000`, and its CMD runs `uv run --no-sync alembic upgrade
     head` (on failure the React starter's message and `exit 1`), then `exec uv run --no-sync
     uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-3000}" --no-access-log`. Uvicorn's
     access log writes each request path with its query string, and the reset page's address
     holds the reset token, so the starter has no access log, as the React starter has none. `compose.test.yml` health checks
     use Python's `urllib`.
   - `skeleton/.dockerignore` gets `**/.venv` and `**/__pycache__`. Plain `forge init` and the
     React starter get these two lines too, and they change nothing for a Node app.
   - `scripts/test.mjs`: the React starter's, with `uv --directory apps/api sync --frozen` after
     the pnpm install and without `scripts/test-build.mjs`. It ends with `GET /health returned
     200`.
   - `apps/api/tests/test_api.py` has the cases of the React starter's
     `apps/api/test/api.e2e-spec.ts`, one function each, against `API_TEST_URL` and
     `PRODUCTION_API_TEST_URL`: sign up, sign in and sign out; create, list, read, update and
     delete a project; `test_account_isolation_...`; forgot-password gives the same answer for
     known and unknown addresses; reset a password once; invalid input; a whitespace-only name;
     sign-in and CSRF before project changes; a cross-origin sign-in;
     `test_production_forgot_password_does_not_log_a_reset_link`. That last one, on the
     production API: sign up; ask for a reset for that account and for an unknown address (the
     same status and body); then `GET /reset-password?token=<a fixed 43-character test token>`,
     which serves the web app. `docker compose logs production-api` then has neither
     `/reset-password` nor the test token. Each test creates its data through the API.
   - `src/forge/init.py`: the option above; one helper gives the file list of each starter, and
     both the refusal check and `_scaffold` use it.
   - `skill.md` (the option is a coordinator's command, so it changes in this part): the "Set up
     a new repo" row becomes `Use \`forge init --starter\` for a new React app, and \`forge init
     --starter python\` for a new app whose owner asks for a Python backend. Use \`forge init\` for
     any other stack, then propose a \`fast_test\` as in step 9 of Adopt a live app, below`. In App
     constitution, "A FastAPI backend has no starter yet." becomes `A FastAPI backend starts from
     forge init --starter python.` In App constitution, after the sentence "In an app whose tests
     run Nx's module-boundary lint, copy the fixed rules into the constitution's ## Fixed rules
     section, and ask nothing about them.", add `In an app made from the Python starter, whose
     tests run import-linter, copy these fixed rules into ## Fixed rules instead, and ask nothing
     about them:` and the four lines:

     ```
     - One app split into modules: a FastAPI API on uv, with SQLAlchemy and Alembic on Postgres, and a React web app on pnpm.
     - Each module owns its tables, in its own models file.
     - A module uses another module only through its public service, never through its tables.
     - The tests run import-linter, so an import of another module's internal files fails them.
     ```

     The sentences that `tests/test_notes_first_discovery.py` test_5 pins stay word for word.
   - README: how to run it, and a short "How it works" that names the modules, the rule, the
     import check and the API types.
   - Test: `tests/test_python_starter.py::test_1_a_python_backend_app_starts_from_the_fastapi_starter`,
     `@pytest.mark.platform`, `@pytest.mark.timeout(1800)`, with `case` in ("new", "wheel", "adopted").
     - new: `_fresh_client(repo, gh, tmp_path, "--starter", "python")` exits 0. The first commit
       has every file of `starter-python/` and the three React starter paths, byte for byte, and
       no `apps/api/src/`, `libs/auth/`, `prisma.config.ts` or `nx.json`. forge.toml's `test` is
       `node scripts/test.mjs`. For `.claude` and `.codex`, `skills/forge/SKILL.md` has
       `forge init --starter python`, the Python fixed-rules sentence and its four lines
       (whitespace joined). The tree: every version in `apps/api/pyproject.toml` is
       `==` and exact, and `uv.lock` (read with `tomllib`) has each pinned package at that
       version; every version in `package.json` is exact; every package that both starters'
       `package.json` files name has the same version; no package starts with `@nestjs/`,
       `@prisma/`, `@nx/`, or is `prisma` or `nx`; the lockfile's root importer equals
       `package.json` (`_pnpm_root_importer` from `tests/test_starter_tree.py`);
       `app/auth/models.py` and `app/projects/models.py` exist; `pyproject.toml` has the
       `[tool.mypy]` settings above, and the root `lint` and `typecheck` scripts call ruff and
       mypy; the Dockerfile has the lines above, `--no-access-log` included. Live half: one module-scoped fixture puts the composed tree (the three React
       starter paths, then `starter-python/`, then the skeleton's `.dockerignore`) in a temp
       folder, with the Docker and Node set-up of `live_starter` in
       `tests/test_starter_tree.py` (move that set-up into a helper both files call; no change
       in what it does). It runs `node scripts/test.mjs` once. The command exits 0 and prints
       `GET /health returned 200`; `test-results/api.xml` shows `account_isolation` and
       `production_forgot_password_does_not_log_a_reset_link` passed; `test-results/browser.xml`
       shows every name of `BROWSER_FLOWS` from `tests/test_starter_tree.py` passed.
     - wheel: `uv build --wheel` into a temp folder; the wheel has
       `forge/templates/starter-python/<path>` for every path that `git ls-files
       src/forge/templates/starter-python` lists, dotfiles included, byte for byte.
     - adopted: the `client` fixture of `tests/test_notes_first_discovery.py` with `adoption`
       "previous release upgrade and sync". For `.claude` and `.codex`, `SKILL.md` has the same
       three texts as in "new". The app side of an existing repo is item 5.
     - `tests/test_starter_app.py` test_3 keeps the React starter's cases and its refusals,
       which do not change.
2. The import check (STARTER).
   - Test: `tests/test_python_starter.py::test_2_an_import_of_another_modules_internals_fails_the_tests`,
     `@pytest.mark.platform`, with `case` in ("clean", "reach into a module"). Always:
     `pyproject.toml` has the three contracts with the guidance sentence, and the root `test`
     script runs `test:imports`. Live only, in the fixture's folder: clean: `uv --directory
     apps/api run lint-imports` exits 0. Reach into a module: add `app/projects/reach_in.py` with
     `from app.auth.service import AuthService` and a use of it. The command exits non-zero, and
     its output names `auth internals` and has `only through its public service`. Remove the file
     after the case.
3. The API types (STARTER).
   - `libs/shared/src/index.ts` keeps the React starter's zod schemas and form input types, and
     takes `Project`, `ProjectStatus` and `Account` from `api-types.ts`
     (`components['schemas'][...]`), so `apps/web` imports them from `@app/shared` with no change.
   - Test: `tests/test_python_starter.py::test_3_the_tests_fail_when_the_api_changes_a_field_the_web_app_uses`,
     `@pytest.mark.platform`, with `case` in ("clean", "the API renames a field"). Always:
     `libs/shared/src/index.ts` imports from `./api-types`, and the root `test` script runs
     `api-types` before `typecheck`. Live only, in the fixture's folder: clean: `corepack pnpm run
     api-types && corepack pnpm run typecheck` exits 0. The API renames a field: in
     `app/projects/schema.py`, rename the response model's `name` field to `title`. The same
     command exits non-zero, and its output names a file under `apps/web/src/features/projects/`.
     Put the file back after the case.
4. The Python page (GUIDE).
   - `python.md` has these sections, each with a short example in the style of `backend.md`:
     `## Layout` (the tree above), `## Modules` (public entry in `__init__.py`; the `protected`
     contract per module, and a new contract for each new module; each module's tables in its
     `models.py`; services get the database session through `Depends`, never build each other),
     `## Config`, `## Logs` (stdlib `logging` with a JSON formatter that writes the fields of
     `backend.md`; `x-correlation-id` kept in a `contextvars` variable and added to each entry;
     fixed messages with ids only), `## Errors` (one set of handlers; `ApiError` with an
     UPPER_SNAKE_CASE code from one list; 500 with a fixed message and the stack in the log only;
     a provider wraps its vendor's errors), `## API` (routers under `/api/v1`; the Pydantic
     settings above; `Envelope[T]`; the status codes and list shape of `api.md`; summaries, one
     PascalCase tag per module and error responses in the OpenAPI schema; `pnpm run api-types`
     after an API change, and commit both generated files), `## Database` (typed models;
     snake_case singular names; `Uuid` ids with `uuid4`; `*_at_utc` times in UTC; money as an
     integer in the smallest unit, `total_in_cents`; booleans with a default; the audit fields;
     soft delete by `deleted_at_utc`, filtered in the query itself; raw SQL only through `text()`
     with bound values, in a repository file; `idx_<table>_<column>`), `## Migrations` (`uv
     --directory apps/api run alembic revision --autogenerate -m "<what>"`, read and commit it,
     never edit a merged one, a data change as its own migration, a drop under the story's
     Risks), `## Security` (the rules of `security.md` in FastAPI terms: the headers middleware,
     CORS, the rate limit, the cookie settings, the CSRF header, scrypt, scoping each query to the
     account, 404 for another account's record), `## Tests` (pytest and httpx against the running
     API and a fresh database, data created through the API, one test per Done-when item, the
     refusals; Playwright for flows as `testing.md` says; unit tests only for pure logic; the root
     `test` script with `ruff check`, `ruff format --check` and `mypy` in strict mode, and
     `node scripts/test.mjs`), `## Deploy` (the image of item 1; `/health`;
     port 3000; migrations before start; the `DATABASE_URL` scheme) and one line on demo data (the
     loader in `apps/api/app/demo/` is app code, not a module, and may read every table).
   - `brief.md`: the brief sentence above, after "Open a file there only when your task touches
     its concern.".
   - `src/forge/standards.md`: the page list adds `python.md` (the same rules for a FastAPI
     backend), and the Data section adds `A Python app writes these names in snake_case
     (payment_transaction, created_at_utc); see python.md.`
   - `conventions/stack.md`: after the keep lines, `A new app whose owner asks for a Python
     backend starts from forge init --starter python: a FastAPI API in apps/api next to the same
     web app. See python.md.`
   - `tests/test_standards.py` and `tests/test_outside_scope_and_runtime_tests.py` read every
     page in the folder: a line of `python.md` that names an interface must also have only, no,
     not or never, and the page must not ask for a test for every item whatever its runtime
     behaviour. `tests/test_starter_app.py` test_3 refuses `npm workspaces` on every page.
   - Test: `tests/test_python_guide.py::test_4_a_worker_in_a_python_app_reads_the_python_page`,
     with the `client` fixture of `tests/test_notes_first_discovery.py` and `adoption` in ("new
     init", "previous release upgrade and sync"). A fix runs `forge work` with
     `install_claude`; the brief has the brief sentence. The conventions folder that the brief
     names (found as `tests/test_starter_app.py` test_3 finds it) has `python.md` with the eleven
     section headings, `extra="forbid"`, `errorId`, `x-correlation-id`, `Uuid`, `_at_utc`,
     `_in_cents`, `deleted_at_utc`, `alembic upgrade head`, `lint-imports`, `ruff format --check`, `mypy` and `pytest`;
     `standards.md` in the synced skills folder names `python.md`.
5. An existing app keeps its stack (GUIDE).
   - Test: `tests/test_python_guide.py::test_5_an_existing_app_keeps_its_stack`, adopted case
     only (the item is about existing apps). Before the adoption commit, the fixture gets an
     existing Python app: `pyproject.toml`, `uv.lock`, a `Dockerfile` and `app/main.py` of its
     own, and forge.toml's `test` set to `uv run pytest`. After upgrade and sync, those four
     files are byte for byte the same, the `test` setting is the same, and `apps/api/`,
     `libs/shared/`, `scripts/test.mjs` and `pnpm-lock.yaml` do not exist.

### New and existing repos

- **New repos** (init): `forge init --starter python` writes the Python starter, its Dockerfile,
  the import contracts and the API types in the first commit, with `node scripts/test.mjs` as
  the test command. `forge init --starter` writes the React starter as today. Plain `forge init`
  is as today, with two more `.dockerignore` lines. The guide lines, the Python page and the brief
  sentence arrive with setup (items 1 and 4).
- **Existing repos** (on upgrade to this release, after `forge sync`): no app file, lockfile,
  Dockerfile or test command changes, and no starter file is written. The guide lines, the Python
  page and the brief sentence arrive with the release and sync; the repo's own rules still win.
  Tested on the adopted earlier-release fixture moved to this release (items 1, 4 and 5).

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
| STARTER | The Python starter and its init option | The FastAPI starter tree with its modules, import contracts, API types, ruff and mypy, tests and Dockerfile; `forge init --starter python` from source and from the wheel; the guide's set-up row and the constitution's Python fixed rules; the live job. New repos get it from init; existing repos get no file. The one part allowed over the line limit (see Risks). | 1, 2, 3 | `src/forge/templates/starter-python/**` (new), `src/forge/init.py`, `src/forge/templates/skeleton/.dockerignore`, `src/forge/templates/skill.md` (every edit of this story), `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `.github/workflows/starter-smoke.yml`, `tests/test_starter_tree.py` (the live set-up helper only), `pyproject.toml` (only if the wheel misses a starter file) | `tests/test_python_starter.py` (`test_1`, `test_2`, `test_3`, new) | FORGE-REACTDEFAULTS-1/STARTER | no | |
| GUIDE | The Python page | The Python conventions page, the brief sentence that points to it, and the standards and stack lines, on new and existing repos, and the proof that an existing app keeps its stack. | 4, 5 | `src/forge/templates/conventions/python.md` (new), `src/forge/templates/conventions/stack.md`, `src/forge/templates/brief.md`, `src/forge/standards.md` | `tests/test_python_guide.py` (`test_4`, `test_5`, new) | | no | |

New moving parts: FastAPI with Pydantic, uvicorn and psycopg, the Python starter's API (item 1); SQLAlchemy and Alembic, its database models and migrations (item 1); uv, its package manager (item 1); import-linter, the module check (item 2); ruff and mypy, the Python lint, format and type checks (item 1); openapi-typescript, a dev dependency that makes the web app's API types (item 3).

## Notes

- **Order.** STARTER waits for FORGE-REACTDEFAULTS-1/STARTER, because it copies `apps/web` and
  mirrors the root web files. GUIDE waits for nothing and runs in parallel: its text names only
  what this doc pins. STARTER owns every `skill.md` edit and its two regenerated copies, so
  the two parts share no file. Both ship in one release.
- **One Python page, not a Python section in each page.** One page is one file for a Python
  worker to open, and the NestJS pages and the tests that pin their text do not change. The
  brief sends a Python worker to it, and the rules of the other pages still apply.
- **Why copy `apps/web` at init.** The Python starter holds no copy of the web app, so a change
  to the React starter's web app reaches both starters. Only the root web files are copied, and
  test 1 holds their versions the same.
- **Why no Nx.** The Python starter has one TypeScript app and one shared library, and the
  module rule is in Python. Nx would add a build tool and its lint plugin for no check. The
  React starter's `apps/web/project.json` comes along and is not used.
- **Why snake_case tables.** SQLAlchemy and Python use snake_case, so the names need no mapping.
  The JSON stays camelCase through Pydantic aliases, so the web app does not change.
- **The fix lane.** Pydantic models in `schema.py` and Alembic files in `migrations/` match the
  interface globs that init writes today, so an API or table change goes to the story lane. A
  route-only change in `routes.py` does not match; add `**/routes.py` to `init.INTERFACES` only
  if that happens in a real app.
- **Not in this story.** Async SQLAlchemy; a
  Python starter for an existing repo; moving an existing app to this starter; a Python-only app
  with no web app.
- **Not to do.** No new command or `forge.toml` setting; the one change is the `python` value of
  `--starter`. No change to an existing repo's app files, Dockerfile or test command. No Nx Cloud,
  telemetry or remote cache.
- No client repo is named anywhere in this story's code, tests, texts or commits.
