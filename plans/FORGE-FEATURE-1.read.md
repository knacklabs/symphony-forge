---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-25T17:56:47.125968+00:00
seconds: 230.781
read_hash: d5fe6ee7129437511e455c78999115811e14a907
round: 2
passed: no
doc_seen: d5fe6ee7129437511e455c78999115811e14a907
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: ea3e81e46537b788402fd656c350baf4bfc8e641
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a17423-77f1-78b1-932c-6686090cb585
session:
loop_choice: accept
loop_reason: The owner accepted the three advisory notes; they are fixed in the builders section: the design's restore behaviour wins, ACCESS scope adds the shared query schema and the Switch and Alert components, and one rollback test
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

1. Blocking: The starter check rejects a freshly initialized TypeScript starter.
   Raise: Functional.
   Case: normal use - a worker generates its first feature in a new starter app.
   [The checklist](plans/FORGE-FEATURE-1.md:292) requires `HistoryModule` in `apps/api/src/app.module.ts`. [That file](src/forge/templates/starter/apps/api/src/app.module.ts:8) imports organisations instead; history is imported by `OrganisationsModule`. No task’s Scope includes changing the API’s `app.module.ts` to establish the required anchor.
   Gain 5, Work 2, Harm 3
   Disposition: cut the starter check uses the OrganisationsModule lines a new app has

2. Blocking: PAGING and ACCESS need test files outside their Scopes.
   Raise: Gate.
   Case: normal use - either part runs the starter’s complete test command.
   [The task Scopes](plans/FORGE-FEATURE-1.md:499) exclude both starters’ organisation and invite test files. Those files still assert [`pagination.totalItems`](src/forge/templates/starter/apps/api/test/organisations.e2e-spec.ts:26), [numbered-page queries and successful member deletion](src/forge/templates/starter/apps/api/test/invites.e2e-spec.ts:53). The [Python organisation](src/forge/templates/starter-python/apps/api/tests/test_organisations.py:28) and [invite cases](src/forge/templates/starter-python/apps/api/tests/test_invites.py:100) make the same assertions. The planned changes leave these tests red, and their owners cannot repair them within Scope.
   Gain 4, Work 2, Harm 3
   Disposition: cut PAGING and ACCESS Scopes name the organisations, invites, soft delete and join tests

3. Blocking: PAGING removes the working edit and delete path before DETAIL supplies its replacement.
   Raise: Plan gap.
   Case: normal use - PAGING closes before DETAIL starts.
   [PAGING’s requirements](plans/FORGE-FEATURE-1.md:428) remove row actions and change the CRUD flow to use the detail screen. [DETAIL supplies that screen afterward](plans/FORGE-FEATURE-1.md:441). The [current router](src/forge/templates/starter/apps/web/src/app.tsx:72) has no detail route. PAGING therefore cannot deliver its required passing flow without bringing forward work assigned to DETAIL.
   Gain 4, Work 2, Harm 3
   Disposition: cut rows keep Edit and Delete in PAGING; DETAIL moves them

4. Blocking: Trap: the planner’s feature command is not safe to execute as a shell line.
   Raise: Functional.
   Case: normal use - a worker executes the documented nine-field example.
   [The example](plans/FORGE-FEATURE-1.md:348) leaves `?`, parentheses and pipes unquoted. With a harmless shell-function substitute for Forge, zsh stops at `description?:long-text` with `no matches found`; Bash syntax checking rejects `status(planned|active|done)`. The [existing command-test harness](tests/conftest.py:324) passes an argument array, so those tests can pass while the worker’s documented line fails.
   Gain 4, Work 2, Harm 3
   Disposition: cut every --field value is single-quoted and test_1 runs the lines through bash and zsh

5. Blocking: An allowed feature without a text field loses its identifying column and keyboard link.
   Raise: Functional.
   Case: normal use - a contacts feature has `email:email` and `active:yes-no`.
   [The field rules](plans/FORGE-FEATURE-1.md:154) explicitly support features without text fields, but make only the first text field an identifying list column and detail link. This example consequently displays only Updated. [The design](docs/design/FORGE-FEATURE-1/SCREENS.md:42) makes that missing name link the keyboard target, and [its detail heading](docs/design/FORGE-FEATURE-1/SCREENS.md:78) also requires a first text field. No fallback or test covers this supported input.
   Gain 3, Work 2, Harm 3
   Disposition: cut a feature needs one text field, its name; a line without one is refused

