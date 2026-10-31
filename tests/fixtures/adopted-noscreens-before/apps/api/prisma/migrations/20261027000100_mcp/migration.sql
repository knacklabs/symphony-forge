CREATE SCHEMA "mcp";

CREATE TABLE "mcp"."IdempotencyKey" (
    "id" UUID NOT NULL DEFAULT uuidv7(),
    "organisationId" UUID NOT NULL,
    "accountId" UUID NOT NULL,
    "tool" TEXT NOT NULL,
    "key" TEXT NOT NULL,
    "itemId" UUID NOT NULL,
    "createdAtUtc" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "IdempotencyKey_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "IdempotencyKey_tool_length" CHECK (char_length("tool") BETWEEN 1 AND 200),
    CONSTRAINT "IdempotencyKey_key_length" CHECK (char_length("key") BETWEEN 1 AND 200),
    CONSTRAINT "uq_IdempotencyKey_account_tool_key" UNIQUE ("accountId", "tool", "key"),
    CONSTRAINT "IdempotencyKey_organisationId_fkey" FOREIGN KEY ("organisationId") REFERENCES "core"."Organisation"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "IdempotencyKey_accountId_fkey" FOREIGN KEY ("accountId") REFERENCES "core"."Account"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX "idx_IdempotencyKey_organisationId" ON "mcp"."IdempotencyKey"("organisationId");
CREATE INDEX "idx_IdempotencyKey_itemId" ON "mcp"."IdempotencyKey"("itemId");
