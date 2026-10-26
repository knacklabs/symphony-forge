BEGIN;

ALTER TABLE history."ChangeRecord"
    ADD COLUMN "subjectId" UUID,
    ADD COLUMN "subjectName" TEXT,
    ADD CONSTRAINT "ChangeRecord_subjectName_length" CHECK (char_length("subjectName") <= 200);

CREATE INDEX "idx_ChangeRecord_organisationId_subjectId_createdAtUtc"
    ON history."ChangeRecord"("organisationId", "subjectId", "createdAtUtc" DESC);

COMMIT;
