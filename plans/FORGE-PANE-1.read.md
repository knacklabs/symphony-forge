---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-13T08:14:19.876906+00:00
seconds: 692.26
read_hash: ba45440024c51ad1aba75cc1c54b393cc9a700ab
round: 4
passed: no
doc_seen: ba45440024c51ad1aba75cc1c54b393cc9a700ab
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 8312c2d05ca214500184d14576aae58aa8ac6053
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

## Round 2

22. Blocking: The new guide path can overwrite a team’s existing skill.
    Raise: Data loss. Case: normal use - An existing repo already has its own `.claude/skills/forge-guide/SKILL.md`. [RENAME](/plans/FORGE-PANE-1.md:131) ships a new file at that path, and [sync writes differing shipped files](/src/forge/sync.py:589) over their current contents. The preservation rule covers the old folder but not this destination.
    Gain 5, Work 3, Harm 4
    Disposition: cut — Before writing anything, sync refuses while both forge-guide/SKILL.md and the old forge/SKILL.md are there (Forge has not yet written the new folder in that repo), names both and says to rename the team's skill; adoption already refuses a taken path; test_5 checks that nothing changes.

23. Blocking: The old-file ownership check can still delete a team file.
    Raise: Data loss. Case: normal use - A repo adopted on v1.2.2 has its own old-folder `run-reference.md` headed `# Run reference`. [That release did not ship the file](/tests/fixtures/forge-v1.2.2/src/forge/story.py:85), but [the revised rule](/plans/FORGE-PANE-1.md:131) treats that ordinary heading as Forge’s mark and deletes it. The proposed test uses a different heading, so finding 1 remains open.
    Gain 5, Work 3, Harm 4
    Disposition: cut — An old file is removed only when its SHA-256 (CRLF read as LF) is in a frozen list built from every text Forge's own tags shipped for that path; no mark or heading counts; test_5 keeps a team run-reference.md headed # Run reference and a changed standards.md, and doctor names both.

24. Blocking: Split: REMOVE → delete the unused hooks in bounded parts.
    Raise: Plan gap. Case: normal use - The cleanup part is built and reviewed. [The revised plan](/plans/FORGE-PANE-1.md:186) puts about 950 production lines of deletion in REMOVE; [the task-size rule](/.codex/skills/forge/SKILL.md:1685) counts removals and sets a limit of about 400. Finding 21 asked for the removals in bounded parts and remains open.
    Gain 4, Work 2, Harm 2
    Disposition: cut — REMOVE is split into OLD-1 (417 lines), OLD-2 (435) and NEXTJSON (about 95), chained leaves first so no remaining file imports a deleted one; run-reference.md changes in DATA, PANE and NEXTJSON, in that order.

25. Advisory: Runs in another worktree of the same repo are labelled as foreign.
    Raise: Not done. A session started in a story worktree has that worktree as [its session root](/tests/fixtures/claude-code-684800b206824dfd0cc8a876e8604b20f72c3617.d.ts:2363). For a run in a task worktree, neither the main `repo_root` nor the task’s `checkout_root` equals it, so [the new comparison](/plans/FORGE-PANE-1.md:117) adds the repo name. Waits have no `checkout_root` to compare at all.
    Gain 3, Work 3, Harm 3
    Disposition: cut — The pane compares the row's repo_root with its own main checkout, found from the session root's .git folder or file, so another worktree of the same repo is this repo.

26. Advisory: Running tests can hide an unanswered worker question.
    Raise: Not done. [The revised needs-you rule](/plans/FORGE-PANE-1.md:115) suppresses a question when *any* queue entry has the same item. A person can run tests while deciding how to answer; [the test run joins the queue with that item](/src/forge/review.py:390), although the question remains unanswered.
    Gain 3, Work 3, Harm 3
    Disposition: cut — A question now counts while its question_id differs from the record's answered_id, so no queue entry (a test run included) can hide it.

27. Advisory: An answered question returns if the next worker round fails.
    Raise: Not done. Forge [records the answer](/src/forge/worker.py:230), but [clears the question only after a completed result](/src/forge/worker.py:406). If the worker fails, its queue entry leaves and [the revised rule](/plans/FORGE-PANE-1.md:115) shows the already-answered question again.
    Gain 3, Work 4, Harm 3
    Disposition: cut — forge work --note writes answered_id with the owner wait end, so an answered question stays answered when the next round fails or never starts.

28. Advisory: The needs-you scan misses an item in a primary checkout.
    Raise: Not done. A developer can clone or check out a `fix/` or `story/` branch as the primary checkout; [Forge’s existing worktree lookup includes it](/src/forge/story.py:799). [The revised scan](/plans/FORGE-PANE-1.md:115) reads only `.git/worktrees/*`, which lists linked worktrees, so a question or stopped read in that primary checkout is omitted.
    Gain 3, Work 3, Harm 3
    Disposition: cut — The scan includes the main checkout's own branch from .git/HEAD.

