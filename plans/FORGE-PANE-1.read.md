---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-13T06:55:36.949279+00:00
seconds: 972.642
read_hash: ac95d27a4a38f3f9a607fb9430308719dce7d8b4
round: 1
passed: no
doc_seen: ac95d27a4a38f3f9a607fb9430308719dce7d8b4
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1d3a1-e831-77b1-bb3d-127c2003a663
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

1. Blocking: The upgrade can delete a team’s own guide files.
   Raise: Data loss. Case: normal use - A repo adopted on v1.2.2 has added its own `run-reference.md` under the old guide folder. [The old release](/tests/fixtures/forge-v1.2.2/src/forge/story.py:85) did not ship that file, but [the plan](/plans/FORGE-PANE-1.md:124) deletes it solely because the path exists. [Sync](/src/forge/sync.py:594) unlinks it.
   Gain 5, Work 3, Harm 4
   Disposition: cut — RENAME removes an old guide file only when it carries Forge's mark (the generated line, or the first line Forge's copy of that name starts with); any other file in the old folder stays, and test_5 holds a team run-reference.md with its own first line.

2. Blocking: An older running process can make the whole pane read fail.
   Raise: Not done. Case: normal use - An earlier Forge release still has a run on the laptop. [The queue conversion](/src/forge/machine.py:578) puts its process-identity timestamp into `started_at`; that timestamp is not ISO format. Removing the release filter as [planned](/plans/FORGE-PANE-1.md:110) sends it to [the ISO parser](/src/forge/machine.py:438), which fails the entire read. Older waiting entries with neither timestamp are also omitted.
   Gain 4, Work 2, Harm 3
   Disposition: cut — DATA checks each entry on its own and leaves out only an entry whose joined_at is not an ISO time (legacy entries from before lane ids), so one bad entry never fails the read; elapsed now counts from joined_at.

3. Blocking: Stop does not stop a session subagent.
   Raise: Functional. Case: normal use - A person selects a build handed to a Claude session subagent and confirms Stop. [The planned action](/plans/FORGE-PANE-1.md:118) calls `forge stop`, but [that command](/src/forge/machine.py:513) only releases Forge’s hold for a native run; the subagent keeps working.
   Adds work: stop the selected subagent; F 2 x H 2 = 4; 2 x C = 4
   Gain 4, Work 2, Harm 3
   Disposition: cut — Stop run is not offered on a session subagent row, because neither forge stop nor the mod API can stop that subagent; the owner's text says to ask the agent.

4. Blocking: Reviews have no output button.
   Raise: Functional. Case: normal use - A person selects a running review. [The plan](/plans/FORGE-PANE-1.md:118) shows Open output only with `output_path`, but [the review process](/src/forge/autoreview.py:54) does not set one. The paths cited as review output in the plan are [test logs](/src/forge/review.py:438).
   Adds work: make review output available to the pane; F 2 x H 2 = 4; 2 x C = 4
   Gain 4, Work 2, Harm 3
   Disposition: cut — DATA makes autoreview write its streamed lines to a review log and pass it to agent_process, so a review row has output_path; the evidence line now names the test logs correctly.

5. Blocking: A question in another idle repo disappears from the needs-you line.
   Raise: Not done. Case: normal use - A worker asks a question and its run ends; the person opens the pane from another repo. [The planned scan](/plans/FORGE-PANE-1.md:112) checks only the current repo and repos with live rows, while [the worker’s lane entry is removed](/src/forge/machine.py:378) when the round ends. The pane can say nothing needs the person.
   Gain 3, Work 2, Harm 3
   Disposition: cut — The needs-you scan now covers every repo Forge remembers on the laptop, reading worktrees from the .git/worktrees files with no git command.

