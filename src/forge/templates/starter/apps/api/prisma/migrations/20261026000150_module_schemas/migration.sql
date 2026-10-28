BEGIN;

CREATE SCHEMA "core";
CREATE SCHEMA "history";
CREATE SCHEMA "projects";

ALTER TABLE public."Account" SET SCHEMA "core";
ALTER TABLE public."Session" SET SCHEMA "core";
ALTER TABLE public."PasswordResetToken" SET SCHEMA "core";
ALTER TABLE public."Organisation" SET SCHEMA "core";
ALTER TABLE public."Membership" SET SCHEMA "core";
ALTER TABLE public."Invite" SET SCHEMA "core";
ALTER TABLE public."ChangeRecord" SET SCHEMA "history";
ALTER TABLE public."Project" SET SCHEMA "projects";

ALTER TYPE public."MembershipRole" SET SCHEMA "core";
ALTER TYPE public."ProjectStatus" SET SCHEMA "projects";

COMMIT;
