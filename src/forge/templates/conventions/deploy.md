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

Our platform builds the repository's root Dockerfile and provides Postgres through `DATABASE_URL`.
For a requested deployment, follow the installed Mainline Deploy skill to connect the client
GitHub repository and choose its subdomain.
The platform routes traffic to container port 3000 and checks `GET /health` for HTTP 200. Keep
one instance running while migrations are made.

The root `package.json` uses npm workspaces for `frontend/` and `backend/`, with a committed
`package-lock.json`. The Dockerfile installs from that lockfile, builds both workspaces, then
starts in `backend/`. The frontend build writes `frontend/dist`; the backend serves that folder
at `/` and starts with `npm run start:prod`. The prototype's first fix creates the app and its
scripts to this contract. Until then the Dockerfile is a deploy template, not a runnable app.
The generated `.dockerignore` keeps local environment files, keys and credential files out of
the image; keep deployment secrets in the platform's secret store.

At every container start, `npx prisma migrate deploy` runs before the backend listens. If it
fails, the container exits without serving traffic. Check `DATABASE_URL` and the failed migration
in the platform logs, fix the cause, and redeploy; the previous healthy version should keep
serving. Keep migrations additive so restarting a container cannot remove production data.
