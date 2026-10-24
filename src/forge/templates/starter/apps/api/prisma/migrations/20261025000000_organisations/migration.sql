CREATE TYPE "MembershipRole" AS ENUM ('admin', 'member');

CREATE TABLE "Organisation" (
    "id" UUID NOT NULL,
    "createdAtUtc" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAtUtc" TIMESTAMP(3) NOT NULL,
    "createdByAccountId" UUID NOT NULL,
    "modifiedByAccountId" UUID NOT NULL,
    "deletedAtUtc" TIMESTAMP(3),
    "deletedByAccountId" UUID,
    CONSTRAINT "Organisation_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "Membership" (
    "id" UUID NOT NULL,
    "accountId" UUID NOT NULL,
    "organisationId" UUID NOT NULL,
    "email" TEXT NOT NULL,
    "role" "MembershipRole" NOT NULL,
    "createdAtUtc" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAtUtc" TIMESTAMP(3) NOT NULL,
    "createdByAccountId" UUID NOT NULL,
    "modifiedByAccountId" UUID NOT NULL,
    "deletedAtUtc" TIMESTAMP(3),
    "deletedByAccountId" UUID,
    CONSTRAINT "Membership_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "Membership_accountId_key" ON "Membership"("accountId");
CREATE INDEX "idx_Membership_organisationId" ON "Membership"("organisationId");
CREATE INDEX "idx_Organisation_createdByAccountId" ON "Organisation"("createdByAccountId");
CREATE INDEX "idx_Organisation_modifiedByAccountId" ON "Organisation"("modifiedByAccountId");
CREATE INDEX "idx_Organisation_deletedByAccountId" ON "Organisation"("deletedByAccountId");
CREATE INDEX "idx_Membership_createdByAccountId" ON "Membership"("createdByAccountId");
CREATE INDEX "idx_Membership_modifiedByAccountId" ON "Membership"("modifiedByAccountId");
CREATE INDEX "idx_Membership_deletedByAccountId" ON "Membership"("deletedByAccountId");
ALTER TABLE "Membership" ADD CONSTRAINT "Membership_accountId_fkey" FOREIGN KEY ("accountId") REFERENCES "Account"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "Membership" ADD CONSTRAINT "Membership_organisationId_fkey" FOREIGN KEY ("organisationId") REFERENCES "Organisation"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE "Project" DROP CONSTRAINT "Project_accountId_fkey";
DROP INDEX "idx_Project_accountId";
ALTER TABLE "Project" DROP COLUMN "accountId", ADD COLUMN "organisationId" UUID NOT NULL;
CREATE INDEX "idx_Project_organisationId" ON "Project"("organisationId");
ALTER TABLE "Project" ADD CONSTRAINT "Project_organisationId_fkey" FOREIGN KEY ("organisationId") REFERENCES "Organisation"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
