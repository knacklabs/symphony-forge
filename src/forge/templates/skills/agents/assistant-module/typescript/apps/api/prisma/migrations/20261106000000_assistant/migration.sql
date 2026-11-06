CREATE SCHEMA "assistant";
CREATE TABLE "assistant"."AssistantChat" (
  "id" UUID PRIMARY KEY DEFAULT uuidv7(),
  "organisationId" UUID NOT NULL REFERENCES "core"."Organisation"("id"),
  "createdByAccountId" UUID NOT NULL REFERENCES "core"."Account"("id"),
  "modifiedByAccountId" UUID NOT NULL REFERENCES "core"."Account"("id"),
  "lastMessageAtUtc" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "createdAtUtc" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAtUtc" TIMESTAMPTZ(3) NOT NULL
);
CREATE INDEX "idx_AssistantChat_list" ON "assistant"."AssistantChat"
  ("organisationId", "createdByAccountId", "lastMessageAtUtc" DESC, "id" DESC);
CREATE INDEX "idx_AssistantChat_createdByAccountId" ON "assistant"."AssistantChat" ("createdByAccountId");
CREATE INDEX "idx_AssistantChat_modifiedByAccountId" ON "assistant"."AssistantChat" ("modifiedByAccountId");
CREATE INDEX "idx_AssistantChat_lastMessageAtUtc" ON "assistant"."AssistantChat" ("lastMessageAtUtc");
CREATE TRIGGER "AssistantChat_set_updated_at" BEFORE UPDATE ON "assistant"."AssistantChat"
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
