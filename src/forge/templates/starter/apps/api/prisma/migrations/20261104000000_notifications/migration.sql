CREATE SCHEMA "notifications";

CREATE TABLE "notifications"."Notification" (
    "id" UUID NOT NULL DEFAULT uuidv7(),
    "organisationId" UUID NOT NULL,
    "recipientAccountId" UUID NOT NULL,
    "subjectId" UUID NOT NULL,
    "subjectName" TEXT NOT NULL,
    "message" TEXT NOT NULL,
    "createdAtUtc" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "resolvedAtUtc" TIMESTAMPTZ(3),
    CONSTRAINT "Notification_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "Notification_subjectName_length" CHECK (char_length("subjectName") BETWEEN 1 AND 200),
    CONSTRAINT "Notification_message_length" CHECK (char_length("message") <= 10000),
    CONSTRAINT "Notification_organisationId_fkey" FOREIGN KEY ("organisationId") REFERENCES "core"."Organisation"("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Notification_recipientAccountId_fkey" FOREIGN KEY ("recipientAccountId") REFERENCES "core"."Account"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX "idx_Notification_organisationId_fk" ON "notifications"."Notification"("organisationId");
CREATE INDEX "idx_Notification_recipientAccountId_fk" ON "notifications"."Notification"("recipientAccountId");
CREATE INDEX "idx_Notification_subjectId_fk" ON "notifications"."Notification"("subjectId");
CREATE INDEX "idx_Notification_list" ON "notifications"."Notification"("organisationId", "recipientAccountId", "createdAtUtc" DESC, "id" DESC) WHERE "resolvedAtUtc" IS NULL;
CREATE INDEX "idx_Notification_subjectId_open" ON "notifications"."Notification"("organisationId", "subjectId") WHERE "resolvedAtUtc" IS NULL;
