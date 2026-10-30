# Admins remove members in client apps

4 parts · Risks: none one-way · New moving parts: none

## What changes for you

- An admin can remove a member on the Members screen, with a Remove button and a confirm step. Admin is the starters' owner role. The member's sessions end at once, so the next page they open asks them to sign in. The invites that the member sent are cancelled. The change history shows "Removed <email>". The API route is `DELETE /api/v1/members/{accountId}`. An admin cannot remove themself. (Source: your decision, 28 Oct 2026; "Owner" read as the starters' admin role, the planner's choice)
- The agent's guide lists member removal as built in. (Needed by: the removal feature)
- A new client repo gets all of this at `forge init`. An existing client repo gets the guide text with `forge sync` and keeps its app code. (Source: the Forge review rules)

Design: none (starter screens built from the starter's existing dialog, alert and page components; each client app's own design covers them, and the starter has no look of its own)

## Why

A person who leaves keeps their access. No route removes a member. An admin cannot take access away, even when the person has gone.

## Done when

1. **In a new app from either starter, an admin removes a member from the Members screen. The member's sessions end at once, the invites they sent are cancelled, and the change history shows the removal.**
2. **The agent's guide lists member removal as built in. A new repo gets everything at init. An existing repo gets the guide text with forge sync, and its app code does not change.**

## Risks

Risks: none one-way. Each part reverts with its pull request.

Trade-off: a removed person keeps their account, and an invite to the same email is refused with "That person already has an account." A way to bring a removed member back waits for a story that needs it.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-MAIL-1"`. Tests run the forge command and never import forge. For app behaviour, they name the cases that the app's own run reports, through `live_run` (`tests/test_starter_tree.py`), `live_python_starter` (`tests/test_python_starter.py`) and `_require_cases`, as `tests/test_mcp.py` does. Live tests carry `@pytest.mark.platform` and `@pytest.mark.timeout(1800)`. `.github/workflows/starter-smoke.yml` lists and runs `tests/test_member_removal.py` in both jobs, as it does `tests/test_mcp.py`. The existing-repo case uses `_adopted_files_after_sync` from `tests/test_mcp.py`.

TS below means `src/forge/templates/starter`, and PY means `src/forge/templates/starter-python`. The PY web side (`apps/web`, `libs/*/web`) is copied from TS at init (`src/forge/init.py::_starter_files`), so one web change serves both.

### What exists (evidence)

- Members. Roles are `admin` and `member` only (`libs/core/server/src/common/permissions.ts`). `Membership` (`apps/api/prisma/schema/organisations.prisma`) has `deletedAtUtc` and `deletedByAccountId`, and `accountId` is unique. `membershipFor` and `agentForKey` already skip a deleted membership, so the session guard (`libs/auth/server/src/session.guard.ts`) and agent keys already refuse a removed member. `OrganisationsController` (`@Controller('members')`) has change role, key create and revoke, list and export. `changeRole` refuses `CANNOT_CHANGE_OWN_ROLE` and gives `404 MEMBER_NOT_FOUND`. PY `app/organisations/routes.py` and `service.py` match. No route removes a member.
- Module boundaries. `Session`, `PasswordResetToken` and `Account` are auth tables (`apps/api/prisma/schema/auth.prisma`; PY `app/auth/models.py`). The organisations module does not import auth. So the auth module owns any route that ends sessions, as `InvitesController` (`@Controller('invites')`) and `AgentsController` in `libs/auth/server/src` already do. PY `app/auth/routes.py` has `invites_router` and `agents_router` for the same reason, and `app/auth/__init__.py` includes them in its `router`.
- Guide. `src/forge/templates/skill.md` has, in the constitution outline, "- Built in: admins invite people by email; members cannot invite people or change roles."

### Words this story pins

REMOVE pins the route, the codes and the history action. REMOVEPY follows them.

