# The default client stack

The smallest stack that runs a client app's first story. Each part is here because almost every
client app needs it on day one; anything else arrives with the story that needs it. A repo that
already runs a different stack keeps its own.

| Part | Choice | Why this one |
|---|---|---|
| Backend | NestJS (TypeScript) | Widely known; modules, dependency injection and validation built in |
| Database | Postgres through Prisma | One boring database; typed queries and migrations |
| Frontend | React with Vite | Widely known; fast builds with almost no config |
| Server data | TanStack Query | Caching, loading and error states without hand-written effects |
| UI | Tailwind with shadcn/ui | Accessible components you own as code |
| Tests | Vitest, Supertest, Testing Library | One runner for both apps; tests through HTTP and the screen |
| Workspace | npm workspaces | Built into npm, so there is no extra build tool |
| CI | Forge's generated `forge.yml` | Runs forge.toml's `test` command as the `tests` check |

## Layout

```
apps/api/            NestJS backend (see backend.md)
apps/web/            React app (see frontend.md)
packages/shared/     types and validators both apps use
docker-compose.yml   Postgres for local work and tests, nothing else
.env.example         every variable, with dummy values
README.md            how to run it, and a short plain-English "How it works"
```

The root `package.json` declares the workspaces and one `test` script that runs lint, typecheck
and every workspace's tests (see testing.md).

## Added later

Each of these is a moving part the client pays for as long as the app runs, so none is set up in
advance. The story that needs one names it, with the Done-when item it serves.

- Redis, for a cache or limits shared by several app instances: add when a story's New moving parts names it.
- A job queue (for example BullMQ) for work that must outlive a request: add when a story's New moving parts names it; until then the work happens inside the request.
- AWS CDK, for the client's cloud infrastructure as code: add when a story's New moving parts names it.
- OIDC sign-in through the client's identity provider: add when a story's New moving parts names it.
- A monitoring stack (metrics, traces, dashboards): add when a story's New moving parts names it; until then the structured logs are the record.

The same goes for libraries an older scaffold installed on day one: a client-side state store, a
generated API client and a browser test runner each come with the story that needs them.
