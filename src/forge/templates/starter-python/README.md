# FastAPI starter

The app has a FastAPI API, a React web app, and Postgres. The API uses SQLAlchemy and Alembic.
The shell uses the neutral shadcn/ui theme. Apply the app's approved design in its own story.
`apps/web/src/components/ui` holds copied shadcn/ui source from the pinned 4.21.4 tool and its MIT license.

## Run it

Use Node 24, Corepack, uv 0.13.0 or later, and Docker with Linux containers. Corepack uses the
exact pnpm version pinned in `package.json`. The starter includes its root Dockerfile. Forge
supplies `.dockerignore` at setup.

Run the complete stack and its checks with:

```sh
node scripts/test.mjs
```

This command installs the pinned pnpm packages, Python packages, and Chromium. It starts a new
Postgres database and two API instances. It runs lint, format, and type checks, pytest, Vitest, and
Playwright. It removes the containers and data after the run, even when a test fails. Reports go
to `test-results/api.xml` and `test-results/browser.xml`.

`.env.example` lists the values that the container needs outside this test stack.

The app serves the web app and API at port 3000. `/health` checks readiness. `/api/docs` lists the
API endpoints.

## How it works

`apps/web` holds routes and feature folders. Project hooks use TanStack Query and the typed API
client. Components use the hooks and make no direct HTTP calls. React Compiler memoizes components.

The code has no `useMemo`, `useCallback`, or `React.memo` outside `components/ui`. Each route has
an error page. A crash on one screen leaves the other screens usable.

The `app.auth` module owns sign-in and account tables. The `app.projects` module owns example
records and project tables. Each module exports its public service from `__init__.py`. A module
uses another module only through its public service. Modules do not import each other's internal
files or query their tables. `import-linter` contracts make an internal import fail the tests.

`libs/shared` keeps the web form zod schemas. It reads API types from the `apps/api` OpenAPI schema.

Passwords use scrypt. Postgres holds sessions, reset tokens, accounts, and projects. Each project
query checks the account. Delete keeps the audit record.

Forgot password always gives the same reply. Only development and test environments log a reset
link. Production sends no email and logs no reset link or token. A story can add a real mail
provider when needed.

The Dockerfile builds the web app, applies migrations, and runs the API. The container needs
`DATABASE_URL`, `APP_ENV`, `APP_ORIGIN`, and `PORT`. The host uses HTTPS in production.
