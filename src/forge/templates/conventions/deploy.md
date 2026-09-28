# Deploying the prototype

Our platform builds the repository's root Dockerfile and provides Postgres through `DATABASE_URL`.
Connect the client GitHub repository and choose its subdomain.
The platform routes traffic to container port 3000 and checks `GET /health` for HTTP 200. Keep
one instance running while migrations are made.

The root `package.json` uses npm workspaces for `frontend/` and `backend/`, with a committed
`package-lock.json`. The Dockerfile installs from that lockfile, builds both workspaces, then
starts in `backend/`. The frontend build writes `frontend/dist`; the backend serves that folder
at `/` and starts with `npm run start:prod`. The prototype's first fix creates the app and its
scripts to this contract. Until then the Dockerfile is a deploy template, not a runnable app.

At every container start, `npx prisma migrate deploy` runs before the backend listens. If it
fails, the container exits without serving traffic. Check `DATABASE_URL` and the failed migration
in the platform logs, fix the cause, and redeploy; the previous healthy version should keep
serving. Keep migrations additive so restarting a container cannot remove production data.
