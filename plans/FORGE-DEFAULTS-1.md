# New client apps start with the constitution's built-in defaults

9 parts · Risks: none one-way · New moving parts: a database rule that refuses to remove a record completely

## What changes for you

- A new client app starts with organisations. Each person belongs to one organisation, as an
  admin or a member. The app shows a person only the records of their own organisation.
- Admins invite people by email. A member cannot invite people or change roles.
- The app records who sent each invite and who changed each role. Admins see this on a change
  history screen.
- The app shows all dates, times and money in one format, in the person's time zone, from shared
  code. The tests fail when new code formats them in a different way.
- Each list in the app has an Export CSV button, and all exports use the same code. The export
  writes a cell that a spreadsheet can run as a formula as plain text.
- The database keeps deleted records and marks them as deleted. It refuses to remove a record
  completely.
- When a screen or the server crashes, the app writes one error report to its logs. A later story
  can send these reports to an error tracking service.
- The app's constitution lists these defaults as built in, so the agent does not ask about them.
- Existing apps keep their code. On upgrade they get only the guide and the rules text.
- This work starts after the React defaults and the zod changes to the starter merge.

Design: docs/design/FORGE-DEFAULTS-1/ (3334cdb7687ed1416c8a11ca5b10f1f79b19d0aa)

## Why

The constitution's defaults promise organisations with admin and member roles, email invites,
one date and money format, a CSV export for each table, change history for admin actions, soft
delete and error tracking. The starter builds none of them, so the agent of each new app decides
and builds its own version. Today the starter scopes data to one account, not to an
organisation. It has no roles, invites, CSV export, money format or web error report, and the
projects page formats its dates with its own local code. On 24 October 2026 the owner chose to
build these once in the starter, as modules that follow the module rules, and not to leave the
choice to the FDE.

## Done when

1. **In a new client app, each person belongs to one organisation, and the app never returns one organisation's records to another.**
2. **Admins can invite people by email, and members cannot change roles or invite people.**
3. **Date, time and money display come only from shared helpers, and a lint rule fails hand-written formatting in API and web.**
4. **Each table has a CSV export from one shared code path, admin actions write change history, and the database refuses to remove a record completely.**
5. **A UI crash and an API crash each write one error report to the logs.**
6. **A new app's constitution lists these defaults as built in, the starter's tests pass, and an existing app's code is unchanged after upgrade.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request. The new migrations change only the
starter, which a new app copies at set-up; no existing app gets them.

Trade-off: a person belongs to one organisation only. An invite to an email that already has an
account is refused. A later story can let one person join more organisations if a client needs
it.

Trade-off: the starter sends invites only where the app has a mail provider. In local and test
runs the invite link goes to the log, as the password reset link does now. In production the app
refuses an invite with a clear message until a story adds a real mail provider.

Trade-off: the change history covers the admin actions that the starter has: invites and role
changes. Each admin action that a later story adds records itself in the same way.

Trade-off: the person's time zone is the time zone of their browser. The app does not keep a time
zone for each person.

Trade-off: the error report keeps only the kind of error, the page path and a reference number. It
keeps no error text, no code lines, no query string and no form data, so it cannot hold personal
data or tokens.

Trade-off: a CSV cell that starts with `=`, `+`, `-` or `@` can run as a formula when the file
opens in a spreadsheet. The shared export puts a `'` before such a cell, so the spreadsheet shows
it as text. The owner chose this guard on 24 October 2026.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-DEFAULTS-1"`. Each test runs the forge command or,
for the starter's own behaviour, reads the starter's files or runs its own commands, and never
imports forge. One test per Done-when rule, named `test_<n>_...`. The starter's behaviour is
proven first by its own end-to-end cases: Supertest cases against the real Postgres and API in
`compose.test.yml`, and Playwright flows against the built app. `starter-smoke` runs them live
(`FORGE_STARTER_LIVE=1`), and every case in its reports must pass. Each part's pytest test
requires its own case names from that run, so a deleted case fails it. Live tests carry
`@pytest.mark.platform` and `@pytest.mark.timeout(1800)`, as `tests/test_starter_tree.py` does.
Forge-command tests (GUIDE) run on a new repo and on a repo adopted on an earlier release, as
`test_4` of `tests/test_app_constitution.py` does.

**Plan against the merged starter.** FORMATS and ERRORS start after
FORGE-REACTDEFAULTS-1/STARTER (React Compiler, the data router, `RouteErrorPage` in
`apps/web/src/components/route-error-page.tsx`, the projects page without hand memoization) and
the zod story's starter part (the projects list query as a zod schema in `@app/shared`, no
class-validator). Read the merged starter before you start; where a path below differs from the
merged tree, follow the merged tree.

**Module graph after this story.** `@app/auth` uses `@app/organisations`; `@app/organisations`
uses `@app/history`; `@app/projects` no longer uses `@app/auth`. Every module uses `@app/core` and
`@app/shared`. No cycle, so Nx's module-boundary rule keeps passing. A new module is wired as
`libs/projects` is: `package.json` (`@app/<name>`, `exports` with only `.`), `project.json` (tag
`type:module`), `tsconfig.json` with references, an entry in `apps/api/package.json` and the
references of `apps/api/tsconfig.json`, its importer in `pnpm-lock.yaml` (`corepack pnpm
install`), its `dist` folder in `scripts/test-build.mjs`, and its name in the libs list and its
schema file in the schema set of `tests/test_starter_tree.py::test_1`.

**Words this story pins.** The part named first owns each name; later parts use it and list that
part under After.

