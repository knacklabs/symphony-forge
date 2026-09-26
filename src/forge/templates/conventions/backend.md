# Backend (NestJS)

How the standards page's backend rules look in NestJS. Read it when your task adds or changes a
module, the config, logging or error handling.

## Layout

```
apps/api/src/
  main.ts               start-up: validation, the exception filter, security, Swagger, JSON logs
  app.module.ts
  config/               the one place that reads environment variables
  common/               the exception filter, the response envelope, the correlation id
  health/               GET /health, so a deploy can check the app is up
  <domain>/             one folder per business domain
    <domain>.module.ts
    <domain>.controller.ts
    <domain>.service.ts
    dto/
    <vendor>.provider.ts    only when the domain calls an external system
```

## Modules

- A module's `exports` list holds its service and nothing else. Another module imports the module
  and calls that service; it never reaches into the folder's other files or its tables.
- Services query through `PrismaService`. Move a query into `<domain>.repository.ts` when a second
  service needs it or it is raw SQL.
- Inject dependencies through constructors; never `new` a service yourself, so tests can swap it.

## Config

Use `@nestjs/config` with a `validate` function, so a missing or malformed variable stops the app
at start-up with a clear message. Only `config/` reads `process.env`; everything else injects the
typed config. Secrets have no defaults.

## Logs

NestJS's own logger writes JSON, so no logging library is needed:

```ts
const app = await NestFactory.create(AppModule, { logger: new ConsoleLogger({ json: true }) });
```

A middleware in `common/` takes the `x-correlation-id` header (or makes a UUID), keeps it in an
`AsyncLocalStorage` from `node:async_hooks`, sets it on the response and adds it to every log
entry and outgoing call. Log a fixed message with the details in a context object:

```ts
this.logger.log({ message: 'Invoice paid', context: { invoiceId }, correlationId });
```

## Errors

- One global `AllExceptionsFilter` in `common/` catches everything. It logs the error with a new
  `errorId` and the correlation id, then returns the envelope from api.md. For a 500 it returns a
  fixed message; the stack trace goes to the log only.
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

Register it under a token in the domain's module, and give tests a fake. Set a timeout on every
call, retry only errors that can succeed on retry, and log each call's duration and outcome.
