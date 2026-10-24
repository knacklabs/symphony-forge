CREATE TABLE "Invite" (
    "id" UUID NOT NULL,
    "organisationId" UUID NOT NULL,
    "email" TEXT NOT NULL,
    "tokenHash" TEXT NOT NULL,
    "expiresAtUtc" TIMESTAMP(3) NOT NULL,
    "createdAtUtc" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAtUtc" TIMESTAMP(3) NOT NULL,
    "createdByAccountId" UUID NOT NULL,
    "modifiedByAccountId" UUID NOT NULL,
    CONSTRAINT "Invite_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "Invite_organisationId_fkey" FOREIGN KEY ("organisationId") REFERENCES "Organisation"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "Invite_tokenHash_key" ON "Invite"("tokenHash");
CREATE UNIQUE INDEX "Invite_organisationId_email_key" ON "Invite"("organisationId", "email");
CREATE INDEX "idx_Invite_expiresAtUtc" ON "Invite"("expiresAtUtc");
CREATE INDEX "idx_Invite_createdByAccountId" ON "Invite"("createdByAccountId");
CREATE INDEX "idx_Invite_modifiedByAccountId" ON "Invite"("modifiedByAccountId");