29. Advisory: A newly started run includes its time waiting for a place.
    Raise: Not done. If a build waits 20 minutes and then starts, [the revised elapsed rule](/plans/FORGE-PANE-1.md:112) immediately shows 20 minutes. The owner-facing description says the row shows [how long the run has run](/plans/FORGE-PANE-1.md:8).
    Gain 3, Work 4, Harm 3
    Disposition: cut — A waiting run counts its wait from joined_at; once started it counts from first_started_at, kept through relaunch and return; the only restart is the first start, when the words change.

30. Advisory: Always mode reads Forge when the narrow-window pane is closed.
    Raise: Not done. At 80 columns, an unrequested pane is not placed, but [startup still calls `read()`](/plans/FORGE-PANE-1.md:118). That contradicts [the promise that a closed pane reads nothing](/plans/FORGE-PANE-1.md:16).
    Gain 2, Work 1, Harm 1
    Disposition: cut — In always mode the start step reads only when ui.open answers isPlaced; otherwise the tick reads once the pane is placed.

31. Advisory: A stopped spec or decision read is absent from needs-you.
    Raise: Not done. [Forge applies the same read-limit stop](/src/forge/story.py:198) to stories, specs and decisions, but [the scan](/plans/FORGE-PANE-1.md:115) checks read notes only for `story/` branches. A spec or decision read waiting for the person’s choice can therefore leave the line saying nothing needs them.
    Gain 3, Work 4, Harm 3
    Disposition: keep — No local fact names which notes file a fix's spec or decision read uses, short of reading every notes file in every fix checkout at each read; the plan says this case is left out.

32. Advisory: Always mode misses a session started inside a repo subfolder.
    Raise: Not done. [Claude’s session root](/tests/fixtures/claude-code-684800b206824dfd0cc8a876e8604b20f72c3617.d.ts:2363) can be the directory where the session started. If that is `/repo/src`, [the startup check](/plans/FORGE-PANE-1.md:118) looks for `/repo/src/forge.toml`, so it does not open the pane even when `/repo/forge.toml` exists.
    Gain 3, Work 3, Harm 3
    Disposition: cut — The pane walks up from the session root to the folder holding .git and looks for forge.toml there.

## Round 3

33. Blocking: The new guide folder can still overwrite a team file.
    Raise: Data loss. Case: normal use - An existing repo has Forge’s old skill and a team-owned `.claude/skills/forge-guide/run-reference.md`, but no `SKILL.md` in the new folder. [The new guard](/plans/FORGE-PANE-1.md:136) does not refuse, and [sync overwrites the file](/src/forge/sync.py:589). Finding 22 remains open for files alongside the new skill.
    Gain 5, Work 3, Harm 4
    Disposition: cut — The owner chose no rename (13 Nov 2026): the guide skill stays in its folder, no client repo file changes, and the mod answers a typed /forge with its own hook, so this case no longer exists.

34. Blocking: A refused sync can replace a team’s instruction link.
    Raise: Data loss. Case: normal use - A repo has the conflicting guide skills and a `CLAUDE.md` symlink to `AGENTS.md`. [Sync replaces that link with a regular file](/src/forge/sync.py:577) before it calls the proposed refusal in `story.ships`. The link is lost even though [the plan promises no changes on refusal](/plans/FORGE-PANE-1.md:15).
    Gain 4, Work 2, Harm 4
    Disposition: cut — The owner chose no rename (13 Nov 2026): the guide skill stays in its folder, no client repo file changes, and the mod answers a typed /forge with its own hook, so this case no longer exists.

35. Blocking: An exact guide copy can still be a file the team added.
    Raise: Data loss. Case: normal use - A v1.2.2 repo’s team copied a later Forge `run-reference.md` into the old guide folder. [That release did not ship the file](/tests/fixtures/forge-v1.2.2/src/forge/story.py:85), but [the hash rule](/plans/FORGE-PANE-1.md:136) deletes it because its text matches a later release. Finding 23 remains open: matching content does not establish who added the file.
    Gain 5, Work 3, Harm 4
    Disposition: cut — The owner chose no rename (13 Nov 2026): the guide skill stays in its folder, no client repo file changes, and the mod answers a typed /forge with its own hook, so this case no longer exists.