- **Removal.**
  - Route: `DELETE /api/v1/members/{accountId}`, admins only. It answers `200` with `data: null`, as the key revoke does. TS: `RemoveMemberController` with `@Controller('members')` and one `@Delete(':accountId')` in `libs/auth/server/src/members.controller.ts` (new), listed in `auth.module.ts`, with `@AdminOnly()`, `@HttpCode(200)`, `ParseUUIDPipe`, `@ApiOperation({ summary: 'Remove a member from your organisation.', description: 'Only admins can remove members. The member is signed out at once, and the invites they sent are cancelled. You cannot remove yourself.' })` and `@ApiErrors(401, 403, 404)`. PY: `remove_member_router = APIRouter(prefix="/api/v1/members", tags=["Organisations"])` in `app/auth/routes.py`, included in `app/auth/__init__.py` as `invites_router` and `agents_router` are.
  - Codes: `403 CANNOT_REMOVE_SELF` "You cannot remove yourself." and `404 MEMBER_NOT_FOUND` "This member was not found." for an account that is not an active member of the admin's organisation.
  - TS service: `AuthService.removeMember(admin: AccountPrincipal, accountId: string): Promise<void>` runs one `this.prisma.$transaction`. In it: `this.organisations.removeMember(admin, accountId, tx)`, then `tx.session.deleteMany({ where: { accountId } })` and `tx.passwordResetToken.deleteMany({ where: { accountId } })`. `OrganisationsApi` (`libs/organisations/contracts/src/service.ts`) gets `removeMember(admin: OrganisationPrincipal, accountId: string, tx: Prisma.TransactionClient): Promise<void>`. `OrganisationsService.removeMember` checks self first. It finds the active membership in `admin.organisationId`, sets `deletedAtUtc: new Date()`, `deletedByAccountId: admin.id` and `modifiedByAccountId: admin.id`, runs `tx.invite.deleteMany({ where: { organisationId: admin.organisationId, createdByAccountId: accountId } })`, and calls `this.history.record(admin, 'member.removed', 'Removed <email>', undefined, tx)`. An agent membership is removed the same way, and its key stops working because `agentForKey` skips deleted rows.
  - PY service: `AuthService.remove_member(admin, account_id)` calls `OrganisationsService.remove_member(admin, account_id)`, deletes the account's `Session` and `PasswordResetToken` rows, and commits once. `OrganisationsService.remove_member` does the same steps as TS, without its own commit.
  - Web: `useRemoveMember()` in `libs/organisations/web/src/hooks/members-hooks.ts` sends the DELETE and invalidates the members query. In `members-page.tsx`, each row except the admin's own shows, to admins only, an outline destructive `Remove` button with `aria-label="Remove <email>"`. It opens an `AlertDialog` with the title "Remove this member?", the description "<email> loses access at once. Invites they sent are cancelled." and the buttons "Cancel" and "Remove" ("Removing…" while pending). On success a toast says "Member removed." This follows `RevokeKeyDialog` in the same file.
  - Web, the removed member's next page: `ProtectedLayout` in `apps/web/src/app.tsx` calls `account.refetch()` in a `useEffect` keyed on `location.pathname`. Today the account query loads once (`useAccount` sets `refetchOnWindowFocus: false`), and a protected request's 401 only throws an `ApiError`, so a removed member who follows a sidebar link sees an error, not the sign-in page. With the refetch, `/auth/me` answers 401, the query data becomes `null`, and `ProtectedLayout` navigates to `/sign-in`. A refetch keeps the old data while it runs, so the page does not flash the loading text. This costs one `/auth/me` request per page change.

### Done-when details

1. Member removal (REMOVE, REMOVEPY, REMOVEWEB).
   - TS app case, in `apps/api/test/organisations.e2e-spec.ts`: `an admin removes a member, who is signed out at once`.
     - An admin invites a member, who joins (the `invite` helper and accept-invite). The admin makes the member an admin, and the member sends one invite.
     - The first admin's `DELETE /api/v1/members/<id>` answers 200. The removed member's next `GET /api/v1/auth/me` gets 401. The member list and the export no longer hold them.
     - The invite that the removed member sent no longer opens (`400 INVITE_INVALID`).
     - `GET /api/v1/history` holds `member.removed` with "Removed <email>".
     - A second DELETE gets 404 `MEMBER_NOT_FOUND`. The admin's DELETE of their own id gets 403 `CANNOT_REMOVE_SELF`. A member's DELETE gets 403. An id from another organisation gets 404.
     - A removed agent's key gets 401 at `/mcp`.
   - PY app case, in `tests/test_organisations.py`: `test_an_admin_removes_a_member_who_is_signed_out_at_once`, with the same steps.
   - Web case, in `apps/web/e2e/members.spec.ts`: `an admin removes a member, who loses access at once`. The member has the app open on the Projects page in a second browser context. The admin removes them through the dialog. With no reload, the member follows the sidebar's History link and sees the sign-in page. The History page shows the removal. The axe check of the page passes, as in the other members cases.
   - Test `tests/test_member_removal.py::test_1_an_admin_removes_a_member`, parameters `typescript` (REMOVE, REMOVEWEB), `python` (REMOVEPY, REMOVEWEB) and `earlier adopted` (REMOVE). Live: the reports hold the API case and the web case. `earlier adopted`: after upgrade and sync, the files under `libs/` and `apps/` are unchanged.
2. The guide (GUIDE). Compare with whitespace collapsed.
   - `src/forge/templates/skill.md`, constitution outline: change "- Built in: admins invite people by email; members cannot invite people or change roles." to "- Built in: admins invite people by email and remove members, which signs them out at once; members cannot invite, remove people or change roles."
   - `docs/guide.md`: one sentence in the agent accounts paragraph or after it, saying that admins remove members on the Members screen.
   - `forge sync` rewrites `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`.
   - Test `tests/test_member_removal_guide.py::test_2_the_guide_states_member_removal`, parameters `new init` and `previous release`, with the setup of `tests/test_mcp_resources_guide.py::test_3`. Both synced skill copies have the Built in line. `previous release`: after `forge sync`, `git status --porcelain` lists only `LISTED` files.

### New and existing repos

