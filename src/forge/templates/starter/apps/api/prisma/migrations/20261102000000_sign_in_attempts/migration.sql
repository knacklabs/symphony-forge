CREATE TABLE core."SignInAttempt" (
    "id" uuid PRIMARY KEY DEFAULT uuidv7(),
    "email" text NOT NULL,
    "failures" integer NOT NULL DEFAULT 0,
    "expiresAtUtc" timestamptz(3) NOT NULL,
    "createdAtUtc" timestamptz(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAtUtc" timestamptz(3) NOT NULL,
    CONSTRAINT "SignInAttempt_email_lower" CHECK ("email" = lower("email")),
    CONSTRAINT "SignInAttempt_email_format" CHECK (char_length("email") <= 254 AND "email" ~ '^[^@[:space:]]+@[^@[:space:]]+$')
);
CREATE UNIQUE INDEX "SignInAttempt_email_key" ON core."SignInAttempt" ("email");
CREATE TRIGGER "SignInAttempt_set_updated_at" BEFORE UPDATE ON core."SignInAttempt"
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
