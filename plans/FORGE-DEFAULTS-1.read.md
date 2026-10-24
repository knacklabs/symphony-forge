---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-24T11:12:39.823186+00:00
seconds: 67.107
read_hash: 054b1cd3567268bc4514dd46ef80972f1b8b765d
round: 3
passed: yes
doc_seen: 054b1cd3567268bc4514dd46ef80972f1b8b765d
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e5ff54afa3d48fb8d092530f893b02d88e6166bc
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a16d41-5bff-7d81-9ea3-e49b001fac54
session:
loop_choice:
loop_reason:
---
# Cold read notes

Written by `forge read`. Under every blocking finding, write one disposition line, amend the
doc, then run `forge read <doc>` again until a round has no blocking notes. Notes marked
`Advisory:` are recorded without requiring a disposition or another round:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

A finding inside What counts is cut or deferred. Keep one only when it falls outside that boundary
or is factually wrong or not worth the change, and give as the reason the Leave out line, the
missing Raise line, the cited fact that disproves it, why it is not worth the change, or the
human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: Trap: removing the first stack line does not remove multiline error messages.
   Raise: Security. Case: normal use - a database exception contains an email or record value in a multiline message.
   [The plan](/plans/FORGE-DEFAULTS-1.md:200) treats every line after the first as a frame. Message continuation lines therefore reach the logs, contradicting the privacy promise at line 66. [Node’s stack format](https://nodejs.org/api/errors.html#errorstack) includes the error message before the frames; that message need not occupy one line. The current [filter](/src/forge/templates/starter/libs/core/src/common/all-exceptions.filter.ts:30) avoids logging exception text.
   Gain 5, Work 2, Harm 4
   Disposition: cut the stack frames from the error report; it logs only the error class, path, method, status, errorId and correlation id, never exception text, and the API crash case checks the constraint text is absent.

2. Blocking: Unproven: item 1: role changes cannot target another organisation.
   Raise: Test. Case: normal use - an admin submits another organisation’s account ID to the role endpoint.
   [The planned cases](/plans/FORGE-DEFAULTS-1.md:252) exercise member denial, another member’s role and the caller’s own role. They would all pass if `changeRole` updated membership by account ID without checking organisation ID. The isolation case at line 230 checks projects, so it cannot catch this new authorization failure.
   Gain 4, Work 2, Harm 4
   Disposition: cut the gap; changeRole filters on account id and the caller's organisationId, and INVITES adds the case `an admin cannot change the role of another organisation's account` (404, role unchanged).

3. Blocking: Unproven: item 1: switching accounts isolates the new Members and Change history caches.
   Raise: Test. Case: normal use - someone signs out after viewing Members or Change history, then signs into another organisation in the same tab.
   [Session changes currently clear only project queries](/src/forge/templates/starter/apps/web/src/features/auth/hooks/auth-hooks.ts:7). The plan pins neither account-scoped keys nor clearing for the new lists. Its [new browser flows](/plans/FORGE-DEFAULTS-1.md:258) use separate contexts or reloads; they would pass while cached emails and history appeared briefly after an account switch.
   Gain 4, Work 2, Harm 4
   Disposition: cut the gap; the auth hooks call queryClient.clear() on sign-in, sign-up, sign-out and accept-invite, and MEMBERS adds a same-tab Members check to the existing account-switch flow.

4. Blocking: Plan gap: ERRORS cannot add its required shared request schema within Scope.
   Raise: Plan gap. Case: normal use - ERRORS implements the new error-report endpoint against the prerequisite zod rules.
   [ERRORS owns no shared-library path](/plans/FORGE-DEFAULTS-1.md:426), and no earlier task pins an error-report schema. The prerequisite’s implemented `task/FORGE-ZOD-1-RULES:src/forge/templates/conventions/api.md:55` requires each request schema in `@app/shared`, used for validation and documentation. An inline schema in core violates that rule; adding the shared schema requires an unowned change.
   Gain 4, Work 1, Harm 2
   Disposition: cut the gap; FORMATS pins `errorReportSchema` in libs/shared/src/index.ts, and ERRORS validates the endpoint with it.

5. Blocking: Unproven: item 3: ordinary handwritten money formatting passes the pinned lint rule.
   Raise: Not done. Case: normal use - a web component displays money with `(cents / 100).toFixed(2)`.
   [The selectors](/plans/FORGE-DEFAULTS-1.md:268) reject `Intl` and `toLocale…` calls only. This money formatter matches none of them, and the static check and both negative cases at line 286 also miss it. The tests can therefore pass while the promised enforcement of shared money formatting is broken.
   Gain 3, Work 2, Harm 3
   Disposition: cut the gap; the lint rule also bans `.toFixed(` outside the shared helper, the static check covers it, and a third negative case adds `(1234 / 100).toFixed(2)`.

6. Advisory: The production invite refusal loses its promised explanation.
   Raise: Functional. Case: normal use - an admin invites someone before a production mail provider is configured.
   [The contract](/plans/FORGE-DEFAULTS-1.md:177) promises `503 MAIL_NOT_CONFIGURED` with “Email is not set up for this app yet.” The existing [exception filter](/src/forge/templates/starter/libs/core/src/common/all-exceptions.filter.ts:26) replaces every 5xx message with “Something went wrong. Try again.” INVITES cannot change that filter, and ERRORS specifies only a logging change.
   Gain 3, Work 2, Harm 2
   Disposition: cut the 503; the refusal is `422 MAIL_NOT_CONFIGURED`, whose message the filter already keeps, and the production case checks the message.

7. Advisory: GUIDE labels unimplemented parts of the defaults as built in.
   Raise: Not done. Case: normal use - the coordinator uses the revised defaults when creating a constitution.
   [GUIDE appends the suffix to entire unchanged answers](/plans/FORGE-DEFAULTS-1.md:361). Those answers include a message catalogue, a summary dashboard and daily managed backups in [fde.md](/.codex/skills/forge/fde.md:157). No task delivers them. The resulting guide claims more is built in than the starter provides.
   Gain 3, Work 1, Harm 2
   Disposition: cut the whole-answer marks on partly built defaults; three fully built answers get the suffix, two get a sentence that names only the built part, and the rest stay unchanged.

8. Advisory: Split: MEMBERS → member management and invitation acceptance; HISTORY → change history and soft-delete enforcement.
   Raise: Plan gap. Case: normal use - builders implement the complete task scopes and their required tests.
   [The task rows](/plans/FORGE-DEFAULTS-1.md:429) suggest more than about 400 changed lines each. MEMBERS owns a list, role controls, a dialog, a joining page, hooks, navigation and two browser flows. HISTORY owns a complete library, schema and migration, organisation integration, a screen, exports, wiring and API/browser tests. For comparison, the existing [form dialog](/src/forge/templates/starter/apps/web/src/features/projects/pages/project-form-dialog.tsx:1) alone is 128 lines. The blanket size claim at line 445 does not account for these scopes.
   Gain 3, Work 3, Harm 4 (floor: migration)

   Disposition: cut the two large parts; MEMBERS splits into MEMBERS and JOIN, and HISTORY into HISTORY and SOFTDELETE, with After chain FORMATS, ORGS, INVITES, MEMBERS, JOIN, HISTORY and SOFTDELETE after FORMATS.

## Round 2

9. Advisory: Plan gap: the shared error schema introduces dependency wiring that no task owns.
   Raise: Plan gap. Case: normal use - ERRORS imports `errorReportSchema` into the controller in core.
   [The schema ownership fix](/plans/FORGE-DEFAULTS-1.md:120) introduces core’s first `@app/shared` import. Core currently has neither a workspace dependency in [package.json](/src/forge/templates/starter/libs/core/package.json:12) nor a project reference in [tsconfig.json](/src/forge/templates/starter/libs/core/tsconfig.json:18). Neither file appears in any task’s Scope. The schema now has an owner, but consuming it requires unowned configuration changes before the starter can build.
   Gain 4, Work 2, Harm 2
   Disposition: keep - The owner chose to fix the last note in the builders section and accept the plan without a third read

## Round 3

No findings.
