BEGIN;

ALTER TABLE "Account" ALTER COLUMN "id" SET DEFAULT uuidv7();
ALTER TABLE "Session" ALTER COLUMN "id" SET DEFAULT uuidv7();
ALTER TABLE "PasswordResetToken" ALTER COLUMN "id" SET DEFAULT uuidv7();
ALTER TABLE "Organisation" ALTER COLUMN "id" SET DEFAULT uuidv7();
ALTER TABLE "Membership" ALTER COLUMN "id" SET DEFAULT uuidv7();
ALTER TABLE "Invite" ALTER COLUMN "id" SET DEFAULT uuidv7();
ALTER TABLE "Project" ALTER COLUMN "id" SET DEFAULT uuidv7();
ALTER TABLE "ChangeRecord" ALTER COLUMN "id" SET DEFAULT uuidv7();

CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW."updatedAtUtc" = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER "Account_set_updated_at" BEFORE UPDATE ON "Account"
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER "Organisation_set_updated_at" BEFORE UPDATE ON "Organisation"
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER "Membership_set_updated_at" BEFORE UPDATE ON "Membership"
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER "Invite_set_updated_at" BEFORE UPDATE ON "Invite"
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER "Project_set_updated_at" BEFORE UPDATE ON "Project"
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
