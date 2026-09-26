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
- Name DTOs `CreateXDto`, `UpdateXDto` and `XResponseDto`.
- Name event files `*.event.ts` and `*.handler.ts`.
- Inject dependencies through constructors; never `new` a service yourself, so tests can swap it.

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
  fixed message; the stack trace goes to the log only. It logs 4xx at debug and 5xx at error.
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
