BEGIN;

ALTER TABLE core."Account"
    ALTER COLUMN "createdAtUtc" TYPE TIMESTAMPTZ(3) USING "createdAtUtc" AT TIME ZONE 'UTC',
    ALTER COLUMN "updatedAtUtc" TYPE TIMESTAMPTZ(3) USING "updatedAtUtc" AT TIME ZONE 'UTC',
    ADD CONSTRAINT "Account_email_lower" CHECK ("email" = lower("email"));

ALTER TABLE core."Session"
    ALTER COLUMN "expiresAtUtc" TYPE TIMESTAMPTZ(3) USING "expiresAtUtc" AT TIME ZONE 'UTC',
    ALTER COLUMN "createdAtUtc" TYPE TIMESTAMPTZ(3) USING "createdAtUtc" AT TIME ZONE 'UTC';

ALTER TABLE core."PasswordResetToken"
    ALTER COLUMN "expiresAtUtc" TYPE TIMESTAMPTZ(3) USING "expiresAtUtc" AT TIME ZONE 'UTC',
    ALTER COLUMN "createdAtUtc" TYPE TIMESTAMPTZ(3) USING "createdAtUtc" AT TIME ZONE 'UTC';

ALTER TABLE core."Organisation"
    ALTER COLUMN "createdAtUtc" TYPE TIMESTAMPTZ(3) USING "createdAtUtc" AT TIME ZONE 'UTC',
    ALTER COLUMN "updatedAtUtc" TYPE TIMESTAMPTZ(3) USING "updatedAtUtc" AT TIME ZONE 'UTC',
    ALTER COLUMN "deletedAtUtc" TYPE TIMESTAMPTZ(3) USING "deletedAtUtc" AT TIME ZONE 'UTC';

ALTER TABLE core."Membership"
    ALTER COLUMN "role" TYPE TEXT USING "role"::text,
    ALTER COLUMN "createdAtUtc" TYPE TIMESTAMPTZ(3) USING "createdAtUtc" AT TIME ZONE 'UTC',
    ALTER COLUMN "updatedAtUtc" TYPE TIMESTAMPTZ(3) USING "updatedAtUtc" AT TIME ZONE 'UTC',
    ALTER COLUMN "deletedAtUtc" TYPE TIMESTAMPTZ(3) USING "deletedAtUtc" AT TIME ZONE 'UTC',
    ADD CONSTRAINT "Membership_role_allowed" CHECK ("role" IN ('admin', 'member'));

ALTER TABLE core."Invite"
    ALTER COLUMN "expiresAtUtc" TYPE TIMESTAMPTZ(3) USING "expiresAtUtc" AT TIME ZONE 'UTC',
    ALTER COLUMN "createdAtUtc" TYPE TIMESTAMPTZ(3) USING "createdAtUtc" AT TIME ZONE 'UTC',
    ALTER COLUMN "updatedAtUtc" TYPE TIMESTAMPTZ(3) USING "updatedAtUtc" AT TIME ZONE 'UTC',
    ADD CONSTRAINT "Invite_email_lower" CHECK ("email" = lower("email"));

ALTER TABLE projects."Project" ALTER COLUMN "status" DROP DEFAULT;
ALTER TABLE projects."Project"
    ALTER COLUMN "name" TYPE TEXT USING "name"::text,
    ALTER COLUMN "status" TYPE TEXT USING "status"::text,
    ALTER COLUMN "status" SET DEFAULT 'active',
    ALTER COLUMN "createdAtUtc" TYPE TIMESTAMPTZ(3) USING "createdAtUtc" AT TIME ZONE 'UTC',
    ALTER COLUMN "updatedAtUtc" TYPE TIMESTAMPTZ(3) USING "updatedAtUtc" AT TIME ZONE 'UTC',
    ALTER COLUMN "deletedAtUtc" TYPE TIMESTAMPTZ(3) USING "deletedAtUtc" AT TIME ZONE 'UTC',
    ADD CONSTRAINT "Project_status_allowed" CHECK ("status" IN ('active', 'archived')),
    ADD CONSTRAINT "Project_name_length" CHECK (char_length("name") BETWEEN 1 AND 120);

ALTER TABLE history."ChangeRecord"
    ALTER COLUMN "createdAtUtc" TYPE TIMESTAMPTZ(3) USING "createdAtUtc" AT TIME ZONE 'UTC';

DROP TYPE core."MembershipRole";
DROP TYPE projects."ProjectStatus";

COMMIT;
