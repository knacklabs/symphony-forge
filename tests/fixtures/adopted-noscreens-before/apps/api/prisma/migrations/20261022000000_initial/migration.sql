CREATE TYPE "ProjectStatus" AS ENUM ('active', 'archived');

CREATE TABLE "Account" (
    "id" UUID NOT NULL,
    "email" TEXT NOT NULL,
    "passwordHash" TEXT NOT NULL,
    "createdAtUtc" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAtUtc" TIMESTAMP(3) NOT NULL,
    "createdByAccountId" UUID NOT NULL,
    "modifiedByAccountId" UUID NOT NULL,
    CONSTRAINT "Account_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "Session" (
    "id" UUID NOT NULL,
    "accountId" UUID NOT NULL,
    "tokenHash" TEXT NOT NULL,
    "csrfTokenHash" TEXT NOT NULL,
    "expiresAtUtc" TIMESTAMP(3) NOT NULL,
    "createdAtUtc" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "Session_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "PasswordResetToken" (
    "id" UUID NOT NULL,
    "accountId" UUID NOT NULL,
    "tokenHash" TEXT NOT NULL,
    "expiresAtUtc" TIMESTAMP(3) NOT NULL,
    "createdAtUtc" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "PasswordResetToken_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "Project" (
    "id" UUID NOT NULL,
    "accountId" UUID NOT NULL,
    "name" VARCHAR(120) NOT NULL,
    "status" "ProjectStatus" NOT NULL DEFAULT 'active',
    "createdAtUtc" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAtUtc" TIMESTAMP(3) NOT NULL,
    "createdByAccountId" UUID NOT NULL,
    "modifiedByAccountId" UUID NOT NULL,
    "deletedAtUtc" TIMESTAMP(3),
    "deletedByAccountId" UUID,
    CONSTRAINT "Project_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "Account_email_key" ON "Account"("email");
CREATE INDEX "idx_Account_createdByAccountId" ON "Account"("createdByAccountId");
CREATE INDEX "idx_Account_modifiedByAccountId" ON "Account"("modifiedByAccountId");
CREATE UNIQUE INDEX "Session_tokenHash_key" ON "Session"("tokenHash");
CREATE INDEX "idx_Session_accountId" ON "Session"("accountId");
CREATE INDEX "idx_Session_expiresAtUtc" ON "Session"("expiresAtUtc");
CREATE UNIQUE INDEX "PasswordResetToken_tokenHash_key" ON "PasswordResetToken"("tokenHash");
CREATE INDEX "idx_PasswordResetToken_accountId" ON "PasswordResetToken"("accountId");
CREATE INDEX "idx_PasswordResetToken_expiresAtUtc" ON "PasswordResetToken"("expiresAtUtc");
CREATE INDEX "idx_Project_accountId" ON "Project"("accountId");
CREATE INDEX "idx_Project_createdByAccountId" ON "Project"("createdByAccountId");
CREATE INDEX "idx_Project_modifiedByAccountId" ON "Project"("modifiedByAccountId");
CREATE INDEX "idx_Project_deletedByAccountId" ON "Project"("deletedByAccountId");

ALTER TABLE "Account" ADD CONSTRAINT "Account_createdByAccountId_fkey" FOREIGN KEY ("createdByAccountId") REFERENCES "Account"("id") ON DELETE NO ACTION ON UPDATE CASCADE;
ALTER TABLE "Account" ADD CONSTRAINT "Account_modifiedByAccountId_fkey" FOREIGN KEY ("modifiedByAccountId") REFERENCES "Account"("id") ON DELETE NO ACTION ON UPDATE CASCADE;
ALTER TABLE "Session" ADD CONSTRAINT "Session_accountId_fkey" FOREIGN KEY ("accountId") REFERENCES "Account"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "PasswordResetToken" ADD CONSTRAINT "PasswordResetToken_accountId_fkey" FOREIGN KEY ("accountId") REFERENCES "Account"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "Project" ADD CONSTRAINT "Project_accountId_fkey" FOREIGN KEY ("accountId") REFERENCES "Account"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "Project" ADD CONSTRAINT "Project_createdByAccountId_fkey" FOREIGN KEY ("createdByAccountId") REFERENCES "Account"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "Project" ADD CONSTRAINT "Project_modifiedByAccountId_fkey" FOREIGN KEY ("modifiedByAccountId") REFERENCES "Account"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "Project" ADD CONSTRAINT "Project_deletedByAccountId_fkey" FOREIGN KEY ("deletedByAccountId") REFERENCES "Account"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
