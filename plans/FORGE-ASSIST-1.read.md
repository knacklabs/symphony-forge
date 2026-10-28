---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-28T14:47:51.513542+00:00
seconds: 244.736
read_hash: dedbbafcc65289cd705d454e47d2e9587038c50b
round: 2
passed: no
doc_seen: dedbbafcc65289cd705d454e47d2e9587038c50b
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: c8b9fe5c19ad9ec1d8cf7b7e2c9514f9221c33e4
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a182e5-1300-7962-994a-2b3033a5d7ad
session:
loop_choice: more
loop_reason: The owner chose one more round to fix the part order
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

1. Blocking: Request sampling creates chat copies outside the promised retention boundary.
   Raise: Security. [The plan:107](/plans/FORGE-ASSIST-1.md:107) logs the exact model request for one turn in ten. That includes conversation text and tool results. Line 120 instead promises that only chats and checkpoints hold text, and clean-up deletes neither these logs nor their copies.
   Case: normal use - a sampled conversation remains in logs after its chat expires.
   Gain 5, Work 2, Harm 4
   Disposition: cut - the one-turn-in-ten request log is removed (it would keep chat text outside the 30 days); the builder reads the request once and the prompt-size case covers growth.

2. Blocking: A prompt refusal does not prevent secrets from being stored.
   Raise: Security. [The plan:121](/plans/FORGE-ASSIST-1.md:121) handles submitted passwords and card numbers only through the prompt. The agent receives the message with a checkpointer attached; [LangGraph checkpoints include the input before model execution](https://docs.langchain.com/oss/python/langgraph/checkpointers). A refusal therefore leaves the secret in checkpoint history. The named test checks no storage outcome.
   Case: normal use - someone pastes a password while asking for help signing in.
   Adds work: redact submitted secrets before checkpointing; F 2 x H 3 = 6; 2 x C = 4.
   Gain 5, Work 3, Harm 4
   Disposition: cut - code now checks the text for a labelled password or a card number (Luhn) before the agent runs, so nothing is checkpointed; a case proves no model call and no checkpoint row; the limit for a bare password is stated.

3. Blocking: Unproven: items 3 and 4: ownership checks on message and confirm requests.
   Raise: Test. [The privacy cases:145](/plans/FORGE-ASSIST-1.md:145) exercise listing and reading another person's chat. They do not exercise either POST endpoint. An implementation that protects GET but resumes another person's pending action through POST would pass every listed ownership case. Both POST routes need the ownership refusal covered before any graph execution.
   Case: normal use - a signed-in person submits another person's chat identifier to the message or confirm endpoint.
   Gain 4, Work 2, Harm 4
   Disposition: cut - the message and confirm endpoints now call `ownChat` first and have cases for another person's chat id (no model call, pending write does not run).

4. Blocking: The TypeScript schema cannot be added within ASSIST's scope.
   Raise: Plan gap. [ASSIST's scope:164](/plans/FORGE-ASSIST-1.md:164) permits only the new assistant schema file and migration. The existing `apps/api/prisma/schema/base.prisma:7` explicitly lists allowed schemas without `assistant`; `auth.prisma:1` owns the Account model that needs the opposite relations for the promised account links. Neither existing file has an owner in this plan.
   Case: normal use - generating the Prisma client for the new tables.
   Gain 4, Work 2, Harm 4
   Disposition: cut - ASSISTDB scope now has `base.prisma`, `auth.prisma` and the model-to-schema test map.

5. Blocking: The shared Assistant web code lacks Python dependency and lockfile work.
   Raise: Functional. [The task scopes:165](/plans/FORGE-ASSIST-1.md:165) omit `starter-python/package.json` and `starter-python/pnpm-lock.yaml`. However, `src/forge/init.py:159` copies shared UI and every web library into Python apps. Their own package manifest lacks Recharts, and their lockfile lacks the new workspace packages and dependency changes. `apps/web/tsconfig.json:26` includes shared UI even with the assistant off.
   Case: normal use - installing and typechecking a newly generated Python app.
   Gain 4, Work 2, Harm 3
   Disposition: cut - WEBBLOCKS scope now has `starter-python/package.json` and `pnpm-lock.yaml`, and its test installs and typechecks a new Python app.

6. Blocking: Not done: assistant attribution never reaches the change-history screen.
   Raise: Not done. [Item 3:29](/plans/FORGE-ASSIST-1.md:29) promises “via the assistant.” The prerequisite deliberately adds storage only and leaves display to the first story setting this value. Current `history.dto.ts:16`, Python `history/schema.py:8`, and `history-page.tsx:49` expose and render no agent attribution. None is scoped here; the listed history test can pass by checking storage alone.
   Case: normal use - an admin reads a change made through the assistant.
   Gain 4, Work 2, Harm 3
   Disposition: cut - the history contracts, DTO, CSV, screen cell, Python schema and CSV, and API types are in scope, with cases for the list, the CSV and the screen cell.

7. Blocking: Scope paths use shorthand that Forge does not expand.
   Raise: Gate. [The task table:164](/plans/FORGE-ASSIST-1.md:164) switches from repository-relative paths to `starter/...` and `starter-python/...`, and attaches annotations such as `(new)` to paths. `src/forge/task.py:74` and `src/forge/review.py:117` split these cells literally; neither expands prefixes nor removes annotations. Required edits will be reported outside scope, and overlap detection will use incorrect paths.
   Case: normal use - starting and reviewing any implementation task.
   Gain 4, Work 1, Harm 2
   Disposition: cut - every Scope cell is a plain repository-relative path or folder with no annotation.

8. Blocking: The report service required by the chart test does not exist in the prerequisite.
   Raise: Plan gap. [The plan:49](/plans/FORGE-ASSIST-1.md:49) expects report services from the agent-ready story, and line 131 requires chart and stats results from one. In that story's current local branch, `plans/FORGE-AGENTREADY-1.md:55` says neither starter has a report; line 177 explicitly cuts an example report. This plan names no report tool, result schema or test fixture that supplies the required result.
   Case: normal use - implementing the report question and its cross-language display mapping.
   Gain 4, Work 2, Harm 3
   Disposition: cut - the dependent claim is cut: the starters have no report, so the chart and tiles are proved with a stand-in report tool, and the owner-facing text now says so.

9. Blocking: API proof and shared test wiring have conflicting owners.
   Raise: Plan gap. [The table and ownership paragraph:164](/plans/FORGE-ASSIST-1.md:164) give ASSIST the API implementation and API test file, but give WEB the text and confirmation proof. WEB cannot fill those API cases within its scope. GUIDE also edits the same new root test file while being declared independent, and no task scopes the required workflow edit. Assign API cases to their API tasks, separate GUIDE's proof file, and give the workflow wiring one owner.
   Case: normal use - closing ASSIST independently and starting GUIDE alongside implementation.
   Gain 4, Work 2, Harm 3
   Disposition: cut - each part owns its test file; API cases sit in the API parts, page cases in the web parts, GUIDE has its own file, and the workflow line is one glob in ASSISTDB.

10. Blocking: Unproven: items 1 and 2: the assembled Assistant page.
    Raise: Test. [The web cases:136](/plans/FORGE-ASSIST-1.md:136) cover individual block rendering and disabled Send. Nothing exercises submitting a question, consuming its stream, displaying the confirm card and submitting its decision. A page with no working submit handler or confirm request passes all listed API and component cases.
    Case: normal use - asking a question and confirming a change through the page.
    Gain 4, Work 2, Harm 3
    Disposition: cut - WEBCHAT has cases for submitting a question, reading the stream, showing the confirm card and sending the decision, plus the limit line.

11. Blocking: Multiple pending writes have no pinned confirmation contract.
    Raise: Plan gap. [The write contract:96](/plans/FORGE-ASSIST-1.md:96) defines individual cards and a generic resume, but does not bind `confirmId` to a particular runtime interrupt when one response proposes multiple writes. [LangGraph requires explicit interrupt-to-response pairing for parallel interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts#handling-multiple-interrupts). Every listed confirmation case can use just one write.
    Case: normal use - “Mark these two projects complete,” followed by confirming one change and cancelling the other.
    Gain 4, Work 2, Harm 3
    Disposition: cut - parallel tool calls are off, so a chat has one open card; `confirmId` is the interrupt's id; a stale id gets 409; a case confirms one change and cancels the next.

12. Blocking: The pinned `assistant.use` permission cannot be registered through the current TypeScript API.
    Raise: Plan gap. [The plan:81](/plans/FORGE-ASSIST-1.md:81) requires that permission for both roles. `libs/core/server/src/common/permissions.ts:7` accepts only view, create, edit, delete and restore; its role map is private. ASSIST cannot register `use` through this interface, and its scope excludes changing the registrar.
    Case: normal use - enabling the module and granting its default permission.
    Gain 3, Work 2, Harm 3
    Disposition: cut - the `assistant.use` permission is removed; every signed-in person can use the module and each tool checks its own permission.

13. Blocking: Split: the backend tasks and WEB exceed the task-size boundary.
    Raise: Plan gap. [ASSIST and ASSISTPY:164](/plans/FORGE-ASSIST-1.md:164) each combine contracts, persistence, checkpoint setup, expiry, five endpoints, model integration, the agent loop, confirmation and tests. Each scope suggests substantially more than 400 changed lines. WEB likewise combines a page, hooks, stream handling, five renderers and a copied chart component. Split each backend into storage/contracts and turn execution; split WEB into block components and the chat flow.
    Case: normal use - building and closing these parts independently.
    Gain 4, Work 2, Harm 3
    Disposition: cut - split into ASSISTDB and ASSIST, ASSISTDBPY and ASSISTPY, WEBBLOCKS and WEBCHAT.

14. Blocking: GUIDE's named test never checks the guidance it delivers.
    Raise: Test. [GUIDE:167](/plans/FORGE-ASSIST-1.md:167) promises coordinator guidance, a worker-brief sentence and upgrade delivery. Its sole test is item 6, whose cases check unchanged app files and disabled starter modules. Those cases pass if GUIDE ships no guidance at all. Neither new-repo nor earlier-adopted proof inspects the delivered guide or worker brief.
    Case: normal use - a coordinator or worker follows the installed guidance after init or upgrade.
    Gain 3, Work 2, Harm 3
    Disposition: cut - GUIDE now has `test_6_the_guides_name_the_optional_assistant` on a new repo and an earlier-adopted repo, checking the guide and brief sentences, which are now written out.

15. Advisory: Retained conversations still need the agents skill's context rules.
    Raise: Plan gap. [The applicability statement:105](/plans/FORGE-ASSIST-1.md:105) excludes context handling because there is no classifier, memory-note store or speech. Those exclusions do not remove conversation history. The prerequisite agents plan, `plans/FORGE-AGENTS-1.md:202–234`, separately requires context-budget handling. This plan keeps active chats indefinitely without a context bound, compaction rule or stated exception.
    Case: normal use - someone reuses a daily work chat until its accumulated messages exceed the selected model's context window.
    Gain 4, Work 4, Harm 3
   Disposition: keep - advisory; a provider refusal for length now shows one plain line asking for a new chat, and the missing context summary is listed for the owner's OK (Planner choice 4).

## Round 2

16. Blocking: The new task order lets WEBBLOCKS ship Python code before its contracts exist.
    Raise: Functional. [WEBBLOCKS:185](/plans/FORGE-ASSIST-1.md:185) waits only for ASSISTDB, but ASSISTDBPY owns the Python `@app/assistant-contracts` package. `src/forge/init.py:159` copies the shared web libraries into Python apps without copying TypeScript contracts. Consequently, WEBBLOCKS's promised Python install/typecheck encounters a missing workspace dependency unless ASSISTDBPY has already merged. This is a new ordering defect introduced by the split; WEBBLOCKS needs that code prerequisite.
    Case: normal use - WEBBLOCKS starts after ASSISTDB while ASSISTDBPY is still building, and generates a Python app containing the assistant blocks.
    Gain 5, Work 1, Harm 3

17. Advisory: The Zod update is separated from the Python version alignment required by existing tests.
    Raise: Plan gap. [ASSISTDB:181](/plans/FORGE-ASSIST-1.md:181) raises TypeScript's Zod version, while only the later WEBBLOCKS task owns Python's package manifest and lockfile. `tests/test_python_starter.py:119–121` requires matching versions for dependencies shared by both starters. ASSISTDB therefore fails that existing check before WEBBLOCKS can start. Unlike the settled missing-web-dependency finding, this concerns the newly split first task's own verification.
    Case: normal use - running the required checks for ASSISTDB before merging it.
    Gain 4, Work 1, Harm 2
