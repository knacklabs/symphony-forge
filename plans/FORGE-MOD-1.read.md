---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-03T13:59:02+00:00
read_hash: 3999b71cae564b33d80f675032da88297f68098c
round: 10
passed: no
doc_seen: 3999b71cae564b33d80f675032da88297f68098c
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 60f6a51374f536976d6541e03e2e9a1db113ee41
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc, then run
`forge read <doc>` again for the next round, until a round finds nothing:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Item 4 assumes an approval path that does not exist today.
   In `approval.py`, Claude approvals come only from ExitPlanMode; AskUserQuestion only counts a human touch. APPROVE must pin the new question/answer contract, digest binding and native hook provenance while preserving the existing refusal checks. Calling the recorder with a constructed payload cannot prove human approval.
   Disposition: keep Approve now opens Claude Code's own plan-approval prompt (ExitPlanMode) so the existing hook and its checks record it; APPROVE proves this first (owner chose)

2. Item 4 contradicts the promised Approve-button behavior.
   “What changes for you” says pressing Approve approves the story; builder details say it starts another approval question. State the actual interaction consistently before the human approves this story.
   Disposition: cut wording now matches: the button opens Claude's own plan prompt and you approve there

3. VIEWS must explicitly pin the contracts its consumers share.
   The flag names, JSON fields/types, item and repository identities, run/review/check identities, unavailable-data representation, per-item next steps and approval document location/digest are unspecified. VIEWS must own these contracts and a test crossing producer and consumer; its Covers cell also needs the event data it supplies for item 3.
   Disposition: cut details 1-3 pin flags, fields, identities, unknown values and next.command; VIEWS covers 1-3

4. Items 1 and 3 lack an owner for missing run and question observations.
   Claude workers do not record their pending questions as Codex workers do, and close has no complete run-start/run-end record. Neither `worker.py` nor `close.py` is in Scope. Pin how VIEWS obtains reliable worker elapsed time, Claude questions and every close outcome, and assign any necessary recording changes.
   Disposition: cut VIEWS adds run start/end records in worker.py, close.py and codex.py; questions come from the item state both workers already write

5. Items 2 and 3 do not define which next step becomes the command.
   `nextstep._report` returns multiple steps, including platform alternatives, placeholders, human merge instructions and waits. Pin deterministic selection, per-item association and which states disable the hotkey; otherwise builders must invent what “next command” means.
   Disposition: cut next.command is the first runnable forge command with no placeholder or alternative, else null

6. P1: MOD changes coordinator behavior without its required instruction update.
   MOD introduces event-driven turns but scopes neither `src/forge/templates/skill.md` nor the worker brief. The repository’s Review rules require that update in the same change, including how the coordinator handles events and watches runs when the mod is unavailable.
   Disposition: cut EVENTS owns the guide's events section and the brief's line; each task owns its own guide section

7. Shared Scope entries leave ownership and wiring unspecified.
   APPROVE’s files are already inside MOD’s `src/forge/mod/**`; VIEWS, APPROVE and SHIP all own `templates/skill.md`. MOD must reserve approval files and pin its registration interface. Assign shared guide lines to one owner or a small final wiring task, rather than making unrelated work wait on guide edits.
   Disposition: keep each task adds its own named guide section; mod files are split per task with register.ts owned by PANE

8. Split: MOD → pane/band and event delivery.
   Pane rendering, keyboard controls, refresh/process handling, event comparison, busy-turn batching and packaging suggest more than about 400 changed lines. Keep drawing and next-step controls in one task; give event delivery its own files and tests.
   Disposition: cut split into PANE and EVENTS