- Format helpers (FORMATS), `libs/shared/src/format.ts`, exported from `@app/shared`:
  `formatDate(value: string | Date, timeZone?: string)` gives `2026-10-24`;
  `formatTime(value, timeZone?)` gives `14:05` (24-hour); `formatDateTime(value, timeZone?)`
  gives `2026-10-24 14:05`; `formatNumber(value: number, fractionDigits = 0)` gives `1,234.56`;
  `formatMoney(cents: number, currency = 'USD')` gives `USD 1,234.56` (`USD -1,234.56` below
  zero) and throws a `RangeError` for cents that are not an integer. With no `timeZone` they use
  the runtime's zone, which in the browser is the person's zone; the API passes `'UTC'`. These are
  the constitution's default formats; a comment in the file says that an app whose constitution
  chooses other formats changes them here.
- Lint message (FORMATS): `Format dates, times, numbers and money with the helpers in
  @app/shared.`
- Error report schema (FORMATS pins it, ERRORS uses it), in `libs/shared/src/index.ts`:
  `errorReportSchema = z.object({ name: z.string().max(200), path: z.string().max(2000)
  }).strict()` and `type ErrorReportInput`. The zod rules want each request schema in
  `@app/shared`, and FORMATS already owns that file's lines before ERRORS and ORGS run side by
  side.