- **New repos** (`forge init --starter`, `forge init --starter python`): member removal in the API and on the Members screen, and the guide text. Plain `forge init` and a newly adopted app get the guide text only.
- **Existing repos** (on upgrade, after `forge sync`): the skill text. They get no app file and no migration. Each item has a test on the adopted earlier-release fixture.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| REMOVE | Member removal in the TypeScript API | `DELETE /api/v1/members/{accountId}` in the auth module, `OrganisationsApi.removeMember`, the ended sessions and reset tokens, the cancelled invites, the `member.removed` history row, and the app's case. | 1 | `src/forge/templates/starter/libs/auth/server/src/members.controller.ts` (new), `starter/libs/auth/server/src/auth.module.ts`, `starter/libs/auth/server/src/auth.service.ts`, `starter/libs/organisations/contracts/src/service.ts`, `starter/libs/organisations/server/src/organisations.service.ts`, `starter/apps/api/test/organisations.e2e-spec.ts`, `tests/test_member_removal.py` | `tests/test_member_removal.py` (`test_1`: `typescript` API half, `earlier adopted`) | FORGE-AGENTREADY-1/RETRY | no | |
| REMOVEPY | Member removal in the Python API | The same route and steps in the Python starter, and its case. Regenerate `libs/shared/api-types`. | 1 | `src/forge/templates/starter-python/apps/api/app/auth/routes.py`, `starter-python/apps/api/app/auth/__init__.py`, `starter-python/apps/api/app/auth/service.py`, `starter-python/apps/api/app/organisations/service.py`, `starter-python/apps/api/tests/test_organisations.py`, `starter-python/libs/shared/api-types/**` (regenerated), `tests/test_member_removal.py` | `tests/test_member_removal.py` (`test_1`: `python` API half) | REMOVE, FORGE-AGENTREADY-1/RETRYPY | no | |
| REMOVEWEB | The Remove button on the Members screen | `useRemoveMember`, the Remove button and dialog, the account refetch on each page change, and the browser case, for both starters. | 1 | `src/forge/templates/starter/libs/organisations/web/src/hooks/members-hooks.ts`, `starter/libs/organisations/web/src/pages/members-page.tsx`, `starter/apps/web/src/app.tsx` (the account refetch on each page change), `starter/apps/web/e2e/members.spec.ts`, `tests/test_member_removal.py` | `tests/test_member_removal.py` (`test_1`: the web case in `typescript` and `python`) | REMOVE, REMOVEPY | yes | |
| GUIDE | The guide lists member removal as built in | The Built in line, the guide sentence and the synced copies, on new and existing repos. | 2 | `src/forge/templates/skill.md`, `docs/guide.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_member_removal_guide.py` (new) | `tests/test_member_removal_guide.py::test_2` (new) | FORGE-AGENTREADY-1/GUIDE | no | |

GUIDE shares no file with the other parts and needs no code from them. REMOVEPY follows REMOVE because REMOVE pins the names. REMOVEWEB follows both APIs because the web is shared and calls the route.

New moving parts: none.

## Notes

- **Order with other work.**
  - FORGE-AGENTREADY-1 changes the same files. RETRY changes `starter/libs/auth/server/src/auth.service.ts` (`invite`), `libs/organisations/contracts/src/service.ts`, `libs/organisations/server/src/organisations.service.ts` (`invite` in one transaction) and `libs/organisations/web/src/hooks/members-hooks.ts` (`useInvite`). RETRYPY changes `app/auth/routes.py`, `app/auth/service.py` and `app/organisations/service.py`. AGENTREADY's GUIDE changes `src/forge/templates/skill.md` and `docs/guide.md` on other lines. So REMOVE waits for RETRY, REMOVEPY for RETRYPY, and GUIDE for AGENTREADY's GUIDE.
  - FORGE-GUIDES-1 changes the starter READMEs, both Dockerfiles, `standards.md`, the conventions and the constitution defaults in `skill.md`. This story changes none of those lines. These are merges, not code needs.
- **Scores (F x H >= 2 x C).**
  - Member removal in each API: 2 x 3 = 6 >= 4. Kept.
  - The Remove button: 2 x 3 = 6 >= 4. Kept, because an owner who does not use the API cannot remove anyone without it.
  - A way to bring back a removed member: 1 x 2 = 2 < 4. Cut.
  - A screen that lists and cancels pending invites: 2 x 1 = 2 < 4. Cut. A new invite already replaces an old one.
- **Owner decisions (30 Oct 2026, settled).** No email setup now: no `SMTP_URL`, `MAIL_FROM`, start check, `compose.yml`, Mailpit, nodemailer or email check on sign-up. Email comes later through SNS or SES directly (kept on `plans/ideas.md`). An admin removes a member: sessions end, a history row, the invites they sent are cancelled.
- **Planner choices the owner did not make.**
  1. "Owner" is the starters' `admin` role, because the starters have only admin and member.
  2. "Pending invites cancelled" means the invites that the removed member sent. A member has no pending invite of their own, because an invite to an email with an account is refused.
  3. The removal route lives in the auth module, because sessions are auth tables and organisations does not import auth.
  4. A removed person cannot be invited again in this story.
  5. A removed member's next page change refetches the account, which sends them to sign-in.
- No client repo is named in this story's code, tests, texts or commits.
