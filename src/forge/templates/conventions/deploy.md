# Deploying the prototype

## First production release

Client sign-off approves the product direction, not production readiness. Plan and build the
remaining production work through stories and reviewed pull requests. Before the first Promote:

1. Confirm the client's production host, account owner, region, domain, budget and release
   approver. Record the decisions, but no secrets, in the repo.
2. Confirm production access, secrets, HTTPS, DNS, database access, migrations and external
   services. Check the release in a non-production environment with a green full test run,
   the customer's main task and permissions for each role.
3. Confirm a current database backup and a demonstrated restore. Record the recovery steps,
   the person responsible and the rollback plan for the app and migrations.
4. Confirm health checks, error alerts, the support contact, release time and any data import
   or downtime with the client.
5. The authorized person presses Promote. Workers never deploy, and agents never promote
   production. Check the production address and main task after release. Use the agreed
   rollback plan if a check fails and notify the support contact.

## Client cloud or servers

Confirm the host before deploy setup. Ask the platform administrator whether Mainline supports
the client's target. Do not assume support for an arbitrary cloud account or server.
For a supported target, follow the installed Mainline Deploy skill. Otherwise, record the
host and constraints and plan the required deploy work as a story. Name who owns server access,
network access, secrets, certificates, the database, backups, alerts and release. Use the
client's approved release process and the production checklist above. A host without Mainline
has no Mainline Promote step. Do not invent install commands or change the client's host choice.

The FDE coordinates customer answers and delivery. The owner chooses scope and accepts
decisions. The customer's named sign-off person approves the design and answers. Agree who
authorizes production. The platform administrator supplies access and environment setup.
The coordinating agent runs Forge, while workers build and commit changes.

## Mainline setup

Mainline Deploy is available to install through the organization's plugin catalog. Do not assume
that the plugin and MCP are installed or that the user is signed in.
Use Mainline Deploy only when the user explicitly requests deployment. First check whether it is
installed in the current host. If it is missing, use the organization's plugin catalog and the
host's installation flow. Do not invent an installation command or marketplace address.
Then follow the Mainline Deploy skill. Check OAuth sign-in and have the user complete it if needed.
Wait for successful authentication before deployment. Installation alone does not mean the user is signed in.
Deploy only the requested app to the requested environment. A build, fix, merge, ship/land request,
successful test or review, demo preparation, or Forge next step does not by itself authorize deployment.
Do not install Mainline or start OAuth sign-in for those requests. An explicit request such as
"deploy this to staging" or "publish this on Mainline" needs no separate routine deployment approval.

`services.toml` at the repo root lists the services our platform runs from this repository.
Each `[[service]]` has a `name`, a `dockerfile` path, a container `port`, a `health` path that
answers HTTP 200 when the service is ready, and an `expose` value: `main` for the app's main
address, `subdomain` for its own subdomain, named by its `subdomain` prefix (for example
`api`), or `internal` for a service with no address, such as a worker, which needs no port or
health path. An optional `command` replaces the Dockerfile's start command.
An optional `mcp` is the path where the service serves its MCP server, such as `/mcp`;
Mainline shows it under Connectors, and its gateway sends the agent key that an admin creates
in the app. Exactly one
service is `main`. One release builds every service, and a rollback rolls them all back. The
platform provides Postgres through `DATABASE_URL`. Forge's starters list one `main` service:
the root Dockerfile on port 3000 with `GET /health`.
For a requested deployment, follow the installed Mainline Deploy skill to connect the client
GitHub repository and choose its main subdomain; the list does not hold it.
Keep one instance running while migrations are made.

Containers run as a user that is not root. Keep application files read-only at run time;
uploads go in the private bucket described in security.md.

When a story adds background jobs or schedules, add an internal worker service. It can use
the app's image with a different start command; use the worker command that the story adds:

```toml
[[service]]
name = "worker"
dockerfile = "Dockerfile"
expose = "internal"
command = "corepack pnpm run start:worker"
```

A Python worker uses its own worker command instead. Internal workers need no port or
health path. The database skill describes the jobs table; a schedule only inserts job rows.

The first deployment that the owner asks for is the deploy setup, once for each repository:
browser sign-in with Google or GitHub, then the repository, `services.toml`, the main
subdomain, the variables that `.env.example` names, and dev first. After the setup, Mainline
deploys dev at each merge to the default branch and a preview for each pull request.
Production changes only when a person presses Promote in Mainline. An agent does not run
these deploys, and an agent never deploys or promotes production.

The root `package.json` and committed `pnpm-lock.yaml` hold the app scripts and dependencies.
The Dockerfile installs from the lockfile, runs `COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm run build`,
then runs `COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm run start:prod`.
The build uses Nx for `apps/web` and `apps/api`. The API serves the built web app at `/` and
answers `GET /health` with HTTP 200 when ready. `start:prod` starts the API. The starter provides
these scripts when `forge init --starter` creates a new repo.
The generated `.dockerignore` keeps local environment files, keys and credential files out of
the image; keep deployment secrets in the platform's secret store.

At every container start, `COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm exec prisma migrate deploy` runs before the backend listens. If it
fails, the container exits without serving traffic. Check `DATABASE_URL` and the failed migration
in the platform logs, fix the cause, and redeploy; the previous healthy version should keep
serving. Expand, then contract: add a new table or column before code uses it, keep the old table
or column for two releases, and remove it only when no live release uses it. A Mainline rollback
restores the previous release's code and keeps the database, so each migration must work with
that code still running.

Mainline sends error alerts from the app's `error` log lines. Each carries an `errorId`, which the person sees on the error screen, so search the platform logs for it. In an app whose `.env.example` names `LOG_LEVEL`, set it in the platform's settings to change how much the app writes.
