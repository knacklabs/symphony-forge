# Starter app

The app has a React web app, a NestJS API, and Postgres. Nx runs the builds and type checks.
The shell uses the neutral shadcn/ui theme. Apply the app's approved design in its own story.
`apps/web/src/components/ui` holds copied shadcn/ui source from the pinned 4.21.4 tool and its MIT license.

## Run it

Use Node 24, Corepack and Docker with Linux containers. Corepack uses the exact pnpm version pinned
in `package.json`. The starter includes its root Dockerfile; Forge supplies `.dockerignore` at setup.

```sh
node scripts/test.mjs
```

This command installs the pinned pnpm packages and Chromium. It starts a fresh Postgres database
and API instances for many companies, one company and production. It runs lint, type checks,
Supertest, Vitest, and Playwright. It then removes its containers and data, even when a test fails.
Reports stay in `test-results/api.xml` and
`test-results/browser.xml`.

For local work, copy `.env.example` to `.env`. Set the database URL and app origin. Run Postgres, then run:

```sh
COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm install --frozen-lockfile
COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm exec node --env-file=.env node_modules/prisma/build/index.js migrate deploy
COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm run build
COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm run start:prod
```

The app serves the web app and API at port 3000. `/health` checks readiness. `/api/docs` lists the API endpoints.

## One company

Set `APP_COMPANIES=one` to close public sign-up. An unset value or `many` keeps sign-up open.
Other values stop the API with `APP_COMPANIES must be one or many.`
`GET /api/v1/auth/options` reports `signUpOpen`. A closed sign-up returns `403 SIGN_UP_CLOSED`.
Admin invites still work.

After migrations and the build, set `ADMIN_EMAIL` and `ADMIN_PASSWORD` for the first admin.
The setup command reads `.env` and checks these credentials with the sign-up schema:

```sh
COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm run setup:company
```

Run this command once. It creates a company and its admin, without a browser session.
A duplicate email returns exit status 1 with `An account already uses that email.`
A new email creates another company. Remove the setup credentials from `.env` after setup.
Production invites need the mail provider described below.

To open sign-up later, change `APP_COMPANIES` to `many` and restart the API.
The company, accounts and records stay in the same tables. No migration is needed.
New apps receive this code. An upgrade leaves existing app files and their sign-up behavior unchanged.

## How it works

`apps/web` holds routes and feature folders. Project hooks use TanStack Query and the typed API
client. Components use the hooks, without direct HTTP calls. React Compiler memoizes components, so the code has
no `useMemo`, `useCallback` or `React.memo` outside `components/ui`. Each route has an error page,
so a crash on one screen leaves the other screens working. `libs/auth` owns sign-in and account
tables. `libs/projects` owns example records and project tables. Each exports a public service from
its package entry. A module uses another module only through that service; it does not import
internal files or query the other module's tables. `libs/core` holds shared NestJS code, and
`libs/shared` holds the schemas and types used across the app.

Zod schemas in `libs/shared` check every request body and query, and the API documentation comes from the same schemas.

`libs/organisations` owns organisations, admin and member roles, and email invites. Each account
belongs to one organisation, and every query checks that organisation. Admins invite people and
change roles; members cannot. `libs/history` records these admin actions for the change history.
In local and test runs, invite links go to the log. Production refuses invites until the app
has a real mail provider.

The helpers in `@app/shared` format dates, times, numbers and money. Dates and times are stored in
UTC and shown in the person's browser time zone; money is stored in cents. Each table has an
Export CSV button, and `sendCsv` from `@app/core` writes formula-like cells as plain text.
Deletes keep records with `deletedAtUtc`; the database's `soft_delete_only()` trigger refuses
a hard delete. Each UI or API crash writes one error report to the logs, with only its kind,
page path and reference number.

`apps/api` wires the modules and serves the app. Passwords use scrypt. Postgres holds server
sessions, reset tokens, accounts, organisations, invites, projects and change history.

Forgot password always gives the same reply. Only `APP_ENV=development` or `APP_ENV=test` writes a reset link to the log. Other environments send no email and log no link or token. Add a real mail provider in the story that needs it.

The Dockerfile runs root `build`, applies migrations, and runs root `start:prod`. Supply `DATABASE_URL`, `APP_ENV`, `APP_ORIGIN`, and `PORT` to the container. Use HTTPS at the host in production.
