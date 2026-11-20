CREATE TABLE "assistant"."AssistantUsage" (
  "id" UUID CONSTRAINT "AssistantUsage_pkey" PRIMARY KEY DEFAULT uuidv7(),
  "accountId" UUID NOT NULL,
  "chatId" UUID,
  "kind" TEXT NOT NULL DEFAULT 'llm',
  "inputTokens" INTEGER NOT NULL,
  "outputTokens" INTEGER NOT NULL,
  "costMicros" BIGINT NOT NULL,
  "createdAtUtc" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "AssistantUsage_accountId_fkey" FOREIGN KEY ("accountId") REFERENCES "core"."Account"("id") ON DELETE RESTRICT,
  CONSTRAINT "AssistantUsage_chatId_fkey" FOREIGN KEY ("chatId") REFERENCES "assistant"."AssistantChat"("id") ON DELETE SET NULL,
  CONSTRAINT "AssistantUsage_kind_allowed" CHECK ("kind" IN ('llm')),
  CONSTRAINT "AssistantUsage_inputTokens_nonnegative" CHECK ("inputTokens" >= 0),
  CONSTRAINT "AssistantUsage_outputTokens_nonnegative" CHECK ("outputTokens" >= 0),
  CONSTRAINT "AssistantUsage_costMicros_nonnegative" CHECK ("costMicros" >= 0)
);
CREATE INDEX "idx_AssistantUsage_accountId" ON "assistant"."AssistantUsage" ("accountId");
CREATE INDEX "idx_AssistantUsage_chatId" ON "assistant"."AssistantUsage" ("chatId");
CREATE INDEX "idx_AssistantUsage_createdAtUtc" ON "assistant"."AssistantUsage" ("createdAtUtc");