- CSV (FORMATS), `libs/core/src/common/csv.ts`, exported from `@app/core`:
  `type CsvColumn<T> = { header: string; value: (row: T) => string | number | null }` and
  `sendCsv<T>(response: Response, filename: string, columns: CsvColumn<T>[], rows: T[]): void`.
  It sends `Content-Type: text/csv; charset=utf-8` and `Content-Disposition: attachment;
  filename="<filename>"`, a header row, CRLF line ends, and quotes a field that has `"`, `,`, CR
  or LF, with its quotes doubled. A date column uses `formatDateTime(value, 'UTC')`, and its
  header ends ` (UTC)`.
  Formula guard: a cell whose text starts with `=`, `+`, `-` or `@` gets a leading `'` (the owner's choice); the exports API case checks one such cell.
- Export routes, each declared before any `:id` route of its controller and scoped like the list:
  `GET /api/v1/projects/export` gives `projects.csv` with `Name,Status,Created (UTC),Updated
  (UTC)` (FORMATS); `GET /api/v1/members/export` gives `members.csv` with `Email,Role,Joined
  (UTC)` (ORGS); `GET /api/v1/history/export` gives `change-history.csv` with `When (UTC),Who,What`
  (HISTORY, admin only). Each list screen's button is `<Button variant="outline" asChild><a
  href="/api/v1/<list>/export" download>Export CSV</a></Button>`.
- Test helpers (FORMATS). `apps/api/test/helpers.ts`: `apiBaseUrl`, `productionApiBaseUrl`,
  `credentials()`, `csrfToken(response)`, `logEvents(service)` (the JSON log lines of
  `docker compose -f compose.test.yml logs --no-color <service>`, parsed, as
  `{ message, context, ... }[]`) and `psql(sql)` (`docker compose -f compose.test.yml exec -T
  database psql -U postgres -d starter_test -v ON_ERROR_STOP=1 -c <sql>`, returning its exit
  status and output). `apps/web/e2e/helpers.ts`: `password`, `newEmail()`, `signUp(page, email?)`,
  `signIn(page, email)`, `csrfToken(page)` and `logEvents(service)`. The web copy of `logEvents`
  is a second copy on purpose: Nx refuses a relative import from `apps/web` into `apps/api`. The
  existing specs import these helpers in place of their local copies.
- Live run (FORMATS), `tests/test_starter_tree.py`: the body of the `live_starter` fixture becomes
  `live_run(tmp_path_factory)` with `@functools.cache`, and the fixture returns `live_run(...)`.
  The run cleans up before it returns, so the cached result is safe to share. A new test file
  calls `live_run(tmp_path_factory)` and `_require_cases(...)` from `test_starter_tree`, so the
  stack runs once per pytest session. `starter-smoke.yml` runs `tests/test_defaults_*.py` with the
  two files it runs now, and its `paths` add the same glob.
- `tests/test_defaults_formats.py::CSV_API_CASES` (FORMATS): the tuple of export API case names
  that `test_4_each_table_exports_csv_from_one_shared_code_path` requires. ORGS and HISTORY add
  their names to it.
- Session cache (MEMBERS): `apps/web/src/features/auth/hooks/auth-hooks.ts` calls
  `queryClient.clear()` on sign-in, sign-up and sign-out, in place of `clearProjectCache`, so no
  list of one account (projects, members, change history) shows after a switch in the same tab.
  JOIN's accept-invite hook does the same.
- Organisations (ORGS): library `libs/organisations`, package `@app/organisations`, schema
  `apps/api/prisma/schema/organisations.prisma` with `enum MemberRole { admin member }`,
  `Organisation { id, createdAtUtc, updatedAtUtc }` and `Membership { id, organisationId,
  accountId @unique, email, role, createdAtUtc, updatedAtUtc }`. `Project.organisationId`
  replaces `Project.accountId`. `OrganisationsService.createForAccount(account: { id; email })`,
  `membershipFor(accountId): Promise<{ organisationId: string; role: MemberRole } | null>` and
  `listMembers(principal)`.
- Principal (ORGS), moved into core: `libs/core/src/common/account-principal.ts` with
  `AccountPrincipal = { id: string; email: string; organisationId: string; role: MemberRole }`,
  and `libs/core/src/common/current-account.decorator.ts` with `CurrentAccount`. Both export from
  `@app/core` and no longer from `@app/auth`. `AuthenticatedRequest.principal` has this type.
- Shared types (ORGS): `memberRoleSchema`, `MemberRole`, `Member = { accountId; email; role;
  joinedAtUtc }`, and `Account = { id; email; role }`.
- Admin guard (INVITES), `libs/core/src/common/admin-only.decorator.ts`: `AdminOnly()` refuses
  anyone but an admin with `403 { code: 'ADMIN_ONLY', message: 'Only an admin can do that.',
  details: null }`.
- Mail (INVITES), moved from `libs/auth/src/mail.provider.ts` into `libs/core/src/mail/`:
  `mail.provider.ts` (`MAIL_PROVIDER`, `MailProvider` with `sendPasswordReset(email, resetUrl)`
  and `sendInvite(email, inviteUrl)`, and `LogMailProvider`, which logs `Invite link created for
  local mail` with `{ inviteUrl }`) and `mail.module.ts` (`MailModule`, `@Global()`, with the
  factory that `AuthModule` has today). The invite URL is `<APP_ORIGIN>/accept-invite?token=<token>`.
- Invites (INVITES): `Invite { id, organisationId, email, tokenHash @unique, expiresAtUtc,
  invitedByAccountId, createdAtUtc, updatedAtUtc, @@unique([organisationId, email]) }` in
  `organisations.prisma`; a token of 32 random bytes in base64url, kept as its SHA-256; 7 days.
  `OrganisationsService.invite(principal, email)`, `openInvite(token)`,
  `joinFromInvite(inviteId, account)` and `changeRole(principal, accountId, role)`. Shared
  schemas `inviteSchema`, `acceptInviteSchema` and `roleChangeSchema`.
- API codes (INVITES): `POST /api/v1/invites` `{ email }`, admin only, gives `201 { email,
  expiresAtUtc }`; `409 EMAIL_ALREADY_REGISTERED` ("That person already has an account.") when any
  membership has that email; `422 MAIL_NOT_CONFIGURED` ("Email is not set up for this app yet.")
  when there is no mail provider (a 4xx, so the exception filter keeps its message unchanged).
  `PUT /api/v1/members/:accountId/role` `{ role }`, admin only, gives `200` with the member;
  `400 CANNOT_CHANGE_OWN_ROLE`; `404 MEMBER_NOT_FOUND` when no membership has that account id and
  the caller's `organisationId` (`changeRole` filters on both).
  `POST /api/v1/auth/accept-invite` `{ token, email, password }`, public, 30 a minute, gives `201`
  with the account and the session cookies; `400 INVITE_INVALID` ("This invite link is not valid.
  Ask an admin for a new one."); `409 EMAIL_ALREADY_REGISTERED`.
- Screens (MEMBERS, JOIN, HISTORY): the routes, texts, components and fields in
  `docs/design/FORGE-DEFAULTS-1/SCREENS.md`. Routes `/members` and `/history` sit inside the
  protected layout; `/accept-invite` is public.
- History (HISTORY): library `libs/history`, package `@app/history`, schema
  `apps/api/prisma/schema/history.prisma` with `ChangeRecord { id, organisationId,
  actorAccountId, actorEmail, action, summary, createdAtUtc }` and an index on `(organisationId,
  createdAtUtc)`, with no foreign keys, so it needs no line in another module's schema.
  `HistoryService.record(principal, action, summary)` and `list(principal)`. Actions:
  `member.invited` with `Invited <email>`, and `member.role_changed` with `Changed <email> from
  <old role> to <new role>`. `GET /api/v1/history`, admin only, gives the newest 100 records as
  `{ id, actorEmail, summary, createdAtUtc }[]`.
- Soft delete rule (SOFTDELETE): the migration `20261025000300_soft_delete_only` creates the function `soft_delete_only()`, which
  raises `Rows in <table> are soft deleted. Set "deletedAtUtc" instead.`, and the trigger
  `Project_soft_delete_only` `BEFORE DELETE ON "Project" FOR EACH ROW`. A later table with
  `deletedAtUtc` adds its own trigger line in its migration.
- Error report (ERRORS), `libs/core/src/common/error-report.ts`: `ErrorReporter.report(input: {
  source: 'api' | 'web'; name: string; path: string; status?: number; method?: string;
  errorId?: string }): string` writes one `error` log line with the message `Error report`, the
  module `ErrorReporter` and the context `{ errorId, source, name, path, status?, method? }`, and
  returns the `errorId`. `JsonLogger` adds the correlation id. `name` is the error's class name
  (`error.constructor.name`, or `Error`). The report holds no exception message and no stack, as
  the filter logs none today: Node's stack starts with the message, and a message can run over
  many lines. `ErrorReportsController`: `POST /api/v1/error-reports`, public, 30 a minute, body
  `errorReportSchema` through `ZodValidationPipe`, gives `201 { errorId }`.
  `CommonModule` provides, exports and registers them, so `app.module.ts` does not change. Web:
  `apps/web/src/lib/error-report.ts` with `reportError(error: unknown): void`, which sends
  `location.pathname` only, never the query string.

### Done-when details

1. Organisation-scoped data (ORGS).
   - Sign-up calls `OrganisationsService.createForAccount` after it creates the account, so a new
     account is the admin of its own new organisation. `SessionGuard` calls `membershipFor` and
     sets the whole principal; an account with no membership gets `401 UNAUTHENTICATED`.
     `/auth/me`, sign-up and sign-in return `role`.
   - Every projects query uses `organisationId: account.organisationId` in place of `accountId`.
     The migration `20261025000000_organisations` creates the enum and the two tables, adds
     `Project.organisationId` as `NOT NULL` with its foreign key and index, and drops
     `Project.accountId` with its index and foreign key. A new app's tables are empty when it
     runs, so the `NOT NULL` column needs no default. `auth.prisma` drops the `ProjectOwner`
     relation and adds the `Membership` back-relation.
   - `GET /api/v1/members` (any member) lists the organisation's members, oldest first. Its
     export is item 4's.
   - No query reads a table of another module: `@app/auth` reaches memberships only through
     `OrganisationsService`, and the member list keeps its own copy of the email. The starter has
     no email change; a story that adds one updates `Membership.email` through the service.
   - API cases in `apps/api/test/organisations.e2e-spec.ts`: `organisation isolation: another
     organisation gets 404 and the project stays unchanged` (the case that `api.e2e-spec.ts` calls
     `account isolation` today, moved and renamed, with a list check added: the other
     organisation's list and export are empty), and `a new account is the only admin of its own
     organisation` (`/auth/me` has `role: 'admin'`; the member list has one row).
   - Test (new repo):
     `tests/test_defaults_organisations.py::test_1_one_organisations_records_never_reach_another`
     requires those two API cases from the live run. `API_SECURITY_TESTS` in
     `tests/test_starter_tree.py` drops `account isolation`, because this test now owns the rule.
     An existing repo gets no starter file (item 6).
2. Invites and roles (INVITES for the API, MEMBERS and JOIN for the screens).
   - Members can read the member list and can create, change and delete projects. Only invites
     and role changes are admin actions.
   - An invite to an email that already has an account is refused, because each account has
     exactly one membership. Inviting the same email again replaces its token and expiry. An
     admin cannot change their own role, so an organisation always keeps an admin.
   - `AuthService.acceptInvite` checks `openInvite(token)` and that the invite's email is the
     typed email, creates the account with the code that sign-up uses, then `joinFromInvite`
     claims the invite (delete where id and not expired, count 1, as the reset token does) and
     creates the `member` membership. The account and the membership are two calls, not one
     transaction: a failure between them leaves an account that gets `401` until support removes
     it. A ponytail comment names this.
   - API cases in `apps/api/test/invites.e2e-spec.ts` (INVITES), each reading the invite token
     from `logEvents('api')`: `an admin invites a person by email who joins the organisation`
     (the new member's project list shows the admin's project); `a member cannot invite people or
     change roles` (both `403 ADMIN_ONLY`); `an admin changes another member's role but not their
     own`; `an admin cannot change the role of another organisation's account` (the admin of a
     second sign-up sends the first admin's account id and gets `404 MEMBER_NOT_FOUND`, and the
     first admin's role is still `admin`); `an invite link works once and only for its email`;
     `production refuses an invite without a mail provider` (on `productionApiBaseUrl`,
     `422 MAIL_NOT_CONFIGURED` with its message).
   - Playwright flow in `apps/web/e2e/members.spec.ts` (MEMBERS): `only an admin sees the invite
     and role controls`. The second person joins through the API (`page.request`: the invite, then
     `POST /api/v1/auth/accept-invite` with the logged token), so this part needs no join page.
     The member sees the list with no Invite person button and no role menu; the admin makes the
     member an admin; after a reload the member sees both; axe finds no serious problem on the
     Members screen. MEMBERS also adds to the existing flow `switching accounts does not show the
     previous account projects` in `starter-shell.spec.ts`: before the switch the first account
     opens Members; after the second account signs in in the same tab, the Members screen shows
     only the second account's email.
   - Playwright flow in `apps/web/e2e/join.spec.ts` (JOIN): `an admin invites a person who joins
     and sees the same projects` (the admin invites from the Members screen; a second browser
     context opens the logged invite link, joins on the Join your team page, and sees the admin's
     project).
   - Test (new repo): `tests/test_defaults_organisations.py::test_2_admins_invite_by_email_and_members_cannot_change_roles_or_invite`
     requires the INVITES API cases; MEMBERS and JOIN each add their flow name to the same test.
     An existing repo gets no starter file (item 6).
3. Shared formats and the lint rule (FORMATS).
   - `eslint.config.mjs` gets `no-restricted-syntax` as an error for `apps/*/src/**/*.{ts,tsx}`
     and `libs/*/src/**/*.ts`, with `libs/shared/src/format.ts` left out, and these selectors,
     each with the pinned message: `NewExpression[callee.object.name='Intl']`,
     `CallExpression[callee.object.name='Intl']`,
     `CallExpression[callee.property.name=/^toLocale(Date|Time)?String$/]` and
     `CallExpression[callee.property.name='toFixed']` (hand-written money such as
     `(cents / 100).toFixed(2)`). The starter has no `toFixed` today. It is an ESLint core
     rule, so no new dependency. Test files under `apps/api/test` and `apps/web/e2e` are outside
     those globs.
   - The projects page uses `formatDate` from `@app/shared` and loses its local `formatDate`.
     Its `by you` lines go: with organisations they would be wrong for a project another member
     made, and showing the maker's email would need a new lookup that no item asks for.
   - Unit test `apps/web/src/lib/format.test.ts` (in `test:hooks`) with fixed instants:
     `formatDateTime('2026-10-24T20:30:00.000Z', 'Asia/Kolkata')` is `2026-10-25 02:00`; the same
     instant in `America/New_York` is `2026-10-24 16:30`; `formatMoney(123456)` is
     `USD 1,234.56`; `formatMoney(-5)` is `USD -0.05`; `formatMoney(1.5)` throws.
   - Playwright flow in `apps/web/e2e/formats.spec.ts`: `dates show in the person's time zone and
     the constitution's format`: `test.use({ timezoneId: 'Pacific/Kiritimati' })`, sign up, route
     `GET **/api/v1/projects?*` to one project with `createdAtUtc` `2026-10-24T20:30:00.000Z`; the
     Created cell shows `2026-10-25`.
   - Test (new repo): `tests/test_defaults_formats.py::test_3_dates_times_and_money_come_from_the_shared_helpers`.
     Always: `eslint.config.mjs` has the message, and no `.ts` or `.tsx` file under
     `apps/*/src` or `libs/*/src` outside `format.ts` has `Intl.`, `toLocale` or `.toFixed(`.
     Live: requires the flow; with `lint_starter` from `tests/test_modular_starter.py` (imported,
     so it installs its own copy once for this module), the case `a web file formats a date by
     hand` (adds `apps/web/src/features/hand-format.ts` with `new
     Intl.DateTimeFormat('en').format(new Date())`), the case `an API module formats money by
     hand` (adds `libs/projects/src/hand-format.ts` with `(1234).toLocaleString()`) and the case
     `a web file formats cents by hand` (adds `apps/web/src/features/hand-money.ts` with
     `(1234 / 100).toFixed(2)`) each make `corepack pnpm run lint` exit non-zero with the message;
     the added file goes after each case.
4. CSV exports, change history and soft delete (FORMATS, ORGS, HISTORY, SOFTDELETE).
   - CSV (FORMATS): `sendCsv` is the one place that writes CSV. The projects export holds every
     project of the caller's organisation that is not deleted, newest first; it does not follow
     the screen's sort or page. API case in `apps/api/test/exports.e2e-spec.ts`: `projects export
     as CSV` (a project named `Plan, "draft"` comes back as `"Plan, ""draft"""`; a deleted project
     is missing; another sign-up's export has only the header). Playwright flow in
     `formats.spec.ts`: `Export CSV downloads the projects list` (`page.waitForEvent('download')`;
     the file starts with the header row and has the project). ORGS adds `members export as CSV`
     and HISTORY adds `change history exports as CSV` to `exports.e2e-spec.ts` and to
     `CSV_API_CASES`. A ponytail comment in `sendCsv` names its ceiling: it builds the whole file in
     memory, fine for the constitution's size of app; stream it when a table passes about 50,000
     rows.
   - Test (new repo): `tests/test_defaults_formats.py::test_4_each_table_exports_csv_from_one_shared_code_path`.
     Always: `text/csv` appears only in `libs/core/src/common/csv.ts`, and every
     `*-page.tsx` that renders a `<Table` has an `/export` link. Live: requires `CSV_API_CASES` and
     the download flow.
   - Change history (HISTORY): `OrganisationsService` records `member.invited` after it saves an
     invite and `member.role_changed` after it changes a role, through `HistoryService.record`.
     The change and its record are two calls; a ponytail comment names this. The Change history
     screen is for admins only: the sidebar and Ctrl+K item show only for an admin, and a member
     who opens `/history` sees `Only an admin can see the change history.` (the API answers 403).
   - HISTORY's migration `20261025000200_history` holds the `ChangeRecord` table. API case in
     `apps/api/test/history.e2e-spec.ts`: `an invite and a role change write change history`
     (newest first, with the admin's email and both summaries; a member gets 403). Playwright flow
     in `apps/web/e2e/history.spec.ts`: `an admin sees who changed what and exports it`.
   - Test (new repo): `tests/test_defaults_history.py::test_4_admin_actions_write_change_history`
     requires the API case and the flow.
   - Soft delete (SOFTDELETE): the migration `20261025000300_soft_delete_only` holds the function
     and the trigger. It touches only `"Project"`, which the first migration makes, so it does not
     depend on the other parts' migrations; on a fresh database Prisma applies all of them in name
     order. Prisma does not track triggers, so `migrate dev` reports no drift. API case in
     `apps/api/test/soft-delete.e2e-spec.ts`: `the database refuses a hard delete of a project`
     (`psql` with `DELETE FROM "Project" WHERE id = ...` exits non-zero with `are soft deleted`,
     and the project still reads 200).
   - Test (new repo): `tests/test_defaults_soft_delete.py::test_4_the_database_refuses_to_remove_a_record_completely`
     requires that case.
5. One error report per crash (ERRORS).
   - `AllExceptionsFilter` calls `ErrorReporter.report` for a status of 500 or more, in place of
     its `API request failed` line, with its own `errorId`, the exception's class name, the
     method, the path and the status; no message and no stack. A 4xx keeps its debug line. So one
     API crash writes one report.
   - `RouteErrorPage` calls `reportError(useRouteError())` in an effect keyed on the error. The
     built app runs without Strict Mode's second effect run, so one crash sends one report. A
     failed report request is ignored.
   - API case in `apps/api/test/error-reports.e2e-spec.ts`: `an API crash writes one error report`:
     `psql` adds `CHECK (email <> '<a fresh crash email>') NOT VALID` to `"Account"`; a sign-up
     with that email gets 500 with an `errorId`; `logEvents('api')` has exactly one `Error report`
     line with that `errorId` and `source: 'api'`, and the line contains neither the email nor
     `violates check constraint` (no exception text reaches the log); the
     constraint is dropped in a `finally`. The crash comes from the database, so the app needs no
     test-only route.
   - Playwright flow in `apps/web/e2e/error-reports.spec.ts`: `a UI crash writes one error report`:
     sign up, route the projects list to `items: null` as the React defaults flow does, open
     `/projects`; the error page shows; exactly one `POST /api/v1/error-reports` is sent; its
     `errorId` is on exactly one `Error report` line with `source: 'web'` and `path: '/projects'`.
   - Test (new repo): `tests/test_defaults_errors.py::test_5_a_ui_crash_and_an_api_crash_each_write_one_error_report`
     requires the case and the flow; without the live run it skips with the reason.
6. The constitution, the rules text and existing apps (GUIDE; every part keeps the starter's
   tests passing).
   - `skill.md`, `## App constitution`: after the sentence that starts "In an app whose tests run
     Nx's module-boundary lint", add `In an app that has libs/organisations, also copy the
     built-in lines into ## Fixed rules, and ask nothing about the defaults they answer.` The
     outline's `## Fixed rules` keeps its four lines (so `tests/test_notes_first_discovery.py`
     still passes) and adds:

     ```
     - Built in: each account belongs to one organisation, as an admin or a member, and every query is scoped to that organisation.
     - Built in: admins invite people by email; members cannot invite people or change roles.
     - Built in: dates and times are stored in UTC and shown in the person's time zone, and money is stored in cents; the helpers in @app/shared format them.
     - Built in: each table has a CSV export, admin actions write change history, and records are soft deleted.
     - Built in: each UI or API crash writes one error report to the logs.
     ```
   - `fde.md` (`.codex/skills/forge/fde.md` is the source; `.claude/skills/forge/fde.md` is its
     copy), `## Constitution defaults`: mark only what this story builds. Three answers that it
     builds whole end with ` Built in when the app has libs/organisations.`: "Can people see each
     other's information", "Who can add people" and "What happens if someone deletes something".
     Two answers that it builds in part get one sentence that names only that part: "Which
     languages and currencies" ends with ` The date, time, number and money formats are built in
     when the app has libs/organisations.`, and "Do you need reports" ends with ` The CSV export is
     built in when the app has libs/organisations.` The message catalogue, the summary dashboard,
     backups and error tracking are not built, so "Who fixes problems" and every other answer stay
     as they are.
   - `brief.md`, after the module-boundary paragraph: `In an app that has libs/organisations,
     scope every query to the caller's organisation (organisationId on the principal), guard admin
     actions with @AdminOnly() and record them with HistoryService.record, format dates, times,
     numbers and money only with the helpers in @app/shared, export a table only with sendCsv from
     @app/core, and let crashes reach the one error report. An app without libs/organisations
     keeps the code it has.`
   - Convention pages: `security.md` (scope each query to `organisationId`; `@AdminOnly()` for an
     admin action); `database.md` (dates stored in UTC; the `soft_delete_only()` trigger for each
     table with `deletedAtUtc`; change history through `HistoryService`); `frontend.md` (dates,
     times and money only through the helpers, in the person's time zone; the Export CSV link; the
     route error page reports the crash); `backend.md` (the organisations and history modules in
     the layout and the tags line; `sendCsv`; the filter writes one error report); `api.md` (the
     `GET /<list>/export` route); `stack.md` (the two libs in the layout, and the line `An app set
     up before this release keeps its own organisation, date, export, history and error code.`
     next to the other keep lines). `src/forge/standards.md` names the two new modules. The
     starter's `README.md` "How it works" names organisations, roles, invites, the helpers, the
     exports, the change history, the soft delete rule and the error report.
   - Test: `tests/test_built_in_defaults_guide.py::test_6_the_constitution_lists_the_built_in_defaults_and_existing_apps_keep_their_code`,
     with `adoption` in ("new init", "previous release upgrade and sync"), set up as `test_4` of
     `tests/test_app_constitution.py`. For `.claude` and `.codex`: `SKILL.md` has the sentence and
     the five outline lines, and `fde.md` has the whole-answer suffix on exactly three lines, the
     two part sentences, and an unchanged "Who fixes problems" line. `forge work` gives a
     brief (`install_claude`, `calls(log)[-1]["brief"]`) with the brief paragraph, and its
     conventions folder has the new sentences and the keep line. Adopted case only: before the
     upgrade the fixture commits `apps/web/src/features/home.tsx` with `toLocaleString()` and an
     `eslint.config.mjs` of its own; after upgrade and sync both are byte for byte the same and no
     `libs/organisations` exists. `tests/test_starter_app.py::test_3` (adopted case) already shows
     that upgrade and sync write no starter file.

### New and existing repos

- **New repos** (`forge init --starter`): the starter has the organisations and history modules,
  the invite and role screens, the format helpers and their lint rule, the CSV exports, the soft
  delete rule and the error report. The constitution guide, the defaults, the brief paragraph,
  the convention pages and the README arrive with setup. Plain `forge init` gets the text and no
  starter.
- **Existing repos** (on upgrade to this release, after `forge sync`): no app file, schema,
  migration or lint config changes. The guide, the defaults, the brief paragraph and the
  convention pages arrive with sync; they name `libs/organisations` as the condition, so they ask
  nothing of an app without it, and its constitution records what the app already uses. Tested on
  the adopted earlier-release fixture moved to this release (item 6).

## Tasks

<!-- One row per task. Covers: the Done-when numbers it delivers, at most three. Scope: the paths
it may change. Tests: the tests it adds or changes. After: the tasks it waits for. When two tasks
share a function, field, file format or command, the first task pins it: it commits the shared
names and stubs plus one test that crosses both sides, and the tasks that use it list it under
After. Split tasks so each owns its files; shared lines (command table, guide list, registry) go
to one task or a small last wiring task; After only when a task needs another task's code. The
Developer column is optional: the lead fills or changes a GitHub username here, below For the
builders, without another approval. Leave it blank for an unassigned part. Forge next uses
the caller's GitHub login; another developer may start it with a warning. Existing tables
without Developer still work. The moving-parts line stays last: "none", or each new dependency, service, datastore,
queue, background job or abstraction layer, with the Done-when item that needs it. -->

All paths under `starter/` mean `src/forge/templates/starter/`.

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| FORMATS | Shared formats and CSV export | The date, time, number and money helpers, the lint rule, the projects page on the helpers, `sendCsv`, the projects export and its button, the shared error report schema, the shared test helpers, and the cached live run. | 3, 4 | `starter/libs/shared/src/format.ts` (new), `starter/libs/shared/src/index.ts`, `starter/libs/core/src/common/csv.ts` (new), `starter/libs/core/src/index.ts`, `starter/libs/projects/src/projects.controller.ts`, `starter/libs/projects/src/projects.service.ts`, `starter/apps/web/src/features/projects/pages/projects-page.tsx`, `starter/apps/web/src/lib/format.test.ts` (new), `starter/eslint.config.mjs`, `starter/apps/api/test/helpers.ts` (new), `starter/apps/api/test/api.e2e-spec.ts` (helper imports only), `starter/apps/api/test/exports.e2e-spec.ts` (new), `starter/apps/web/e2e/helpers.ts` (new), `starter/apps/web/e2e/starter-shell.spec.ts` (helper imports only), `starter/apps/web/e2e/formats.spec.ts` (new), `tests/test_starter_tree.py` (`live_run` only), `.github/workflows/starter-smoke.yml` | `tests/test_defaults_formats.py` (`test_3`, `test_4`, new); the format unit test; the API case and the two flows of items 3 and 4 | FORGE-REACTDEFAULTS-1/STARTER, FORGE-ZOD-1/STARTER | yes | |
| ERRORS | One error report for crashes | `ErrorReporter`, the report endpoint, the filter's one report per API crash, and the route error page's one report per UI crash. | 5 | `starter/libs/core/src/common/error-report.ts` (new), `starter/libs/core/package.json`, `starter/libs/core/tsconfig.json`, `starter/libs/core/src/common/common.module.ts`, `starter/libs/core/src/common/all-exceptions.filter.ts`, `starter/apps/web/src/lib/error-report.ts` (new), `starter/apps/web/src/components/route-error-page.tsx`, `starter/apps/api/test/error-reports.e2e-spec.ts` (new), `starter/apps/web/e2e/error-reports.spec.ts` (new) | `tests/test_defaults_errors.py` (`test_5`, new); the API case and the flow of item 5 | FORMATS | no | |
| ORGS | Organisations and scoped data | The organisations module, an organisation and admin role at sign-up, the principal with its organisation and role, projects scoped to the organisation, the member list and its export. | 1, 4 | `starter/libs/organisations/**` (new), `starter/apps/api/prisma/schema/organisations.prisma` (new), `starter/apps/api/prisma/schema/auth.prisma`, `starter/apps/api/prisma/schema/projects.prisma`, `starter/apps/api/prisma/migrations/20261025000000_organisations/` (new), `starter/libs/core/src/common/account-principal.ts` and `current-account.decorator.ts` (moved from `libs/auth/src`), `starter/libs/core/src/common/authenticated-request.ts`, `starter/libs/core/src/index.ts`, `starter/libs/auth/**`, `starter/libs/projects/**`, `starter/libs/shared/src/index.ts`, `starter/apps/api/src/app.module.ts`, `starter/apps/api/package.json`, `starter/apps/api/tsconfig.json`, `starter/pnpm-lock.yaml`, `starter/scripts/test-build.mjs`, `starter/apps/api/test/api.e2e-spec.ts` (isolation case out), `starter/apps/api/test/organisations.e2e-spec.ts` (new), `starter/apps/api/test/exports.e2e-spec.ts` (members case), `tests/test_starter_tree.py` (libs list, schema set, `API_SECURITY_TESTS`), `tests/test_defaults_formats.py` (`CSV_API_CASES` only) | `tests/test_defaults_organisations.py` (`test_1`, new); `tests/test_starter_tree.py` (`test_1`); the API cases of item 1 and the members export case | FORMATS | no | |
| INVITES | Invites and roles in the API | The admin guard, invites by email through the mail provider moved into core, joining from an invite, role changes, and refusals for members. | 2 | `starter/libs/organisations/**`, `starter/apps/api/prisma/schema/organisations.prisma`, `starter/apps/api/prisma/migrations/20261025000100_invites/` (new), `starter/libs/core/src/common/admin-only.decorator.ts` (new), `starter/libs/core/src/mail/**` (new, moved from `libs/auth/src/mail.provider.ts`), `starter/libs/core/src/index.ts`, `starter/libs/auth/**`, `starter/libs/shared/src/index.ts`, `starter/apps/api/src/app.module.ts`, `starter/apps/api/test/invites.e2e-spec.ts` (new) | `tests/test_defaults_organisations.py` (`test_2`, new); the API cases of item 2 | ORGS | no | |
| MEMBERS | Members screen and invite dialog | The Members screen with the role menu and Export CSV, the invite dialog, the sidebar and Ctrl+K items, and a full query cache clear on each account change, as `SCREENS.md` shows them. | 2 | `starter/apps/web/src/features/members/**` (new), `starter/apps/web/src/features/auth/hooks/auth-hooks.ts`, `starter/apps/web/src/app.tsx`, `starter/apps/web/src/components/app-shell.tsx`, `starter/apps/web/e2e/members.spec.ts` (new), `starter/apps/web/e2e/starter-shell.spec.ts` (the account-switch flow only), `tests/test_defaults_organisations.py` (`test_2` flow name only) | the flow `only an admin sees the invite and role controls`, required by `test_2`; the Members check in `switching accounts does not show the previous account projects` | INVITES | yes | |
| JOIN | Join from an invite link | The Join your team page for an invite link, its accept-invite hook and its public route. | 2 | `starter/apps/web/src/features/auth/pages/accept-invite-page.tsx` (new), `starter/apps/web/src/features/auth/hooks/auth-hooks.ts`, `starter/apps/web/src/app.tsx`, `starter/apps/web/e2e/join.spec.ts` (new), `tests/test_defaults_organisations.py` (`test_2` flow name only) | the flow `an admin invites a person who joins and sees the same projects`, required by `test_2` | MEMBERS | yes | |
| HISTORY | Change history | The history module, records for invites and role changes, and the admin-only Change history screen and its export. | 4 | `starter/libs/history/**` (new), `starter/apps/api/prisma/schema/history.prisma` (new), `starter/apps/api/prisma/migrations/20261025000200_history/` (new), `starter/libs/organisations/**`, `starter/libs/shared/src/index.ts`, `starter/apps/api/package.json`, `starter/apps/api/tsconfig.json`, `starter/pnpm-lock.yaml`, `starter/scripts/test-build.mjs`, `starter/apps/web/src/features/history/**` (new), `starter/apps/web/src/app.tsx`, `starter/apps/web/src/components/app-shell.tsx`, `starter/apps/api/test/history.e2e-spec.ts` (new), `starter/apps/api/test/exports.e2e-spec.ts` (history case), `starter/apps/web/e2e/history.spec.ts` (new), `tests/test_starter_tree.py` (libs list, schema set), `tests/test_defaults_formats.py` (`CSV_API_CASES` only) | `tests/test_defaults_history.py` (`test_4`, new); `tests/test_starter_tree.py` (`test_1`); the change history API case and flow of item 4 | JOIN | yes | |
| SOFTDELETE | The database refuses a hard delete | The `soft_delete_only()` function and its trigger on projects, in one migration, with the API case that proves it. | 4 | `starter/apps/api/prisma/migrations/20261025000300_soft_delete_only/` (new), `starter/apps/api/test/soft-delete.e2e-spec.ts` (new) | `tests/test_defaults_soft_delete.py` (`test_4`, new); the API case `the database refuses a hard delete of a project` | FORMATS | no | |
| GUIDE | Constitution, conventions and brief | The built-in lines in the constitution guide and the defaults, the worker brief paragraph, the convention pages, the standards page and the starter's README, on new and existing repos. | 6 | `src/forge/templates/skill.md`, `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `.codex/skills/forge/fde.md`, `.claude/skills/forge/fde.md`, `src/forge/templates/brief.md`, `src/forge/templates/conventions/security.md`, `database.md`, `frontend.md`, `backend.md`, `api.md`, `stack.md`, `src/forge/standards.md` and its synced copies, `starter/README.md` | `tests/test_built_in_defaults_guide.py` (`test_6`, new) | FORGE-REACTDEFAULTS-1/RULES, FORGE-ZOD-1/STARTER | no | |

New moving parts: `soft_delete_only()`, a Postgres trigger function in the starter's migrations that refuses a hard delete of a soft-deleted table's rows (item 4). No new package: the lint rule is ESLint's core `no-restricted-syntax`, and the helpers use the runtime's `Intl`.

## Notes

- **Order.** FORMATS, then ORGS, INVITES, MEMBERS, JOIN and HISTORY in a line: each one changes
  files that the one before it wrote (the projects service, the organisations service, the auth
  hooks, the routes and the sidebar). ERRORS and SOFTDELETE start after FORMATS and run beside
  that line; they share no file with it or with each other. GUIDE shares no file with any part
  and starts at once, after the two in-flight parts that also change the convention pages and
  the brief. All nine ship in one release.
- **The zod part's name.** The zod story has no task table yet. FORMATS and GUIDE wait for its
  part that changes the starter and the API and backend convention pages; if that part has
  another name than `STARTER`, use its name.
- **Part sizes.** Each part is planned under 400 lines. A moved file counts once, as the move.
- **Design.** MEMBERS, JOIN and HISTORY build the screens in `docs/design/FORGE-DEFAULTS-1/`, with the
  starter's neutral shadcn/ui theme and no new look. FORMATS adds one button to the projects
  list, also in that folder. ERRORS changes no screen.
- **Simplest version, by the owner's rule.** Not in this story: one person in more than one
  organisation; an organisation name or settings screen; email verification; removing a member;
  a list of pending invites (inviting again sends a new link); paging on the change history (the
  screen shows the newest 100, and the export has all); one transaction across two modules (the
  two places are marked with ponytail comments); a guard that keeps change history rows from
  changing; a stored time zone for each person.
- **Changes no flow.** No command, option, `forge.toml` setting or stored state changes. The
  worker side is the brief paragraph and the convention pages; the coordinator side is the
  constitution guide in `skill.md`.
- No client repo is named anywhere in this story's code, tests, texts or commits.
