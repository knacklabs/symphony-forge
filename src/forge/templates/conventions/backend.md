# Backend (NestJS)

How the standards page's backend rules look in NestJS. Read it when your task adds or changes a
module, the config, logging or error handling.

## Layout

```
apps/api/src/
  main.ts               start-up: the exception filter, security, Swagger, JSON logs
  app.module.ts          wires the API and its modules
  health/               GET /health, after migrations have succeeded at start-up
libs/
  auth/contracts/        sign-in schemas and types
  auth/server/           sign-in module, exported as @app/auth-server
  projects/contracts/    project schemas and types
  projects/server/       example records module, exported as @app/projects-server
  organisations/contracts/ organisations schemas, types and OrganisationsApi contract
  organisations/server/  organisations, roles and invites module, exported as @app/organisations-server
  history/contracts/     history types and HistoryApi contract
  history/server/        admin change history module, exported as @app/history-server
  core/server/           config, common code and Prisma service, exported as @app/core-server
  shared/util/           general helpers, exported as @app/shared-util
```

An app made before this layout keeps its own folders and schema; follow the folders it has.

## Modules

Request input is checked by zod schemas from the module's contracts package, as api.md says; the
app has no global ValidationPipe.

- Each library's public entry is `src/index.ts`, imported by its package name; its package's
  `exports` has only `.`. A module has a `contracts` package, such as `@app/projects-contracts`, for
  schemas and types, and a `server` package, such as `@app/projects-server`, for Nest modules,
  controllers and services. A server uses another module's service through that module's public
  contract. Only cross-module services expose interfaces and tokens: `OrganisationsApi`/
  `ORGANISATIONS_API` and `HistoryApi`/`HISTORY_API`.
- Nx tags use `type:contracts` or `type:server` with a `scope:<module>` tag. The core server uses
  `scope:core`; shared helpers use `type:util` and `scope:shared`.
- `@nx/enforce-module-boundaries` in `eslint.config.mjs` enforces these tags. A module server can
  import another module only through its contracts package. The web app cannot import server code.
- `apps/api/prisma/schema/base.prisma` holds the generator and datasource. The auth module owns
  `auth.prisma` for accounts, sessions and reset tokens; the projects module owns `projects.prisma`
  for projects and their status. Keep each module's models in its schema file, even when a relation
  points to a table owned by another module.
- Services query through `PrismaService`. Move a query into `<domain>.repository.ts` when a second
  service needs it or it is raw SQL.
- Name request schemas `createXSchema` and `updateXSchema` (one `xSchema` when both are the same)
  and list queries `xListQuerySchema`, in `@app/<module>-contracts`; name response DTOs `XResponseDto`.
- Name event files `*.event.ts` and `*.handler.ts`.
- Inject dependencies through constructors; never `new` a service yourself, so tests can swap it.

In an app that has `libs/organisations`, that module owns organisations, roles and invites;
`libs/history` owns change history. Record admin actions with its public `HistoryService.record`.
Export a table only with `sendCsv` from `@app/core-server`; it writes formula-like cells as plain
text.

## Call a service or send an event

- If the current action needs another module's answer to continue, call that module's public
  service and await the result.
- If other modules react after an action succeeds and the current action needs no answer from
  them, send an in-process event. The sender does not need to know which modules react.
  Add events only when the story's `New moving parts` names them.

Reviews apply this call-or-event rule only to new code. Existing code needs no conversion.
For work that must outlive a request, follow [stack.md](stack.md).

## Config

Use `@nestjs/config` with a `validate` function, so a missing or malformed variable stops the app
at start-up with a clear message. Only `config/` reads `process.env`; everything else injects the
typed config. Secrets have no defaults.

## Logs

Nest's `ConsoleLogger({ json: true })` doesn't write the page's fields (`timestampUtc`, `environment`,
`serviceName`, `module`, a `context` object), so a small logger in `common/` adds them; it needs no
logging library:

```ts
@Injectable()
export class JsonLogger implements LoggerService {
  private write(level: string, message: string, module?: string, context: object = {}) {
    process.stdout.write(JSON.stringify({ timestampUtc: new Date().toISOString(), level, message,
      context, environment: process.env.NODE_ENV, serviceName: 'api', module,
      correlationId: correlationStore.getStore() }) + '\n');
  }
  log(message: string, module?: string, context?: object) { this.write('info', message, module, context); }
  warn(message: string, module?: string, context?: object) { this.write('warn', message, module, context); }
  error(message: string, trace?: string, module?: string) { this.write('error', message, module, { trace }); }
  debug(message: string, module?: string, context?: object) { this.write('debug', message, module, context); }
  fatal(message: string, module?: string, context?: object) { this.write('fatal', message, module, context); }
}
// main.ts: NestFactory.create(AppModule, { logger: new JsonLogger() })
```

A middleware in `common/` takes the `x-correlation-id` header (or makes a UUID), keeps it in an
`AsyncLocalStorage` from `node:async_hooks`, sets it on the response and adds it to every log
entry and outgoing call. Log a fixed message with only the fields needed in the context object, never whole objects:

```ts
this.logger.log('Invoice paid', 'InvoiceService', { invoiceId });
```

## Errors

- One global `AllExceptionsFilter` in `common/` catches everything. It logs the error with a new
  `errorId` and the correlation id, then returns the envelope from api.md. For a 500 it returns a
  fixed message. It logs 4xx at debug and 5xx at error.
- In an app that has `libs/organisations`, the filter writes one error report per crash, with
  only the error kind, page path and reference number. Keep error text, stack traces, query
  strings and form data out of the report; let crashes reach the filter without reporting twice.
- Throw Nest's HTTP exceptions (`NotFoundException`, `ConflictException`) with a body of
  `{ code, message, details }`, so the filter can pass the code through.
- A provider catches its vendor's errors and throws our own, with our code (`PAYMENT_DECLINED`),
  never the vendor's text.

## Providers

```ts
export interface PaymentProvider { charge(input: ChargeInput): Promise<ChargeResult>; }

@Injectable()
export class StripePaymentProvider implements PaymentProvider { /* the only file that imports Stripe */ }
```

Register it under a token in the domain's module, and give tests a fake, and local and dev too, so nothing calls the vendor by accident. Set a timeout on every
call, retry only errors that can succeed on retry, and log each call's duration and outcome.
Payment and notification provider calls are idempotent.