36. Blocking: A changed old skill leaves `/forge` owned after sync succeeds.
    Raise: Functional. Case: normal use - A team has changed its old `forge/SKILL.md`. On its first upgrade, the new skill does not yet exist, so [the guard](/plans/FORGE-PANE-1.md:136) allows sync to create it while preserving the changed old skill. The old skill still owns `/forge`, so the pane cannot open after the reported successful sync.
    Gain 5, Work 3, Harm 4
    Disposition: cut — The owner chose no rename (13 Nov 2026): the guide skill stays in its folder, no client repo file changes, and the mod answers a typed /forge with its own hook, so this case no longer exists.

37. Blocking: An answer can be marked handled before a worker receives it.
    Raise: Data loss. Case: normal use - A person answers a question while the machine is busy, then cancels the queued work command. [The new rule](/plans/FORGE-PANE-1.md:120) records only the answered question’s ID before admission; [the answer text is committed only after admission](/src/forge/worker.py:299). The answer never reaches a worker, but the pane stops showing the question.
    Adds work: retain the answer until a worker can receive it; F 2 x H 2 = 4; 2 x C = 4
    Gain 3, Work 3, Harm 4
    Disposition: cut — answered_id is written only by the round that carries the answer, right after its state commit holding Coordinator note and Answer, which comes after admission and before the worker starts; a cancelled queued command leaves the question shown.

38. Blocking: Questions recorded by an earlier release disappear.
    Raise: Not done. Case: normal use - A repo has an unanswered question from Forge v1.2.2. [That worker recorded the question without a question ID](/tests/fixtures/forge-v1.2.2/src/forge/worker.py:183). Under [the new comparison](/plans/FORGE-PANE-1.md:120), both IDs are absent and equal, so the pane says nothing needs the person.
    Gain 3, Work 3, Harm 4
    Disposition: cut — A question without a question_id (the v1.2.2 shape) always counts until a round clears it; only a present question_id equal to answered_id hides it.

39. Blocking: An earlier release’s run clock can reset on its second launch.
    Raise: Not done. Case: normal use - An older build remains running during an upgrade and receives the normal commit nudge. [The older worker resets `started_at`](/src/forge/machine.py:322), and [the revised rule falls back to that value](/plans/FORGE-PANE-1.md:125) for earlier releases. Finding 12 therefore remains open for those runs.
    Gain 3, Work 2, Harm 3
    Disposition: cut — An entry without first_started_at counts from joined_at, which earlier releases also set once per round, so a second launch never resets it.

40. Blocking: Doctor can hold back an exact old guide that the plan says it repairs.
    Raise: Not done. Case: normal use - A client committed a previous `forge sync` separately from its version-pin change. Even when the old guide matches the frozen hash list, [doctor’s existing ownership check](/src/forge/doctor.py:203) holds a file last changed by that ordinary commit back. This contradicts [the promised repair](/plans/FORGE-PANE-1.md:136) and can leave the old skill owning `/forge`.
    Gain 4, Work 3, Harm 4
    Disposition: cut — The owner chose no rename (13 Nov 2026): the guide skill stays in its folder, no client repo file changes, and the mod answers a typed /forge with its own hook, so this case no longer exists.

41. Advisory: A build can appear to wait after its tests have returned its place.
    Raise: Functional. [Returning from tests clears `started_at`](/src/forge/machine.py:345), and re-admission sets `admitted` without restoring it. [The planned rule](/plans/FORGE-PANE-1.md:117) therefore labels the resumed build as waiting.
    Gain 3, Work 3, Harm 3
    Disposition: cut — waiting is now place above 0 or machine._admitted false, so a build that got its place back is not waiting.

42. Advisory: The review-output test can pass with an empty live log.
    Raise: Test. [DATA’s test](/plans/FORGE-PANE-1.md:150) checks only that the review output path exists. A buffered writer that does not flush until the review ends passes that check, while a person opening the output during the review sees no lines.
    Gain 3, Work 3, Harm 3
    Disposition: cut — The review log is flushed after each line, and test_3 reads it while the stub reviewer still runs.

43. Advisory: Queue order can differ from the promised start order.
    Raise: Not done. [Forge prioritizes some later arrivals](/src/forge/machine.py:615), so they can start before an earlier waiting build. [The planned drawing](/plans/FORGE-PANE-1.md:128) sorts by join time instead of start time.
    Gain 3, Work 3, Harm 3
    Disposition: cut — One stated key, joined_at then id (the order Forge took the rows in); the owner text and done-when 3 now say that order instead of start order.

44. Advisory: Changing repos during a session leaves the pane’s repo identity stale.
    Raise: Not done. [Claude’s session root changes on `/cd`](/tests/fixtures/claude-code-684800b206824dfd0cc8a876e8604b20f72c3617.d.ts:2362), but [the plan finds the repo only at session start](/plans/FORGE-PANE-1.md:123). After moving to another repo, its rows and questions are labelled relative to the first one.
    Gain 3, Work 3, Harm 3
    Disposition: cut — The pane finds its repo again at each read and each /forge, so a /cd moves the labels with it.

