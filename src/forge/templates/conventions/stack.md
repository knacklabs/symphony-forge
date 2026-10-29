# The default client stack

The smallest stack that runs a client app's first story. Each part is here because almost every
client app needs it on day one; anything else arrives with the story that needs it. A repo that
already runs a different stack keeps its own.

| Part | Choice | Why this one |
|---|---|---|
| Backend | NestJS (TypeScript) | Widely known; modules, dependency injection and validation built in |
| Database | Postgres through Prisma | One boring database; typed queries and migrations |
| Frontend | React with Vite, React Router and React Compiler | Widely known; fast builds with almost no config |
| Server data | TanStack Query | Caching, loading and error states without hand-written effects |
| UI | Tailwind with shadcn/ui | Accessible components you own as code |
| Lint | ESLint | The usual linter; it runs in the one `test` script |
| Tests | Vitest, Supertest, Testing Library, Playwright | Unit and HTTP tests plus browser tests of user flows |
| Workspace | Nx | One build tool for the web app and API; no Nx Cloud |
| Package manager | pnpm through Corepack | The root package pins pnpm and the lockfile pins every dependency |
| Modules | Nx libraries | Each business area owns its tables and publishes contracts for other modules |
| CI | Forge's generated `forge.yml` | Runs forge.toml's `test` command as the `tests` check |

## Layout

```
apps/api/src/                 NestJS app entry, module wiring and health route (see backend.md)
apps/web/src/                 React app (see frontend.md)
libs/auth/contracts/src/      sign-in schemas and types
libs/auth/server/src/         sign-in module, exported as @app/auth-server
libs/projects/contracts/src/  project schemas and types
libs/projects/server/src/     project module, exported as @app/projects-server
libs/organisations/contracts/src/ schemas, types and OrganisationsApi contract
libs/organisations/server/src/ organisations, roles and invites, exported as @app/organisations-server
libs/history/contracts/src/   history types and HistoryApi contract
libs/history/server/src/      admin change history, exported as @app/history-server
libs/core/server/src/         shared NestJS code, exported as @app/core-server
libs/shared/util/src/         general helpers, exported as @app/shared-util
apps/api/prisma/schema/       base.prisma plus one schema file per business module
pnpm-workspace.yaml           the workspace package list
pnpm-lock.yaml                exact dependency versions
compose.test.yml              Postgres and the app for stack tests
Dockerfile                    the one deploy file (see deploy.md)
.env.example                  every variable, with dummy values
README.md                     how to run it, and a short plain-English "How it works"
```

An app made before this layout keeps its own folders and schema; follow the folders it has.

The root `package.json` pins pnpm and has a `test` script for lint, type checks, API tests, hook
tests and browser tests (see testing.md). Nx builds and type-checks the web and API apps and checks
the module boundaries.

An app set up before Nx keeps its npm workspaces and its Dockerfile.
An app set up before this release keeps its package manager, lockfile and folder layout.
An app set up before this release keeps its own organisation, date, export, history and error code.

A new app whose owner asks for a Python backend starts from forge init --starter python: a FastAPI
API in apps/api next to the same web app. See python.md.

## Deploy contract

The root `package.json` has `build` and `start:prod` scripts. `COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm run build` uses Nx to
build `apps/web` and `apps/api`. The API serves the web app at `/` and answers `GET /health` with
HTTP 200 when ready. `COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm run start:prod` starts the
API. The Dockerfile runs `COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm exec prisma migrate deploy`
before the server starts.
The platform supplies Postgres through `DATABASE_URL` and sends traffic to port 3000. See
[deploy.md](deploy.md) for the deployment steps and failure behavior.

A prototype's first version also builds a demo-data loader, so the client sees their own work
(see demo-data.md).

## Added later

Each of these is a moving part the client pays for as long as the app runs, so none is set up in
advance. The story that needs one names it, with the Done-when item it serves.

- Redis, for a cache or limits shared by several app instances: add when a story's New moving parts names it.
- Background jobs and schedules for work that must outlive a request: the story adds a worker in `services.toml` and a Postgres jobs table read with `FOR UPDATE SKIP LOCKED`, as the database skill says. No separate queue server; until that story, work happens inside the request.
- Terraform, for the client's cloud infrastructure as code: add when a story's New moving parts names it.
- OIDC sign-in through the client's identity provider: add when a story's New moving parts names it.
- A monitoring stack (metrics, traces, dashboards): add when a story's New moving parts names it; until then the structured logs are the record.

Modules use another module only through its contracts package. The server code stays inside its
module library. The web app cannot import a server library.

`OrganisationsApi`/`ORGANISATIONS_API` and `HistoryApi`/`HISTORY_API` are the public service
contracts used across modules.

The same goes for libraries an older scaffold installed on day one: a client-side state store and
a generated API client each come with the story that needs them. Playwright arrives with the first
user-facing flow that needs a browser test.
