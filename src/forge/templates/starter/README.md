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

This command installs the pinned pnpm packages and Chromium, starts a fresh Postgres database and
both API instances, and runs lint, type checks, Supertest, Vitest, and Playwright. It then removes
its containers and data, even when a test fails. Reports stay in `test-results/api.xml` and
`test-results/browser.xml`.

For local work, copy `.env.example` to `.env`. Set the database URL and app origin. Run Postgres, then run:

```sh
COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm install --frozen-lockfile
COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm exec node --env-file=.env node_modules/prisma/build/index.js migrate deploy
COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm run build
COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm run start:prod
```

The app serves the web app and API at port 3000. `/health` checks readiness. `/api/docs` lists the API endpoints.

## How it works

`apps/web` holds routes and feature folders. Project hooks use TanStack Query and the typed API
client. Components use the hooks, without direct HTTP calls. React Compiler memoizes components, so the code has
no `useMemo`, `useCallback` or `React.memo` outside `components/ui`. Each route has an error page,
so a crash on one screen leaves the other screens working. `libs/auth` owns sign-in and account
tables. `libs/projects` owns example records and project tables. Each exports a public service from
its package entry. A module uses another module only through that service; it does not import
internal files or query the other module's tables. `libs/core` holds shared NestJS code, and
`libs/shared` holds the schemas and types used across the app.

`apps/api` wires the modules and serves the app. Passwords use scrypt. Postgres holds server sessions, reset tokens, accounts, and projects. Every project query checks the account. Delete keeps the audit record.

Forgot password always gives the same reply. Only `APP_ENV=development` or `APP_ENV=test` writes a reset link to the log. Other environments send no email and log no link or token. Add a real mail provider in the story that needs it.

The Dockerfile runs root `build`, applies migrations, and runs root `start:prod`. Supply `DATABASE_URL`, `APP_ENV`, `APP_ORIGIN`, and `PORT` to the container. Use HTTPS at the host in production.
