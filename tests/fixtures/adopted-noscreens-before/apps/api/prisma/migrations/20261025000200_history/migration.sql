CREATE TABLE "ChangeRecord" (
    "id" UUID NOT NULL,
    "organisationId" UUID NOT NULL,
    "actorAccountId" UUID NOT NULL,
    "actorEmail" TEXT NOT NULL,
    "action" TEXT NOT NULL,
    "summary" TEXT NOT NULL,
    "createdAtUtc" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "ChangeRecord_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "idx_ChangeRecord_organisationId_createdAtUtc" ON "ChangeRecord"("organisationId", "createdAtUtc");
CREATE INDEX "idx_ChangeRecord_actorAccountId" ON "ChangeRecord"("actorAccountId");
