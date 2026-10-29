BEGIN;

ALTER TABLE history."ChangeRecord"
    ADD COLUMN "viaAgent" TEXT,
    ADD CONSTRAINT "ChangeRecord_viaAgent_length" CHECK ("viaAgent" IS NULL OR char_length("viaAgent") BETWEEN 1 AND 200);

COMMIT;
