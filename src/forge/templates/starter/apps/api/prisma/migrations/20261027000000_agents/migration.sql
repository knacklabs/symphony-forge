BEGIN;

ALTER TABLE core."Membership"
    ADD COLUMN "isAgent" BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN "agentKeyHash" TEXT;

CREATE UNIQUE INDEX "Membership_agentKeyHash_key" ON core."Membership"("agentKeyHash");

ALTER TABLE core."Organisation"
    ADD COLUMN "agentDeleteRestore" TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];

COMMIT;
