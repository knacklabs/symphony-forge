# Database (Prisma and Postgres)

The database skill (`.codex/skills/database/SKILL.md`) has the rules for new tables, columns,
constraints, indexes and queries. This page has the Prisma how-to. Existing tables keep their
current rules unless a story asks to change them. If the app's constitution differs, follow it.

Each business module owns one schema file under `apps/api/prisma/schema/`. Keep its models in that
file. `base.prisma` holds the generator and datasource; Prisma reads the directory to generate one
client for the app.

## Schema

Prisma model and field names become the table and column names, so write them as the standards
page names them and no `@@map` is needed:

```prisma
model Order {
  id                  String        @id @default(dbgenerated("uuidv7()")) @db.Uuid
  userId              String        @db.Uuid
  paymentStatus       String        @default("UNPAID")
  total               Decimal       @db.Decimal(19, 4)
  totalCurrency       String
  isGift              Boolean       @default(false)
  cancelledAtUtc      DateTime?     @db.Timestamptz(3)
  createdAtUtc        DateTime      @default(now()) @db.Timestamptz(3)
  updatedAtUtc        DateTime      @default(now()) @db.Timestamptz(3)
  deletedAtUtc        DateTime?     @db.Timestamptz(3)
  user                User          @relation(fields: [userId], references: [id])

  @@index([userId], map: "idx_Order_userId")
}
```

- Add the named status CHECK in migration SQL, for example
  `CONSTRAINT "Order_paymentStatus_allowed" CHECK ("paymentStatus" IN ('UNPAID', 'PAID'))`.
- The shared `set_updated_at()` trigger sets `updatedAtUtc` on each update.
- Store dates and times in UTC.
- For money, follow the database skill: use an exact decimal and a separate currency column.
- A boolean has a default, so it never has a third, empty state.
- Add `createdByAccountId`, `modifiedByAccountId` and `deletedByAccountId` once the app has
  accounts.

## Queries

- Filter soft-deleted rows in the query itself (`where: { deletedAtUtc: null }`), where the reader
  can see it, rather than in hidden middleware.
- Delete by setting `deletedAtUtc`. A hard delete is for logs, temporary tables and data the
  client asked to be erased.
- Raw SQL goes through `$queryRaw` with tagged templates, so every value is a parameter, and lives
  in a repository file.
- For search queries and indexes, follow the database skill.

## Migrations

In an app that has `libs/organisations`, each table with `deletedAtUtc` has a
`soft_delete_only()` trigger that refuses a hard delete. Record admin actions through
`HistoryService.record`, never by writing directly to the history table.

```
COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm exec prisma migrate dev --name add_paymentStatus_to_Order
```

Prisma puts the timestamp in front of the name. Commit the generated SQL, never edit a migration
once it is merged, and write a data change as its own migration. A migration that drops or rewrites
data goes under the story's Risks, with how to recover.

## Tests

Tests run against a real Postgres from `compose.test.yml`. The test setup creates a database with
a unique name, runs `COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm exec prisma migrate deploy` against it and drops it afterwards, so two
checkouts can run their tests at the same time without sharing rows.