6. Blocking: Unproven: item 3 never exercises denied view, create or edit permissions.
   Raise: Test.
   Case: normal use - a plan removes a member’s edit permission.
   [The endpoint test](plans/FORGE-FEATURE-1.md:382) uses the default mapping, where members have every permission except delete. A replace route incorrectly guarded by `.view` therefore passes, including the static “exactly one decorator” check, but permits edits after `.edit` is removed. None of the specified parameters changes the mapping to exercise that denial.
   Gain 3, Work 2, Harm 3
   Disposition: cut a notes feature with member: [] proves denied view, create and edit on every route

7. Advisory: Linked-item display and selection have no rule for targets beyond one page.
   Raise: Plan gap.
   Case: normal use - an organisation has 60 clients and a job references one outside the currently loaded client page.
   [The web contract](plans/FORGE-FEATURE-1.md:371) requires filters, Comboboxes and cells to obtain linked names through the target’s list hook, while [the list contract](plans/FORGE-FEATURE-1.md:137) returns 20 items. The [current hook](src/forge/templates/starter/apps/web/src/features/projects/hooks/projects-hooks.ts:23) returns one page. No lookup or traversal contract covers an already selected target outside that page; the specified live example does not require more than one client.
   Gain 3, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)

8. Advisory: Unproven: the command’s malformed-field refusals have no assigned test.
   Raise: Test.
   Case: normal use - a planner supplies a reserved field name or unsupported field kind.
   [COMMAND promises](plans/FORGE-FEATURE-1.md:219) pre-write refusals for invalid names, reserved names, unknown kinds and missing link targets. [Test 1](plans/FORGE-FEATURE-1.md:345) exercises valid generation and an existing folder; [test 6](plans/FORGE-FEATURE-1.md:455) exercises starter detection. Neither proves the other refusal rules or that they leave the app unchanged.
   Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

## Round 2

9. Advisory: Restore’s screen and API contracts contradict each other.
   Raise: Plan gap.
   Case: normal use - an admin turns on Show deleted.
   [The API contract](plans/FORGE-FEATURE-1.md:185) specifies `deleted=true`, deleted items only, and a permission refusal for members. [The screen contract](docs/design/FORGE-FEATURE-1/SCREENS.md:43) specifies `deleted=yes`, active and deleted items together, and ignoring the parameter for members. The plan makes SCREENS.md authoritative, so builders have incompatible instructions for the same request.
   Gain 4, Work 2, Harm 3
   Disposition: keep - The owner accepted the three advisory notes; they are fixed in the builders section: the design's restore behaviour wins, ACCESS scope adds the shared query schema and the Switch and Alert components, and one rollback test

10. Advisory: ACCESS lacks Scope for the shared query change and restore components.
    Raise: Gate.
    Case: normal use - ACCESS implements the deleted list and deleted detail screen.
    [ACCESS’s Scope](plans/FORGE-FEATURE-1.md:582) permits only `Account` changes in the TypeScript shared index, but `deleted` must enter [the strict projects query schema there](src/forge/templates/starter/libs/shared/src/index.ts:11). The updated design also requires [Switch](docs/design/FORGE-FEATURE-1/SCREENS.md:43) and [Alert](docs/design/FORGE-FEATURE-1/SCREENS.md:128). Neither component exists in the starter, and their files are outside every task’s Scope.
    Gain 4, Work 2, Harm 3
   Disposition: keep - The owner accepted the three advisory notes; they are fixed in the builders section: the design's restore behaviour wins, ACCESS scope adds the shared query schema and the Switch and Alert components, and one rollback test

11. Advisory: Unproven: item 4’s new transaction guarantee has no rollback test.
    Raise: Test.
    Case: rare - the history write fails after the item write.
    [The amended rule](plans/FORGE-FEATURE-1.md:173) promises that this failure rolls back the item change. [The assigned proof](plans/FORGE-FEATURE-1.md:485) checks successful writes and four history summaries only. The current [TypeScript history writer](src/forge/templates/starter/libs/history/src/history.service.ts:9) uses its own Prisma client, and [Python commits internally](src/forge/templates/starter-python/apps/api/app/history/service.py:30). Retaining that behavior while accepting an unused transaction argument would pass the specified proof.
    Gain 3, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)
