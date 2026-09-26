# Database (Prisma and Postgres)

How the standards page's data rules look in Prisma. Read it when your task adds or changes a table,
a migration or a query.

## Schema

Prisma model and field names become the table and column names, so write them as the standards
page names them and no `@@map` is needed:

```prisma
model Order {
  id                  String        @id @default(uuid()) @db.Uuid
  userId              String        @db.Uuid
  paymentStatus       PaymentStatus @default(UNPAID)
  totalInCents        Int
  isGift              Boolean       @default(false)
  cancelledAtUtc      DateTime?
  createdAtUtc        DateTime      @default(now())
  updatedAtUtc        DateTime      @updatedAt
  deletedAtUtc        DateTime?
  user                User          @relation(fields: [userId], references: [id])

  @@index([userId], map: "idx_Order_userId")
}
```

- Money is an integer in the smallest unit (`totalInCents`), never a float.
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
- Search starts with Postgres full-text search (a `tsvector` column with a GIN index) in raw SQL.

## Migrations

```
npx prisma migrate dev --name add_paymentStatus_to_Order
```

Prisma puts the timestamp in front of the name. Commit the generated SQL, never edit a migration
once it is merged, and write a data change as its own migration. A migration that drops or rewrites
data goes under the story's Risks, with how to recover.

## Tests

Tests run against a real Postgres from `docker-compose.yml`. The test setup creates a database with
a unique name, runs `npx prisma migrate deploy` against it and drops it afterwards, so two
checkouts can run their tests at the same time without sharing rows.
