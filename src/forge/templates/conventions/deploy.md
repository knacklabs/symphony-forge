# Deploying the prototype

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
health path. An optional `command` replaces the Dockerfile's start command. Exactly one
service is `main`. One release builds every service, and a rollback rolls them all back. The
platform provides Postgres through `DATABASE_URL`. Forge's starters list one `main` service:
the root Dockerfile on port 3000 with `GET /health`.
For a requested deployment, follow the installed Mainline Deploy skill to connect the client
GitHub repository and choose its main subdomain; the list does not hold it.
Keep one instance running while migrations are made.

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
serving. Keep migrations additive so restarting a container cannot remove production data.
