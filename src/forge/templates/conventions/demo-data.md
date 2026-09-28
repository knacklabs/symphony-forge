# Demo data

How a prototype shows the client their own work instead of empty screens. Read it when your task
builds the prototype's first version or changes its demo data.

## What it holds

- The loader lives in the app, in `backend/src/demo/`. Forge ships this page, not the code.
- Its records are shaped from the column headers of the spreadsheet or form the client uses today,
  and every label comes from the "Words they use" list in `docs/product/DISCOVERY.md`.
- The values are made up but look like theirs. It holds no real personal data: no real names,
  emails, phone numbers or addresses, even when the client's own sheet has them.

## When it runs

It runs only when `APP_ENV=demo` and `DEMO_DATA=1` are both set and every app table is empty.
Otherwise it refuses, logs why and inserts nothing, so it can never touch production or mix with
real rows:

```ts
@Injectable()
export class DemoDataService {
  constructor(private readonly prisma: PrismaService, private readonly config: AppConfig,
              private readonly logger: JsonLogger) {}

  async loadIfAllowed() {
    if (this.config.appEnv !== 'demo' || this.config.demoData !== '1') {
      return this.logger.log('Demo data refused: needs APP_ENV=demo and DEMO_DATA=1', 'DemoData');
    }
    const models = Object.values(Prisma.ModelName);
    const counts = await Promise.all(models.map((m) =>
      (this.prisma as any)[m[0].toLowerCase() + m.slice(1)].count()));  // every app table
    if (counts.some((n) => n > 0)) {
      return this.logger.warn('Demo data refused: the app tables already hold rows', 'DemoData');
    }
    await this.prisma.$transaction(async (tx) => { /* insert the records, all or nothing */ });
  }
}
```

`config/` reads `APP_ENV` and `DEMO_DATA` like every other variable (see backend.md).

## Start-up

The API's start command runs `npx prisma migrate deploy` before `node dist/main.js`, so the tables
exist first. Then `main.ts` calls the loader once, before it starts listening:

```ts
const app = await NestFactory.create(AppModule, { logger: new JsonLogger() });
await app.get(DemoDataService).loadIfAllowed();
await app.listen(port);
```

Tests never set `DEMO_DATA`, so they always start empty (see testing.md).