9. Unproven: item 1: automatic pane visibility in a narrow terminal.
   Claude Code can leave an automatically opened pane hidden below its width threshold; it does not always place it above the prompt. Pin a supported user-open action or narrow-screen fallback and test that path. [Pane opening rules](https://code.claude.com/docs/en/plugins/mods/interface#when-a-pane-waits-for-a-wider-terminal).
   Disposition: cut /forge opens at any width; unasked open only shows at 144+ columns and the band points to /forge otherwise; tested at 80 columns

10. Unproven: item 1: refresh behavior and incomplete state.
    Fixture row checks do not prove timer refresh, refresh after commands, advancing elapsed time or recovery from a slow/failed/malformed response. Add cases for an empty board, missing state and unavailable checks; `board._prs` currently fetches check details for only the newest 25 pull requests.
   Disposition: cut refresh timer, after-forge-command refresh, single-flight, failure/slow/malformed handling, empty board and 25-PR limit pinned with tests

11. Unproven: item 2: the hotkey’s refusal states.
    The named test proves a successful submission only. It does not prove that typing into a nonempty prompt remains ordinary input, that nothing-ready disables the hotkey, or what happens while busy, after a stale command, or when submission fails. Name these cases in MOD’s Tests cell.
   Disposition: cut hotkey states pinned: empty prompt only, null, stale and busy cases tested

12. Unproven: item 3: event identity, lifecycle and queued delivery.
    Two snapshots do not prove repeated runs ending in the same stage, runs entirely between refreshes, initial load/reload behavior, overlapping refreshes or failed submissions. Pin event identities and consumption rules, reconcile “one turn per change” with busy-turn batching, and test batching, two sessions on one repo and isolation between repos.
   Disposition: cut event identities, seen store, initial load, batching and failed submit pinned with tests

13. Unproven: items 3 and 5: which sessions receive automatic turns.
    Mods also run in `claude -p` and VS Code chat sessions, even where nothing draws. Forge starts headless Claude workers itself, so installing the plugin can make workers receive coordinator events unless eligibility is defined. Pin interactive/coordinator gating and prove fallback behavior. [Where mods run](https://code.claude.com/docs/en/plugins/mods/overview#where-mods-run).
   Disposition: cut only interactive sessions; FORGE_WORKER=1 set for every Forge-started process makes the mod inert; tested

14. Unproven: item 4: approval refuses safely and Request changes delivers its note.
    Display and successful-recording tests do not cover a document changing after display, the wrong worktree, missing/malformed documents, unrelated questions, cancellation, replay or synthetic completion. Add coverage through the new native path, including Request changes delivering the exact note without recording approval.
   Disposition: cut trust checks stay in forge hook approval; tests cover changed doc, CRLF, and Request changes recording nothing

15. Item 5 does not resolve marketplace identity across repository versions.
    Claude Code identifies marketplaces by name and cannot register two with the same name simultaneously. Pin marketplace/plugin names, source paths and version handling for two repos on different Forge tags and for an existing cached install; changing settings alone is insufficient proof. [Marketplace version rules](https://code.claude.com/docs/en/plugins/host-marketplace#run-release-channels).
   Disposition: cut owner chose one mod from the latest release for every repo; the mod runs each repo's pinned Forge and shows a too-old line

16. Unproven: item 5: installation, reload, settings preservation and fallback.
    Settings-output tests and plugin validation do not prove the plugin loads from the shipped source. Define when an existing session activates it, and test repeated sync, existing unrelated entries, malformed settings, unavailable downloads and absent/old/disabled Claude Code. Prove the doctor warning leaves its exit status successful and Codex/no-mod behavior intact.
   Disposition: cut sync output, repeated sync, unrelated entries, malformed settings, reload and doctor exit status pinned with tests

17. Trap: Windows line endings and shells: items 1, 2, 4 and 5.
    No named cases cover CRLF approval text, Unicode/spaced/backslash paths, PowerShell/cmd command quoting or WSL launch behavior. Pin process invocation and working-directory handling, and assign the relevant platform cases to the owning Tests cells.
   Disposition: cut argv without a shell through the repo launcher, repo-root cwd, CRLF normalised; tested

18. Trap: installed-version mismatch and unavailable test tooling: items 1–5.
    Read-only `forge next` and `forge board` bypass the CLI’s pin check, so a pinned plugin can reach an installed Forge lacking its JSON flags. Pin executable/version resolution and test mismatch recovery. CI currently provisions only Python/uv; assign ownership for a pinned Claude test binary and executable plugin test/validation runs without network-dependent test execution. [Mod test runner](https://code.claude.com/docs/en/plugins/mods/test).
   Disposition: cut version check through the launcher with the too-old line; CI installs a pinned Claude Code for plugin tests

## Round 2

19. Item 5’s launcher cannot satisfy the stated shell-free, repo-pinned invocation.
    `.forge/hooks.sh` is a fragment that must be sourced by a shell; it defines a fallback function and prefers installed Forge. Read-only commands bypass pin enforcement. Pin an executable invocation that selects the repo’s version, assign its owner before PANE, and test mismatched installations and Windows paths.
    Disposition: cut the mod runs forge from PATH with argv as the agent does; the machine view's version drives the too-old line; launcher dropped

20. Item 3 still has no defined source for Claude worker questions.
    Finding 4’s disposition says both workers already write them, but `worker.work` returns from the Claude path before the question-recording code. VIEWS must explicitly capture Claude questions and test their appearance in the machine view.
    Disposition: cut RUNS records Claude and Codex worker questions with ids, tested

21. Item 3’s per-repo seen store contradicts delivery to each session.
    `$.store` is shared across sessions: one session consuming an event—or recording everything as seen during startup—can suppress another session’s turn. Namespace consumption by repository and session, and test two sessions sharing the same store. [Store contract](https://code.claude.com/docs/en/plugins/mods/reference#mods-api-methods).
    Disposition: cut seen ids keyed by repo root and session id; two sessions sharing one store tested

22. Unproven: item 3: repeated occurrences can reuse the chosen event identities.
    A worker can ask the same question in another round; checks can fail again on a retry at the same head and suite. Run end times can also collide because `repo.now()` has second precision. Use occurrence identities and test repeated occurrences, plus failed-submit retries, which remain absent from the named cases.
    Disposition: cut Forge writes a fresh id per review result, run end and question; checks use run id and attempt; repeats and failed-submit retry tested

23. Item 5 does not define how sync obtains the latest released mod.
    Registering an unpinned repository and enabling its plugin does not update an existing cached installation; marketplace auto-update is off by default. Pin released-catalog selection, plugin versioning and the update operation, then test an existing older install. [Marketplace updates](https://code.claude.com/docs/en/plugins/host-marketplace#keep-users-up-to-date).
    Disposition: cut sync adds, updates the marketplace and installs or updates the plugin at user scope; the default branch's marketplace lists the latest release; older install tested

24. Item 5’s settings-only delivery does not install the plugin or enable it across every repo.
    Project settings apply to that repository, and an enabled entry can still lack an installed plugin. Define installation and scope consistently with the machine-wide promise; test a fresh installation and a second repo on another Forge version. [Installation scopes](https://code.claude.com/docs/en/plugins/install#choose-an-install-scope).
    Disposition: cut install is user scope through the claude CLI, one per machine; sync writes no repo file for it; fresh machine tested

25. Disputed keep 7: separate guide sections do not remove Forge’s file-level scope conflict or finish plugin wiring.
    `task.start` rejects overlapping file paths, so every task still overlaps on `skill.md`. EVENTS and APPROVE also cannot edit PANE-owned `register.ts`, and no registration seam is pinned. Assign shared guide wiring to one owner and make PANE deliver the registration contract its successors use.
    Disposition: cut VIEWS owns all guide and brief text; PANE creates the events.ts and approval.ts seam that EVENTS and APPROVE fill

26. The shared per-item next-step and approval-file contracts remain unspecified.
    Details define only one global `next.command`, while EVENTS needs a next step for each changed item and APPROVE needs the waiting story’s actual worktree document. VIEWS must pin those fields, including null-command handling, document location and repository/item identities, with a contract test.
    Disposition: cut board --json carries each item's next.command and approval.doc, pinned with a contract test and shared fixture

27. Split: VIEWS → run observations and machine views.
    VIEWS now owns run lifecycle recording, process gating and both JSON views across seven Python modules, suggesting more than about 400 changed lines. Put observations first, then have machine views consume their pinned records.
    Disposition: cut split into RUNS then VIEWS

28. Unproven: item 1: several claimed refresh cases still have no named proof.
    The test list omits refresh after a Forge tool call, the 20-second timeout, skipping overlapping refreshes, missing state and unavailable GitHub data. Add these cases to PANE’s tests and the relevant machine-view tests; the disposition currently claims more coverage than the doc specifies.
    Disposition: cut named tests added for refresh after forge calls, timeout, overlap, missing state and GitHub unreachable

29. Unproven: item 2: reread failure and submission failure.
    Details promise a toast for failed submission but name no test for it, and give no behavior when the pre-submit `forge next --json` reread fails. Pin that refusal behavior and test that neither failure submits an outdated command.
    Disposition: cut failed re-read and failed submit submit nothing and toast; tested

30. Unproven: item 4: document selection, read failures and Request changes delivery.
    The new tests still omit approval from another story worktree, missing/malformed documents and delivery of the exact Request changes note. Also reconcile “CRLF normalised to LF” with “byte for byte” comparison against a CRLF document by naming the expected normalized text.
    Disposition: cut doc comes from approval.doc in the story's worktree; missing doc tested; expected text is the part with CRLF turned into LF

31. Simpler: separate Request changes input → Claude Code’s native approval interaction.
    The revised owner-facing behavior asks for the native plan prompt, while APPROVE still adds a separate input and submission path. Use the native interaction unless a distinct required behavior needs the extra control; otherwise cut it from the task.
    Disposition: cut Request changes is Claude Code's own prompt answer; no extra control

## Round 3

32. Item 3 still contradicts its session-specific event delivery.
    Details 3 keeps seen identities “per repo”; EVENTS says “per repo and session.” Since [`$.store` is shared across sessions](https://code.claude.com/docs/en/plugins/mods/reference#mods-api-methods), reconcile the contract and name the promised test with two sessions sharing one store. Finding 21 remains open.
    Disposition: cut detail 3 rewritten: seen ids keyed by repo root + session id only; two sessions sharing one store tested

33. Item 3 still specifies event identities that repeated occurrences can reuse.
    Details 3 retains review commits, check suites, question text and end timestamps despite RUNS adding fresh IDs. Replace those identities with the disposition’s occurrence IDs and check attempts; name tests for repeated occurrences and failed-submit retries. Finding 22 remains open.
    Disposition: cut detail 3 now uses only Forge-written ids and check run id plus attempt; repeated question, re-run and failed-submit retry tested

34. The per-item next-command contract is still absent.
    Only the global `next.command` is defined; EVENTS needs one for each changed item. VIEWS must pin the board field and null-command behavior, with a contract test proving different items receive their own next steps. Finding 26 is only partly closed.
    Disposition: cut board --json gives each item its own next.command with the same rule, null otherwise; contract test with two items

35. P1: writing all instructions in VIEWS conflicts with the repository’s same-change review rule.
    PANE, EVENTS, APPROVE and SHIP change coordinator capabilities without an instruction update in their own changes. AGENTS.md explicitly requires that update in the same change. Resolve task ownership without relying on an earlier documentation-only update.
    Disposition: cut each task updates its own guide section in the same change; parallel tasks wait on skill.md via task start

36. Unproven: item 5: Forge versions that reject `--json` entirely.
    The current CLI refuses that flag and returns no machine-view object, so checking its `version` field cannot establish this fallback. Pin how unsupported views are distinguished from ordinary refresh failures and test the actual refusal producing the upgrade line.
    Disposition: cut the too-old line comes only from the real --json refusal text; other failures are refresh failures; both tested

37. Unproven: item 5: the shipped plugin installs and loads in real Claude Code.
    Stubbed CLI tests and validation cannot prove tagged-source resolution, activation after reload, or use across two repos on different Forge versions. Add a SHIP integration test using real Claude Code, isolated user state and a local tagged marketplace fixture so execution needs no network.
    Disposition: cut SHIP adds one real Claude Code integration test with an isolated home and a local tagged marketplace fixture

## Round 4

38. Item 3’s failed-check identity is undefined for the check sources Forge supports.
    GitHub’s [CheckRun schema](https://docs.github.com/en/graphql/reference/checks#checkrun) has no attempt-number field; [commit statuses](https://docs.github.com/en/rest/commits/statuses#get-the-combined-status-for-a-specific-reference), which `checks._seen` also handles, have their own IDs rather than check-run IDs.
    VIEWS must pin identities from fields those providers actually return. Name producer and event tests for failed check runs, failed commit statuses and repeated failures, rather than supplying invented attempt fields in fixtures.
    Disposition: cut a failed check is identified by GitHub's own id: check run database id or commit status id; both and repeats tested from recorded responses

## Round 5

39. Item 3 incorrectly assumes every check rerun gets a new check-run ID.
    GitHub permits an app to [rerequest and update the existing check run](https://docs.github.com/en/rest/checks/runs#rerequest-a-check-run). If it fails again under the same ID, the permanent seen-ID set suppresses the second failure.
    Pin an occurrence key that handles reused IDs, and add VIEWS and EVENTS cases for failed → running → failed with the same check-run ID.
    Disposition: cut a failed check run is keyed by its id plus completed_at, so a re-run under the same id that fails again is a new occurrence; tested in VIEWS and EVENTS

## Round 6

No findings.

## Round 7

40. MACHINE’s required cross-story dependency is missing from After.
    Detail 6 requires FORGE-LANES-1 to merge first, but MACHINE lists only PANE. `task.start` enforces dependencies from After ([task.py:174](/src/forge/task.py:174)). Add the external tasks that deliver the lane view and test progress so Forge cannot start MACHINE prematurely.
    Disposition: keep Forge's After column resolves only stories on the default branch and FORGE-LANES-1 isn't there yet; detail 6 says MACHINE starts only after it merges, and the coordinator checks that

41. PANE does not pin the registration and rendering seams MACHINE needs.
    PANE owns `register.ts`, `pane.ts` and the band, while MACHINE can edit only `machine.ts` and its tests. Unlike EVENTS and APPROVE, MACHINE has no registration stub or shared contract for adding its tab and strip counts. PANE must deliver those seams and a test crossing them; the platform’s [tab example](https://code.claude.com/docs/en/plugins/mods/interface#build-a-pane-with-tabs) composes tabs within the pane renderer.
    Disposition: cut PANE exports addTab and creates machine.ts with registerMachine, called from register.ts, with one test crossing the seam

42. Item 6’s promise to show older repos’ runs contradicts its data producer.
    “New and existing repos” promises those runs appear once any repo runs the new release. The local FORGE-LANES-1 story explicitly says older versions use their own test lock and no agent lane; they therefore do not supply the promised queue entries. Define and test how those runs become observable, or narrow the promise.
    Disposition: cut narrowed: the Machine tab shows repos on this release; older repos show the upgrade line

43. Item 6 has no committed owner or targeting contract for `forge stop`.
    FORGE-LANES-1’s current task table does not deliver this command, and MACHINE scopes no command implementation or command test. Assign its implementation and named test before MACHINE. Pin how stopping a selected row targets another repo, distinguishes identical item names, and handles a run ending or restarting while confirmation is open.
    Disposition: cut forge stop --repo <root> <item> is owned by FORGE-LANES-1 AGENTS with its test; ended or changed runs say nothing to stop

44. Item 6’s telemetry and estimate contracts remain incomplete.
    Detail 6 omits memory rendering and leaves load sampling undefined. Its “last full run time” source also does not exist in the current timings: Forge records worker, review and CI-wait durations, while FORGE-LANES-1 moves full suites to CI. Pin the producer fields, memory units, sampling cadence and duration source, with producer/consumer proof before MACHINE uses them.
    Disposition: cut memory and time-left estimates dropped; load comes from the lanes view, sampled at each refresh, hidden where the OS gives none

45. Unproven: item 6: empty, unavailable and changing machine state.
    The named fixture tests do not cover empty lanes, null progress or missing estimates, Windows load/memory availability, failed or malformed refreshes, growing or unreadable output files, or stop success and failure after confirmation. Pin what each state displays and assign these cases to MACHINE’s Tests cell and the stop command’s owner.
    Disposition: cut each state's display is pinned in detail 6 with a named plugin test

46. Cut or defer: lane and load toasts.
    Detail 6 adds notifications for run starts, outcomes and load thresholds, although item 6 requires machine visibility and controls, and item 3 explicitly says progress only updates the pane. Remove these notifications, or reconcile the owner-facing behavior and assign their occurrence, reload and repetition tests.
    Disposition: cut toasts removed

## Round 8

47. Disputed keep 40: Forge can resolve dependencies before the other story reaches the default branch.
    `story._plan` reads another story’s worktree or local branch ([story.py:378](/src/forge/story.py:378)); `task.start` then waits for its tasks to merge. Add the lane-producing tasks to After rather than replacing that gate with a coordinator check.
    Disposition: cut MACHINE's After now names FORGE-LANES-1/AGENTS and FORGE-LANES-1/TESTS

48. Item 6’s stop contract still cannot distinguish a replacement run.
    `forge stop --repo <root> <item>` carries no identity for the run the person confirmed. A replacement for the same item can therefore be stopped. The current FORGE-LANES-1 plan also specifies only `forge stop <item>`. Pin an expected-run identity, reconcile both plans, and test identical item names across repos and replacement during confirmation.
    Disposition: cut stop targets the lane entry id the person saw (forge stop --id); a replacement has a new id; FORGE-LANES-1 gives entries ids

49. Unproven: item 6: confirmed stop success/failure and failed/malformed refreshes.
    Finding 45’s disposition claims every case has a named test, but detail 6 still names none for successful confirmed stopping, stop failure, or retaining rows after failed/malformed refreshes. Add those cases to the owning Tests cells.
    Disposition: cut confirmed stop, failed stop and kept rows after failed refresh are named MACHINE tests

50. The new refresh contract contradicts itself and can miss GitHub-only changes.
    Detail 1 says to run the board only when snapshot modification time changes, then retains unconditional 30-second and post-command refreshes. No producer is assigned to refresh GitHub when local state stays unchanged. Choose one schedule and test initial load, a check failing without local writes, and retry after a failed refresh with unchanged modification time.
    Disposition: cut one schedule: every 10 s, no snapshot file; GitHub checks cached 60 s by forge board; initial load, red check without local change and retry are tested

51. VIEWS cannot deliver the promised snapshot invalidation within its Scope.
    State, run and lane writers live outside VIEWS’s files. No earlier task pins the snapshot writer, schema or notification interface they must share. Assign those changes and define atomic updates, the shared-Git-directory path across worktrees, and how another repo’s lane change refreshes this session; prove the producer/consumer boundary.
    Disposition: cut the snapshot file is gone, so there is no writer to assign

52. Item 2’s stage timings and round association have no complete producer contract.
    Current timing records contain item, step, start, duration and outcome, but no round; no test-run timing is recorded ([repo.py:115](/src/forge/repo.py:115)). Worker duration also includes tests the worker runs. Assign the missing observations and pin how views expose current stages, retries, skipped stages and other repos’ timings, with producer tests rather than fixtures supplying those facts.
    Disposition: cut RUNS records the round on every timing and times every test run; VIEWS exposes per-item stages; Build includes the worker's own tests

53. Item 2’s narrow and unavailable-lanes layouts drop promised summary content.
    The under-80-column format contains no next step or hotkey, and “no lanes view … omits line 1” also removes their assigned row. `Agents N/M` shows occupancy and capacity without the promised waiting-agent count. Pin layouts retaining the next step and both waiting counts, and test them at narrow width and without lane data.
    Disposition: cut every layout keeps the next step; line 1 shows both waiting counts; without lane data line 1 is the next step

54. Finding 41’s tab seam still leaves the strip’s shared ownership unresolved.
    PANE builds the lane summary in detail 2, while MACHINE also delivers “the strip’s lane line.” `addTab(name, render)` connects only tab content. Assign the strip to one task, or have PANE pin a contribution interface and crossing test before MACHINE uses it.
    Disposition: cut PANE owns the whole strip; MACHINE adds only the tab, spinner line and keys

55. Unproven: item 6: `/forge` text fallback on VS Code, Remote Control and headless sessions.
    PANE owns this behavior but does not cover item 6, and no test names those surfaces. Detail 1 relies on `e.surface`, which the [reference documents for render events](https://code.claude.com/docs/en/plugins/mods/reference#render-sites), although this decision occurs in `command.run`. Pin a supported command-time capability check and prove text output on each promised surface, including Remote Control attached to a drawing terminal.
    Disposition: cut /forge always returns the text summary and opens the pane, so no surface check is needed; a headless test proves the text

56. Split: PANE → plugin transport/refresh and pane/summary controls.
    Packaging, command execution, snapshot watching, refresh recovery, pane rendering, stage summaries, narrow layouts, text fallback, hotkey refusal paths and three registration seams now suggest more than about 400 changed lines. Give transport and lifecycle handling one owner, then let rendering and controls consume its pinned interface.
    Disposition: cut split into CORE (transport, refresh, seams, text) and PANE (pane and strip)

## Round 9

57. Finding 52 remains partly open: test timing changes have no complete owner.
    RUNS promises to time close’s tests and `forge test`, but scopes neither [review.py:251](/src/forge/review.py:251) nor a dependency on the task introducing `forge test`. Assign that boundary, add item 2 to RUNS’s Covers, and name producer tests for round association, actual test durations and skipped tests.
    Disposition: cut RUNS covers 2, scopes review.py and records the test timing inside review.test_run, which forge test also uses; producer tests named

58. Item 2 still has no defined source for other repos’ stage summaries.
    CORE runs `forge board --json` in the session’s repo, while the lanes contract supplies run entries without stage histories or totals. Pin how VIEWS or CORE obtains another repo’s title, current round and stages, and test two repos with different histories. A fixture containing those fields cannot prove their production.
    Disposition: cut the strip shows only this repo's items; other repos appear in the Machine tab from the lanes view

59. CORE’s new shared interfaces remain incomplete and contradict detail 6.
    CORE calls consumers with `data` and `addTab`, but neither contract nor their initial implementation is pinned; PANE delivers `addTab` later. Detail 6 also still assigns creation of `machine.ts` to PANE, whose Scope excludes it. CORE must pin the shared data/update interface and tab stub, with one owner for the summary formatting used by both text and drawing.
    Disposition: cut CORE pins data and onUpdate, creates the pane.ts addTab stub and machine.ts, and owns summary.ts used by text and strip

60. Finding 53’s unavailable-lanes test still contradicts the required behavior.
    Detail 2 now preserves the next step without lanes, but its test still says “no lanes view … omits line 1.” Replace that expectation with proof that the next-step line and applicable hotkey remain available.
    Disposition: cut without lanes the strip keeps the next step and its hotkey; test updated

61. SHIP’s real installation test still depends on PANE.
    SHIP now lists only CORE in After, although its integration test must load the plugin and show the correct pane lines in two repos. CORE creates an empty `registerPane`; it cannot deliver that observation. Restore PANE as a dependency or move the pane integration proof to a task that follows it.
    Disposition: cut SHIP's After is PANE again

62. Unproven: item 1: the GitHub cache survives separate command invocations and expires correctly.
    CORE’s plugin test can prove polling against supplied responses, but not VIEWS’s actual 60-second cache: every refresh starts a new Forge process. Add a producer test covering successive invocations, cache expiry and a GitHub-only check change.
    Disposition: cut a VIEWS producer test covers reuse within 60 s across invocations, expiry, and a GitHub-only change

63. Item 1’s GitHub-fetch coverage is contradictory.
    Detail 1 requires one request for checks on all open pull requests, then retains the rule that checks beyond the newest 25 show `unknown`. Choose the intended fetch/display bound and prove it in VIEWS with more than 25 open pull requests.
    Disposition: cut one request for the newest 25 open pull requests; the rest show unknown; tested with 30

## Round 10

64. Finding 60 remains open: the unavailable-lanes test still removes the required next-step line.
    Detail 2 preserves `1: <next command>` without lane data, but its test still says “no lanes view … omits line 1” ([plan:117](/plans/FORGE-MOD-1.md:117)). Replace that expectation with proof that the next-step line and applicable hotkey remain available.
    Disposition: cut the test now proves the next-step line and its hotkey stay without lane data