6. Blocking: A stopped plan read is omitted from the needs-you line.
   Raise: Not done. Case: normal use - A plan read reaches its round limit and waits for the owner’s choice. [Forge records that stop in the read notes](/src/forge/story.py:172), but [the plan](/plans/FORGE-PANE-1.md:112) scans only task and fix branches and their state stops. This is different from a plan merely waiting for approval.
   Gain 3, Work 2, Harm 3
   Disposition: cut — A plan read stopped at its round limit (story.stopped true, no loop_choice in the story worktree's read notes) now counts as a stop.

7. Blocking: An answered worker question remains shown as needing the person.
   Raise: Not done. Case: normal use - The person answers a question and the next worker round is running. [Forge records the answer](/src/forge/worker.py:230), but clears or replaces the thread’s `question` only when the round finishes at [worker.py:420](/src/forge/worker.py:420). [The planned scan](/plans/FORGE-PANE-1.md:112) treats that non-empty field as an open question throughout the round.
   Gain 3, Work 2, Harm 3
   Disposition: cut — A question counts only while the thread record holds it and no queue entry exists for that item: an answer starts a new round, whose entry stays until the round ends and clears the record.

8. Blocking: A cached answer from one repo is shown as the answer for another.
   Raise: Not done. Case: normal use - Two sessions use different repos and the second starts after the first saved a snapshot. [The single shared key](/plans/FORGE-PANE-1.md:113) also stores repo-specific `repo_root` and `needs_you`, so the second pane initially labels rows and questions relative to the first repo. If its read fails, that wrong answer remains.
   Gain 3, Work 2, Harm 3
   Disposition: cut — The answer is now laptop-wide (repo_root dropped, needs_you a list); the pane works out its own repo from $.session.root() against each row's repo_root or checkout_root, for stored and fresh answers alike.

9. Blocking: An automatically opened pane waits up to three seconds for its first content.
   Raise: Not done. Case: normal use - A new session has the option set to always and has no saved snapshot. [Startup](/plans/FORGE-PANE-1.md:114) opens the pane without starting a read; [the timer](/plans/FORGE-PANE-1.md:115) starts the first one on its third tick. That misses item 2’s 300 ms limit.
   Gain 4, Work 1, Harm 3
   Disposition: cut — With the option always, the start step opens the pane and starts a read at once (neither awaited), so stored content shows at once and the first read does not wait for a tick.

10. Blocking: A failed read after an empty snapshot has no specified failure line.
    Raise: Test. Case: normal use - A successful read says nothing is running, then Forge stops answering. [The failure rules](/plans/FORGE-PANE-1.md:123) cover a snapshot with rows and no stored snapshot, but not a stored empty snapshot. [The test](/plans/FORGE-PANE-1.md:135) can pass while the pane keeps showing the old empty state without its age.
    Gain 3, Work 1, Harm 3
    Disposition: cut — Once any answer was shown or stored, a failure keeps its rows or Nothing is running. and adds Last update <time> ago. Forge did not answer.; mod test 2 covers the empty case.

11. Blocking: Waiting runs and tests with progress lose their round.
    Raise: Not done. Case: normal use - A review is waiting, or a test reports completed and total counts. [The prescribed words](/plans/FORGE-PANE-1.md:123) replace the round with the waiting or progress text, although [the queue records a round](/src/forge/machine.py:214) and item 3 requires it for every run.
    Gain 3, Work 1, Harm 3
    Disposition: cut — The detail now keeps Round <n> before the waiting words and the test counts; the design pages show those rows without a round, which goes to the coordinator as a design change.

12. Blocking: A run’s displayed time can move backwards during the same round.
    Raise: Not done. Case: normal use - A worker finishes a turn with uncommitted changes and receives the normal commit nudge. [The existing test](/tests/test_lanes_agents.py:156) describes this second launch; [each launch resets `started_at`](/src/forge/machine.py:322), and [elapsed time uses that value](/src/forge/machine.py:438). The planned pane therefore resets the same row’s clock.
    Gain 3, Work 2, Harm 3
    Disposition: cut — The time counts from joined_at, set once when the round joins and kept through relaunch and suspension; mod test 2 and test_3 cover a second launch.

13. Blocking: A run waiting for machine resources can appear to be running.
    Raise: Functional. Case: normal use - The laptop is busy or low on memory while a queue place is free. [Admission still waits](/src/forge/machine.py:275), but [the place value can be zero](/src/forge/machine.py:182). [The pane’s rule](/plans/FORGE-PANE-1.md:123) uses only a positive place to identify a wait.
    Adds work: represent the resource wait in the row; F 2 x H 2 = 4; 2 x C = 2
    Gain 3, Work 1, Harm 3
    Disposition: cut — DATA adds waiting (place above 0 or no started_at), so a run held by load or memory reads Waiting for a free place, with the busy line below.

14. Blocking: The planned setup-check test contradicts the check’s preservation rule.
    Raise: Plan gap. Case: normal use - An old guide is restored by hand and committed in a client repo. [The planned test](/plans/FORGE-PANE-1.md:145) expects the ordinary repair message, but [doctor holds a hand-changed file back](/src/forge/doctor.py:203). The test also does not run the promised repair.
    Gain 4, Work 2, Harm 4
    Disposition: cut — The leftover case commits the old copy with doctor's own subject, so doctor treats it as Forge's file, then checks the differs line, runs forge doctor --fix and checks the removed line and that team files stay.

15. Blocking: Deleting the old tests leaves the timing inventory failing.
    Raise: Plan gap. Case: normal use - PANE deletes the named test files. Their entries remain in [.test_durations](/.test_durations:216), so [the inventory check](/tests/test_ci_timing_inventory.py:12) reports obsolete tests. The timing file is absent from [PANE’s scope](/plans/FORGE-PANE-1.md:176).
    Gain 4, Work 1, Harm 2
    Disposition: cut — Each part that deletes or renames a test removes its keys from .test_durations in the same part (checked by test_ci_timing_inventory); PANE and REMOVE list the file in Scope.

16. Blocking: The real-session test is filtered out of the plugin CI job.
    Raise: Test. Case: normal use - The new test file is added to the existing pytest command as [planned](/plans/FORGE-PANE-1.md:132). [The job’s `-k` filter](/.github/workflows/forge-next.yml:69) selects only the two existing plugin cases, so the new test is deselected while the job can pass.
    Gain 4, Work 1, Harm 3
    Disposition: cut — The plugin job gets its own pytest line for tests/test_pane_session.py after installing Claude Code 2.1.322; if the headless run cannot start the mod there, the test skips with the reason and the coordinator's by-hand step is the proof.

17. Blocking: The replacement tests do not exercise the two retained buttons.
    Raise: Gate. Case: normal use - A person opens a selected run’s output or confirms a stop. [The deleted tests](/src/forge/mod/hooks/machine.test.ts:136) exercise selection, output, confirmation and the selected run; [the replacement](/plans/FORGE-PANE-1.md:140) checks that buttons exist, while the manual check only cancels Stop.
    Adds work: retain those button behaviour checks; F 2 x H 2 = 4; 2 x C = 4
    Gain 3, Work 2, Harm 3
    Disposition: cut — Mod test 3: buttons presses a row, Open output (pane and lines or the empty words) and Stop run (question, Keep running, Stop with the selected id, ended run, no Stop on a session subagent row).

18. Blocking: Moving the next-step performance test to the board weakens its proof.
    Raise: Gate. Case: normal use - A repo has many finished fixes and active stories. [The existing test](/tests/test_next_reuses_command_work.py:89) bounds work done by `forge next`; [the deletion plan](/plans/FORGE-PANE-1.md:151) moves its JSON reads to `forge board --json`. A slow `forge next` path could then pass.
    Adds work: retain the next command’s performance check; F 2 x H 2 = 4; 2 x C = 4
    Gain 3, Work 2, Harm 3
    Disposition: cut — Tests that check forge next itself switch to plain forge next and keep their bounds; only row checks move to forge board --json.

19. Blocking: DATA changes the command before its guide is updated.
    Raise: Gate. Case: normal use - DATA merges while PANE is still waiting. [The current guide](/src/forge/templates/run-reference.md:48) says other releases are omitted, but DATA changes that result and [defers the guide update](/plans/FORGE-PANE-1.md:143). The repository review rule requires the coordinator guide or worker brief to change in the same change.
    Gain 4, Work 2, Harm 2
    Disposition: cut — DATA now updates run-reference.md (every release's rows, the new fields, elapsed from joining) and the forge-guide copies in the same part, after RENAME.

20. Blocking: The DATA test’s platform instructions conflict.
    Raise: Plan gap. Case: normal use - The Windows suite selects platform-marked tests. [The plan](/plans/FORGE-PANE-1.md:83) requires a module-level platform mark for the path-comparing test, but puts the `resource`-using test in that same file and says it has no platform mark at [line 142](/plans/FORGE-PANE-1.md:142). The module mark also selects it on Windows.
    Gain 4, Work 1, Harm 2
    Disposition: cut — test_3 (paths, platform mark) and test_4 (resource, no mark) now live in separate files, under one stated platform rule.

21. Blocking: Split: PANE → switch the pane, then remove the old hooks in bounded parts.
    Raise: Plan gap. Case: normal use - The part is built and reviewed. [Its scope](/plans/FORGE-PANE-1.md:176) removes 982 production hook lines and adds about 330, over the plan’s roughly 400-line task limit even before other changes.
    Gain 4, Work 2, Harm 2
    Disposition: cut — PANE is split: PANE switches to the new mod (about 390 counted lines) and REMOVE deletes the unused hook files and forge next --json; the story has four parts in a chain, RENAME, DATA, PANE, REMOVE.
