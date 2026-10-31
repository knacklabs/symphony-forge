# FastAPI starter

The app has a FastAPI API, a React web app, and Postgres. The API uses SQLAlchemy and Alembic.
The web app keeps its build setup and neutral shadcn/ui theme, but starts without an app shell or
screens. The design comes first: use the client's existing design. If there is none, draft one on
a design canvas from the client's brand, or use a neutral design when there is no brand. The agent
builds each screen with the API that a person uses. Webhooks, endpoints only agents or other
systems call, and background jobs get no screen.
`libs/shared/ui/src/components/ui` holds copied shadcn/ui source from the pinned 4.21.4 tool and its MIT license.

## Run it

Use Node 24, Corepack, uv 0.13.0 or later, and Docker with Linux containers. Corepack uses the
exact pnpm version pinned in `package.json`. The starter includes its root Dockerfile. Forge
supplies `.dockerignore` at setup.

Run the complete stack and its checks with:

```sh
node scripts/test.mjs
```

This command installs the pinned pnpm packages, Python packages, and Chromium. It starts a new
Postgres database and three API instances. It runs lint, format, and type checks, pytest, Vitest, and
Playwright. It removes the containers and data after the run, even when a test fails. Reports go
to `test-results/api.xml` and `test-results/browser.xml`.

`.env.example` lists the values that the container needs outside this test stack.

The app serves the web app and API at port 3000. `/health` checks readiness. `/api/docs` lists the
API endpoints.

## Set up a one-company app

Set `APP_COMPANIES=one` in the API environment to close public sign-up. If you do not set this
value, the app uses `many` and keeps public sign-up open.

Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in the API environment. From `apps/api`, run this command
to create the company and its first account as the admin:

```sh
uv run --no-sync python -m app.setup_company
```

Run the command once. It does not check whether a company already exists. A second run with a new
email creates another company.

Set `APP_COMPANIES=many` to open public sign-up later. Restart the API. The app keeps the same
company, people, and records. No data migration is needed.

## How it works

`apps/web` keeps the web entry point and theme CSS, but starts without an app shell, route table or
screens. `libs/core/web` holds the API client and query client. `libs/shared/ui` holds shadcn/ui
components. The agent builds a screen in the client's design with each person-facing API; webhooks,
agent-only or system-only endpoints, and background jobs get no screen. Build the basic screens
first, then the business screens. The demo opens on the business task and shows the basic screens
last. Components use the hooks and make no direct HTTP calls. Each route has an error page. A
crash on one screen leaves the other screens usable. React Compiler memoizes components, so the code has no `useMemo`, `useCallback` or
`React.memo` outside `libs/shared/ui/src/components/ui`.

The `app.auth` module owns sign-in and account tables. The `app.projects` module owns example
records and project tables. Each module exports its public service from `__init__.py`. A module
uses another module only through its public service. Modules do not import each other's internal
files or query their tables. `import-linter` contracts make an internal import fail the tests.

Each module's form schemas and public types live in `libs/<module>/contracts`. The shared API types
come from `apps/api` OpenAPI in `libs/shared/api-types`, and general helpers live in
`libs/shared/util`.

Passwords use scrypt. Postgres holds sessions, reset tokens, accounts, and projects. Each project
query checks the account. Delete keeps the audit record. When the agent builds the Members screen,
an admin can copy an invite link and send it by chat when the app has no mail provider. Email
invites need a mail provider.

Forgot password gives the same neutral reply for known and unknown emails. When the agent builds
the Members screen, an admin can make a reset link and send it by chat if the app has no mail
provider. A reset link works once and expires.

The Dockerfile builds the web app, applies migrations, and runs the API. The container needs
`DATABASE_URL`, `APP_ENV`, `APP_ORIGIN`, and `PORT`. The host uses HTTPS in production.

## When something breaks

1. Find the error id shown by the app in Mainline's logs. Use that log entry to find the
   cause. Mainline reads error log lines with their error id to send alerts.
2. Roll back to the last working release in Mainline if a release breaks the app. A rollback
   restores the code and keeps the database.
3. Restore a snapshot if data is lost or damaged. Stop writes, choose a snapshot from before
   the problem, and check the restored data before you open the app again. Changes made after
   the snapshot must be entered again.
4. Change a leaked secret in the host's secret store and restart the app. Revoke the old
   secret at its provider. For an agent key, revoke it in the app and create a new key.