## Round 4

45. Blocking: Keeping the old guide path can overwrite a team file.
    Raise: Data loss. Case: normal use - A v1.2.2 client added its own `.claude/skills/forge/run-reference.md`, which [that release did not ship](/tests/fixtures/forge-v1.2.2/src/forge/story.py:85). The new plan keeps that path and [changes the shipped reference](/plans/FORGE-PANE-1.md:153). On upgrade, [sync overwrites the differing file](/src/forge/sync.py:589). Finding 1 remains open through an overwrite instead of a deletion.
    Gain 5, Work 3, Harm 4
    Disposition: keep — The plan adds no new write in a client repo: Forge already ships {.claude,.codex}/skills/forge/run-reference.md and rewrites it on every sync (src/forge/story.py:100-102, since commit e068513c7, first in v1.2.26), so a team file at that path is already overwritten by any upgrade since then; Forge's existing rule for a file it ships applies.

46. Blocking: A cancelled queued answer can still close the shared question.
    Raise: Data loss. Case: normal use - An item has an open pull request. The person answers its question, then cancels while the run waits for a place. [The revision](/plans/FORGE-PANE-1.md:118) delays `answered_id`, but [the existing worker records and publishes the wait’s end before admission](/src/forge/worker.py:230). On a later attempt, [the worker clears the question from that published end](/src/forge/worker.py:174), although the answer was never committed or delivered. Finding 37 remains open.
    Gain 3, Work 3, Harm 4
    Disposition: cut — The owner's rule (13 Nov 2026, "Simple and always true") has no answered state: an item shows while its record holds a question and no build round of it runs or waits; the worker.py change and its tests are gone.

47. Blocking: An answered question from an earlier release stays visible.
    Raise: Not done. Case: normal use - A person answers a question written by v1.2.2, and the next worker round is running or fails. [That release recorded no question ID](/tests/fixtures/forge-v1.2.2/src/forge/worker.py:183), and [the revised rule](/plans/FORGE-PANE-1.md:118) always counts such a question until a round clears it. The pane therefore still shows the answered question, leaving finding 7 open for earlier releases.
    Gain 3, Work 2, Harm 3
    Disposition: cut — No answered state exists any more; an earlier release's question is read the same way as any other (the record's question, and no build round running or waiting).

48. Blocking: The older-release time rules still disagree.
    Raise: Plan gap. Case: normal use - An older build receives a commit nudge and launches again. [The data contract](/plans/FORGE-PANE-1.md:115) falls back to `started_at`, which resets on launch; [the Time rule](/plans/FORGE-PANE-1.md:123) instead says to use `joined_at`. Following the contract still resets the clock, so finding 39 is not closed by the stated rules.
    Gain 4, Work 1, Harm 3
    Disposition: cut — One clock start, named once in the data contract and used by the Time rule: first_started_at when present, else joined_at; started_at is never used, because a second launch resets it.

49. Advisory: A failed answered round can leave work blocked while the pane says nothing needs you.
    Raise: Not done. For an item without a pull request, an answered round can fail after `answered_id` is recorded. [The pane hides the question](/plans/FORGE-PANE-1.md:118), but the retained question still makes [a plain `forge work` retry refuse](/src/forge/worker.py:201) and ask for the answer again.
    Gain 3, Work 3, Harm 3
    Disposition: cut — No answered state exists any more: after a failed round the record still holds the question and the item shows again, which matches the refusal of a plain forge work retry.

50. Advisory: The needs-you scan misses migration worktrees.
    Raise: Not done. [The scan](/plans/FORGE-PANE-1.md:118) checks `task/`, `fix/` and `story/` branches, but migration uses [`forge/migrate-v1`](/src/forge/migrate.py:81), which [Forge treats as a fix branch](/src/forge/task.py:173). A worker question or stop there is omitted.
    Adds work: include migration worktrees in the scan; F 1 x H 2 = 2; 2 x C = 2
    Gain 3, Work 1, Harm 4 (floor: migration)
    Disposition: cut — The scan includes forge/ branches (migrate's fix branch), which task.branch_item already maps.

51. Advisory: An older Forge source checkout can save an incomplete shared snapshot.
    Raise: Not done. When Forge is installed from its source and the pane runs in an older worktree of that source, [the CLI runs that checkout’s code](/src/forge/cli.py:117). Its older `lanes` command can omit other releases and `needs_you`, yet [the pane stores its answer under the shared key](/plans/FORGE-PANE-1.md:119). Another session can initially show that incomplete answer.
    Gain 3, Work 3, Harm 3
    Disposition: cut — The pane stores only answers that carry needs_you (this release's shape); an older checkout's answer is shown but never stored.
