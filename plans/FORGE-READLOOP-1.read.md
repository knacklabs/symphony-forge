---
reader: codex (gpt-6-sol)
read_at: 2026-09-28T15:50:11+00:00
read_hash: 681c20e42cbf8596b0ec19010db15c8a4143e6f6
amended_hash: 95dece00b89a6360a1c1c2b70c43509cbf1691b8
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. The plan does not preserve the same reader across rounds.
   `forge read` currently chooses the reader from the app coordinating that invocation ([story.py](/src/forge/story.py:153)). Running a later round from the other app switches reader families. Pin whether Forge uses the recorded reader or refuses a mismatched invocation.
   Disposition: cut: item 1 keeps the recorded reader family and refuses a round from the app that is itself the reader.

2. The pass gate needs a rule for confirmed specs.
   `spec confirm` changes the spec’s frontmatter after its passing read, and `spec measure` later changes its body ([records.py](/src/forge/records.py:163)). A pull-request check against the full `read_hash` would reject those existing flows. Define which changes require another round and how the check recognizes permitted confirmation or measurement changes.
   Disposition: cut: item 2 gates only unconfirmed specs; a confirmed spec's confirm and measure changes need no new round.

3. An approved story can start tasks after its Tasks table changes without another read.
   `forge next` checks the read only while approval is pending, and `forge task start` checks an approval hash that excludes the Tasks table ([nextstep.py](/src/forge/nextstep.py:226), [task.py](/src/forge/task.py:137)). Pin the post-approval gate and add `src/forge/task.py` to the owning scope if task start must refuse.
   Disposition: cut: item 2 adds forge task start to the gate, so a changed Tasks table needs a passing round; task.py is in GATES' Scope.

4. SPEC needs to pin the round-notes contract that LOOP will parse.
   The plan names `round` and `passed`, but does not define how to identify a round’s exact `No findings.`, number findings across rounds, or dispose of a new `Disputed keep` before the next read. Existing notes also lack those fields; specify how old unapproved reads continue and how previously approved stories retain approval ([story.py](/src/forge/story.py:491)).
   Disposition: cut: Notes pin the round contract (round, passed, ## Round <n>, numbering, old notes as round 1); item 3 says how a disputed keep is disposed; item 2 says old approved stories keep approval.

5. Unproven: items 1–3: round recovery and refusal paths.
   The Tests cells name files but no cases for an unavailable Codex conversation, a failed or discarded round, legacy notes, a changed approved Tasks table, spec confirmation, or a disputed keep settled by the human. Put the required cases in the relevant Done-when items and their tests in the owning task’s Tests cell.
   Disposition: cut: items 1 and 2 now name each recovery and refusal case their tests cover.

6. Item 5 does not pin how a learned trap reaches the outcome pull request.
   `forge story done` currently opens a fix containing only state changes ([story.py](/src/forge/story.py:224)). Specify the skill step that checks the review-round threshold, edits `AGENTS.md` in that fix, and verifies the trap ships with the outcome.
   Disposition: cut: item 5 says the agent adds the trap lines in the outcome fix's worktree and commits them before closing it.

7. Split: LOOP → round execution and pass gates.
   LOOP owns three Done-when items across six Python modules, two docs, an adapter, and the real-SDK tests; its scope suggests more than about 400 changed lines. Put round execution in one task and approval, spec, PR, and post-approval gates in a following task.
   Disposition: cut: LOOP is split into ROUNDS (items 1, 6) and GATES (item 2, after ROUNDS).

## Round 2 (run by hand on gpt-6-sol xhigh)

8. Finding 2 remains open. The exemption for confirmed specs covers any spec that still says `status: confirmed`, not just `spec confirm` and `spec measure` changes. A direct Behaviour edit can retain that status without a new read; [records.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/records.py:123) validates the body only when `spec save` runs. Pin how the pull-request check distinguishes the permitted changes, and test a substantive edit to a confirmed spec.
   Disposition: cut: item 2 keeps confirmed specs under their existing confirmed hash; the pull-request check refuses a body edit, and confirm and measure refresh it.

9. Finding 3 remains open. After the first task merges, [task start](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/task.py:126) reads the doc from `origin/main`, even if the story worktree has a newly read Tasks table. `forge read` writes notes but does not commit that amended doc. Pin which version starts the next task and how the passing doc and notes reach its base; test this after one task has merged.
   Disposition: cut: item 2 has task start read the doc and notes from the story branch and merge it into the new task branch; tested before and after the first merge.

10. The legacy approval exception needs a boundary. Item 2 lets a story approved before this change start tasks without a passing round, while also requiring a new round for edits after approval. It does not say whether the exception ends when that old story’s Tasks table changes. Test both an unchanged legacy approval and a later edit to it.
   Disposition: cut: item 2 ends the old-approval exception at the doc's first change; both cases tested.

11. GATES cannot make its promised test updates within its listed paths. Existing `--amended` assertions occur in [test_codex_reader.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/tests/test_codex_reader.py:144), [test_story.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/tests/test_story.py:250), [test_approval.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/tests/test_approval.py:66), and [test_split_commands.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/tests/test_split_commands.py:201), among others. The [GATES row](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:91) names none of them in Scope or Tests.
   Disposition: cut: GATES' Scope names the tests that use --amended.

12. Unproven: item 3, a human-settled disputed keep. The plan assigns this entirely to prompt and skill text, but does not say what happens if the next reader raises the same dispute again. No named test proves that the recorded human answer is accepted, despite item 3 promising that outcome.
   Disposition: cut: item 3's round prompt never re-raises a finding whose disposition cites a Decided line; SPEC's test checks it.

13. Finding 6 remains open on proof. Item 5 now instructs the agent to commit learned traps, but neither its Done-when text nor SPEC’s Tests cell checks the two-round or two-task trigger, creation of a missing `## Known traps` section, or that the trap commit reaches the outcome fix’s pull request. [story done](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:224) currently opens a fix containing only state changes.
   Disposition: cut: item 5 adds creating a missing section and SPEC's test checks every step and threshold in the synced skill.

14. Unproven: item 4, the case-to-test rule as applied to this story. The [Tests cells](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:87) name files, not tests for each promised case: a failed round, exact `No findings.` rejection variants, the round-four nudge, Windows PowerShell and cmd, and WSL have no identified proof. The current [CI matrix](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/.github/workflows/forge-next.yml:17) covers Ubuntu, macOS, and Windows, but identifies no WSL or shell-specific run.
   Disposition: cut: each Tests cell names its cases; Notes say no item runs its own shell commands, so CI's three systems cover it.

## Round 3 (run by hand on gpt-6-sol xhigh)

15. The Tests cells do not name usable test paths. [Forge’s parser](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:573) treats each comma-separated entry as a path, so entries such as `tests/test_readloop_rounds.py: a continued round` become literal paths and [review scope matching](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/review.py:161) will mark the real test file outside the task. GATES’ “and any other test that uses `--amended`” is likewise not a path; [test_records.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/tests/test_records.py:168) and [test_prcheck.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/tests/test_prcheck.py:88) still need explicit ownership. Earlier finding 11 remains open.
   Disposition: cut: Tests cells are plain paths; ROUNDS' Scope names all six tests that use --amended.

16. Earlier finding 9 remains open: merging the story branch does not carry an amended doc or passing notes that have not been committed. A read [writes notes without committing them](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:190), and a Tasks-only edit does not trigger the [approval commit](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/approval.py:86). Item 2 must pin when those files are committed before task start, both before and after the first task merges, and test that the task branch contains them.
   Disposition: cut: item 2 says a passing round commits the doc and notes on the story branch, and tests that the task branch contains them.

17. The legacy-notes diff has no guaranteed source text. Old reads calculated `read_hash` [without `git hash-object -w`](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:161); an uncommitted doc read then edited may have no retrievable blob. [Counting old notes as round 1](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:52) conflicts with the required previous-round diff. Pin the fallback and test an old unapproved read whose original text is unavailable.
   Disposition: cut: item 1 starts a fresh round without a diff when the previous text can't be found, with a test.

18. Unproven: item 2’s exact pass rule. The [GATES test promise](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:54) names the positive `No findings.` case, but no rejection cases such as `No findings.\n1. defect` or leading text. The current reader [accepts a “no findings” prefix](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:187), so these variants need explicit gate tests.
   Disposition: cut: item 2 pins the trimmed exact-text rule and tests its near misses.

19. Earlier finding 13 remains open on proof. [SPEC’s test](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:96) checks that the skill says to commit a learned trap; it does not prove a triggered trap reaches the outcome fix’s pull request. [The outcome fix](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:224) currently records only state changes. Pin an artifact check for both threshold triggers and the missing-section case, or narrow item 5 to the instruction the test actually proves.
   Disposition: cut: item 5 is narrowed to the instruction, which SPEC's test proves.

20. Split GATES further. Its [Scope](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:98) spans six production modules, documentation, an adapter, existing test rewrites and a new gate suite. That still suggests more than the stated roughly 400 changed lines for one task, even after the earlier LOOP split.
   Disposition: cut: the gate is split: GATES (stories, item 2) and SPECS (specs, new item 7); ROUNDS takes --amended's removal.

## Round 4 (run by hand on gpt-6-sol xhigh)

21. **Earlier finding 8 remains open.** Item 7 does not say how the pull-request check distinguishes `spec measure` from an edit that changes both a confirmed spec’s body and its `confirmed_hash`. Both values live in the same file, and measurement legitimately refreshes the hash ([plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:84), [records.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/records.py:188)). Pin the trusted comparison and test a body-plus-hash edit. Also test `spec confirm` on an edited confirmed spec: it currently returns before checking the hash ([records.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/records.py:145)).
   Disposition: cut: item 7 leaves confirmed specs on today's rules, so there is no confirmed-spec comparison to pin.

22. **The `--amended` removal crosses task ownership.** ROUNDS promises to remove it and update every test that uses it, including `test_records.py` and `test_prcheck.py`, but the corresponding production messages are in `records.py` and `prcheck.py`, owned later by SPECS ([plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:102), [records.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/records.py:51), [prcheck.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/prcheck.py:30)). Assign those message and test changes together so ROUNDS can pass before SPECS starts.
   Disposition: cut: the --amended removal is its own item 8 and task CUT, which owns records.py and prcheck.py messages and every test that used it.

23. **An approved story’s `forge next` path is still unpinned after a Tasks-table edit.** Its read check currently runs only when approval is pending; otherwise it can offer `forge task start` ([nextstep.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/nextstep.py:226)). Item 2 tests task-start refusal, but items 2 and 6 do not require a test that `forge next` names the needed read and round for this post-approval state ([plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:46)).
   Disposition: cut: item 2 tests forge next naming the read and round for an approved story whose doc changed.

24. **Unproven: item 1’s Claude next round.** Item 1 requires a recorded Claude reader to start a fresh round with the first-round instructions, but its named cases cover fresh Codex recovery and legacy notes without explicitly covering a second Claude round. Name that case in ROUNDS’ test contract ([plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:34)).
   Disposition: cut: item 1 tests a second round with a Claude reader.

25. **Unproven: item 2’s archive boundary.** The plan requires archiving the Codex conversation when a round passes, but names no test that it remains available after a round with findings, or what happens when archiving fails. The current read archives after any successful turn and reports archive failure without failing the read ([story.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:192), [plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:57)).
   Disposition: cut: item 2 archives only on a pass, keeps the conversation after findings, and treats a failed archive as a note; both tested.

26. **Split: ROUNDS remains over the task-size target.** It owns round execution, notes, conversation recovery, reader pinning, the nudge, command removal, six existing test files, documentation, and a new real-SDK suite across thirteen listed paths. That scope suggests more than about 400 changed lines despite covering only two Done-when items ([plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:102)).
   Disposition: cut: ROUNDS keeps rounds and the nudge; the removal moved to CUT.

## Round 5 (run by hand on gpt-6-sol xhigh)

27. **ROUNDS cannot both drop `amended_hash` and keep `--amended` working until CUT.** The plan requires both in the same handoff ([plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:119)). Today, `--amended` writes that field and the read gate uses it ([story.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:143)). Pin the temporary record and gate behavior so ROUNDS passes before CUT removes the command.
   Disposition: cut: Notes say ROUNDS leaves amended_hash, --amended and today's gate as they are; CUT drops them.

28. **A human-settled keep can be disputed again.** Item 3 puts the `Decided:` citation on the *new disputed finding*, while the original kept finding still has its old reason ([plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:60)). The next-round rule protects only a finding whose own disposition cites that line. Pin how the original finding is marked settled, and test a further round that sees both findings.
   Disposition: cut: item 3 gives both the original kept finding and the disputed one a keep citing the Decided line.

29. **Changed tests are missing from their tasks’ Tests cells.** SPEC will need to update the shipped-skill hash in [test_split_ships.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/tests/test_split_ships.py:21), and CUT promises to rewrite six existing `--amended` test files. The plan puts those files only in Scope and lists only new suites under Tests ([plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:105)). Forge’s [test-audit skill](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/.codex/skills/test-audit/SKILL.md:15) requires every added or changed test in that column; list the affected files there.
   Disposition: cut: each task's Tests cell lists the existing tests it changes.

## Round 6 (run by hand on gpt-6-sol xhigh)

30. **Finding 29 remains open for CUT.** Item 8 removes the one-read wording, but CUT’s Scope omits [cold-read.md](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/templates/cold-read.md:57), the [Forge skill template](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/templates/skill.md:17), its two shipped copies, and the repository’s generated [AGENTS.md](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/AGENTS.md:14). Changing that generated output also changes hashes asserted by [test_split_ships.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/tests/test_split_ships.py:18), which CUT lists in neither Scope nor Tests. Assign these changes and that test to a task.
   Disposition: cut: CUT's Scope and Tests add the skill, its synced copies, cold-read.md, the repo's AGENTS.md and test_split_ships.py; item 8 names them.

31. **Unproven: items 1–2, malformed reader output.** The plan counts every response other than exact `No findings.` as a round with findings, but does not say how to dispose of a response such as `No findings.\nAdditional concern` that contains no numbered finding. The current [output handling](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:187) leaves such text unnumbered, while [undisposed](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:344) detects only numbered findings. Pin whether ROUNDS numbers that response or refuses it, and test that another round cannot bypass its disposition.
   Disposition: cut: item 1 numbers an unnumbered reply as one finding, as today, with a test.

32. **Trap: a story branch can miss a newly learned trap (item 5).** `forge read` uses the [story checkout](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:446), whose AGENTS.md can predate a trap later merged through another story’s outcome fix. The plan says every cold read checks the repo’s traps but does not say which version to read or test this state. Pin the source of current traps for an older story branch.
   Disposition: cut: item 5 has Forge put the default branch's Known traps section into every round's prompt ().

33. **The new test naming note conflicts with the listed existing tests.** [The note](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:132) says *each test file* starts with `STORY = "FORGE-READLOOP-1"` and uses `test_<n>_` names for this story. CUT and SPEC also list existing files such as [test_codex_reader.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/tests/test_codex_reader.py:23) and [test_split_ships.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/tests/test_split_ships.py:12), which identify earlier stories. Limit the note to new files and new cases, or assign the required rewrites explicitly.
   Disposition: cut: the note applies to new test files; existing ones keep their story and change only broken cases.

## Round 7 (run by hand on gpt-6-sol xhigh)

34. **Earlier finding 32 remains open on proof.** Item 5 names the default branch as the source of known traps, but SPEC owns only prompt and skill files; ROUNDS owns the code that must load the traps and lists only items 1 and 6, with no test for an older story branch after a new trap lands. Assign the runtime behavior and that case to ROUNDS’ test contract. [Plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:75), [task rows](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:109).
   Disposition: cut: item 1 (ROUNDS) now carries the default branch's traps in every round and tests an older story branch.

35. **Item 2’s post-approval gate can be bypassed by a task branch.** The plan makes the next task read the story branch. If an earlier task’s pull request changes only the Tasks table, the current pull-request check accepts it because it compares the approval hash, which excludes that table, and never checks the read hash. The next task can then pass against the unchanged story branch while inheriting the edited table from the default branch. Pin and test the pull-request or task-start check for this state. [Plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:44), [pull-request check](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:354), [task start](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/task.py:126).
   Disposition: cut: item 2 adds Forge's pull-request check to the story gate, tested with a task pull request that changes only the Tasks table.

36. **Item 8 leaves shipped one-read instructions behind.** New repositories still receive a spec README saying `forge read` gives “one cold read,” and the active Forge skill says a deferred decision needs “No second cold read.” Neither instruction is named for removal; the README is outside CUT’s Scope. Update the active instructions and test the generated repository output. [README template](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/templates/skeleton/docs/specs/README.md:5), [skill template](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/templates/skill.md:148), [CUT row](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:111).
   Disposition: cut: item 8 and CUT's Scope cover the skill's No second cold read line and the specs README, with a generated-output test.

## Round 8 (run by hand on gpt-6-sol xhigh)

37. **The post-merge task path is still unproven for this repository.** Forge [squash-merges tasks](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/merge.py:64), so the default branch does not inherit the story branch’s ancestry. After a later passing read changes the Tasks table, the [planned merge of the story branch into the next task branch](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:54) can produce add/add conflicts in the doc and read notes. Pin how task start reconciles those branches and test it after a squash merge; the [existing task test](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/tests/test_task.py:131) uses a history-preserving merge.
   Disposition: cut: item 2 has the story branch's copy of the doc and notes win any conflict when task start merges it, tested after a squash-merged first task.

38. **Unproven: item 1, retry after a failed or discarded Codex round.** [Codex records the conversation](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/codex.py:324) before [Forge rejects a failed turn or changed-file read](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:183). The next attempt could resume a conversation containing a discarded answer even though the plan says that round records nothing. Pin which conversation a retry uses and test retries after both failures.
   Disposition: cut: item 1 drops a failed or discarded round's conversation so the retry starts fresh, tested after both.

39. **Unproven: item 7, a passing but unconfirmed spec in a pull request.** [Spec save commits the draft](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/records.py:136), while read notes are currently written without a commit; [spec confirm commits them](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/records.py:165) only after changing the spec to confirmed. Item 7 gates unconfirmed specs, but does not say how a passing round’s notes reach that pull request. Pin whether a passing draft may pass the check and test its committed PR head.
   Disposition: cut: item 7 has a passing round commit the spec and its notes (GATES does the commit), tested on the pull-request head.

## Round 9 (by hand on gpt-6-sol xhigh, one kept conversation from here)

40. **GATES omits an existing test it must reconcile.** Item 2 makes later task branches merge the story branch, but [test_task.py](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/tests/test_task.py:131) asserts that their parent is `origin/main`. GATES lists only its new suite in Scope and Tests. Assign that test to GATES and update it, or state and test a legacy exception.
   Disposition: cut: GATES owns tests/test_task.py; the task branch still starts from the default branch, so its parent check stays true.

41. **Item 2 leaves failed task-start merges unhandled.** It resolves conflicts in the doc and read notes, but a full story-branch merge can conflict in other files, including the roadmap. [Task start](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/task.py:106) creates the branch and worktree first. Pin the refusal and cleanup so a conflict does not strand a task branch that blocks retry; test that path in GATES.
   Disposition: cut: task start no longer merges the story branch; it commits the story branch's copy of the doc and notes on the new task branch, so no other file can conflict.

42. **Unproven: item 1’s Claude recovery paths.** The plan names a continued Claude round, but its fresh-session and failed/discarded retry cases do not identify a backend; the [test note](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:154) names only the Codex SDK harness. ROUNDS needs tests showing that a missing Claude session gets the full fresh prompt and that failed or discarded Claude rounds retry with a new session id.
   Disposition: cut: item 1 tests Claude's missing session and both retries with a fake claude on PATH.

43. **Unproven: item 1 when the recorded reader app becomes unavailable.** [The plan](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:29) pins the reader family, but specifies a wrong-app refusal only while the other app is installed. Pin and test what `forge read` does if that recorded family is no longer installed, without silently switching readers.
   Disposition: cut: item 1 starts fresh on the reader Forge would pick now when the recorded app is gone, says so and records it, with a test.

## Round 10

44. **The task copy omits renewed approval.** After a first task is squash-merged, reapproving a changed Done-when item commits a new approval hash to the story branch’s [state file](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/approval.py:164). Item 2 copies only the doc and read notes into the next task branch, leaving the old approval at its pull-request head; the [pull-request check](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:369) then rejects the new doc. Pin how the approval state reaches that branch and test a renewed approval after a squash merge. The named Tasks-table test cannot catch this because that edit leaves the approval hash unchanged.
   Disposition: cut: item 2 copies the story's state file with the doc and notes, tested with a renewed approval after a squash merge.

45. **The new reader-switch rule changes the approved promise.** [“What changes for you”](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:7) says the same reader reads every round, while [item 1](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:35) now switches apps when the recorded reader is unavailable. State that exception in the user-facing promise.
   Disposition: cut: What changes for you now states the one-app reader and the switch.

46. **Unproven: item 2’s archive path after a reader switch.** A Codex round with findings leaves its conversation open. If Codex then becomes unavailable and a Claude round passes, the plan does not say whether Forge attempts to archive that earlier Codex conversation, prints the promised archive-failure note, or leaves it silently. Pin the outcome and test this switch-and-pass case in GATES.
   Disposition: cut: item 2 archives only the passing round's own conversation and names a left-over one in a note, tested.

## Round 11

47. **Item 2 does not distinguish the first task’s base from later tasks’.** It says the new task branch starts from the default branch, but [task start](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/task.py:128) and its [test](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/tests/test_task.py:108) start before the first merge from the story branch. That branch can also contain a [roadmap addition](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:121) that copying only the doc, notes and state would omit. Pin the first-task base and prove its files reach the pull request.
   Disposition: cut: item 2 keeps today's story-branch start before the first merge, and tests a first task carrying the roadmap entry.

48. **The legacy exception can copy a stale story doc over the default branch’s copy.** Before this change, [task start](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/task.py:128) reads the default branch after the first task merges, and the old [pull-request check](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:369) permits a Tasks-table-only edit. For an already approved story in that state, item 2’s new story-branch source can miss the newer table and commit the older one into the next task. Pin how GATES detects this legacy divergence and test it.
   Disposition: cut: item 2 limits the copy to stories whose notes have rounds; older stories keep today's task start throughout.

## Round 12

49. **Finding 47 remains open.** The disposition says the first task starts from the story branch and carries the roadmap entry, but [item 2](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:63) still says the new branch starts from the default branch and copies only the doc, notes and state. It names no first-task exception or roadmap test.
   Disposition: cut: item 2 now says the first task starts from the story branch with its roadmap entry, with a test (the earlier edit had failed to apply).

50. **Finding 48 remains open.** The disposition limits copying to stories whose notes have rounds, but [item 2](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:63) still gives task start the story-branch copy while that branch exists. Its legacy exception lasts only “until its doc changes”; it does not preserve the existing default-branch path for an older approved story whose Tasks table diverged after a merge, or name a test for that case.
   Disposition: cut: item 2 keeps today's task start throughout for old approved stories, tested with a Tasks table changed on the default branch.

## Round 13

51. **The legacy exception reopens the post-approval read gap.** [Item 2](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:59) requires a new round after any doc edit, including the Tasks table, but then says an older approved story keeps today’s task-start behavior throughout. Today’s [task start](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/task.py:126) reads the default-branch copy after the first merge and checks an approval hash that excludes the Tasks table. Pin whether the edited legacy story must first pass a new read, and test both the refusal and its eventual start from the default-branch copy.
   Disposition: cut: item 2 says old approved stories keep today's rules entirely, with no read gate after approval, tested starting from the default-branch copy without a read.

52. **Unproven: item 2’s first-task roadmap path for a promoted fix.** The roadmap entry is added on the story branch by [`story new --from-fix`](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:121), but that command turns the existing fix branch into the first task branch without copying the story doc, read notes or roadmap entry ([`_promote`](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:544)). The promised first-task test could pass for an ordinary story whose roadmap entry was already on the default branch. Pin how the promoted task’s pull-request head receives and checks the passing story artifacts, and test that path.
   Disposition: cut: item 2 has approval merge the story branch into a promoted task's branch, tested on that task's pull request.

## Round 14

53. **The promoted-task merge needs a failure path.** [Item 2](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:72) merges the story branch into an existing task branch during approval. The promoted fix may have changed the roadmap or another file also changed on the story branch, so that merge can conflict. Pin whether approval is recorded before or after a successful merge, how Forge leaves both worktrees on failure, and how the agent retries. Test a conflict in GATES; the promised successful pull-request test does not prove recovery.
   Disposition: cut: item 2 records approval first, aborts a conflicting merge leaving the task branch as it was, names the merge to resolve, and tests the conflict.

54. **Unproven: the legacy exemption at `forge next` and pull-request check.** Item 2 says older approved stories keep today’s rules entirely, but its legacy test covers only [task start](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:68). GATES also adds read gates to `forge next` and the pull-request check. Test that both preserve the exemption for an older approved story whose Tasks table changed on the default branch.
   Disposition: cut: item 2's legacy test covers forge next, the pull-request check and task start.

## Round 15

55. **The promoted-task merge can fail before a conflict exists.** [`story new --from-fix`](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:544) does not require the promoted task worktree to be clean. A local edit that the approval merge would overwrite makes Git refuse before entering a merge state, so the planned [abort-and-retry path](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:72) does not apply. Pin the refusal and recovery with approval already recorded, and test an overlapping local edit in GATES.
   Disposition: cut: item 2 covers any failed merge, including uncommitted edits in the way, leaving branch and folder as they were, with a test.



## Round 16

No findings.

## Round 17

56. **A settled older keep can become visible as unsettled again.** After a disputed keep, item 3 updates both the original finding’s disposition and the dispute to cite the human’s `Decided:` line. A continued prompt sends only the previous round’s dispositions, so the reader never receives the updated disposition of an original finding from an older round ([item 1](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:33), [item 3](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:93)). Pin how changed older dispositions reach the reader, and test a third round after a human settles a dispute.
   Disposition: cut: item 1 sends older findings whose disposition changed since, tested with a third round after a settled dispute.

57. **Continued rounds can use stale story context.** The first-round [prompt](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/templates/cold-read.md:8) supplies the confirmed spec and asks the reader to check `BRIEF.md` answers. Item 1 now sends only the story doc diff and tells the reader to reread that doc. If the linked spec or answers change between rounds, neither change appears in that diff. Pin how each continued round checks current linked context, and test a change between rounds.
   Disposition: cut: item 1 tells the reader to re-read the confirmed spec and BRIEF.md from their paths, tested with a change between rounds.

## Round 18

58. **ROUNDS has no pinned baseline for changed older dispositions.** Item 1 sends only older findings whose disposition changed since the last round, but the [notes contract](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:164) stores the previous doc text, not the dispositions last shown to the reader. Findings rounds need not commit their notes. Pin how Forge compares dispositions with what that conversation last received, and test that a settled older keep is sent while unchanged older findings are omitted.
   Disposition: cut: Notes pin doc_seen, spec_seen and notes_seen object ids stored each round; changed older dispositions compare against notes_seen; tested with unchanged ones left out.

59. **A spec path alone may point to the wrong copy.** The planned `$spec_path` identifies a file, but Forge’s [confirmed-spec lookup](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/src/forge/story.py:458) can find the current spec on a promoted task branch rather than in the story checkout. Telling the continued reader to open that path can yield an absent or stale file. Pin the selected ref or supply the current spec text, and test a spec that exists only on the promoted task branch.
   Disposition: cut: item 1 sends the confirmed spec's diff since the previous round, found as the first round finds it, instead of a path; tested with a spec only on a promoted task branch.



## Round 19

No findings.


## Round 20

60. **SPEC’s new first-round code lacks an owning test case.** The [new Note](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/plans/FORGE-READLOOP-1.md:159) makes SPEC change `story.read` to exclude the next-round prompt and load traps from the default branch, but SPEC’s Done-when coverage and test promise do not name either runtime case; item 1’s older-branch trap test remains with ROUNDS. The existing [story test](/Users/ravikiranvemula/Workdir/symphony-forge-story-FORGE-READLOOP-1/tests/test_story.py:219) only checks that the doc reaches the reader. Give SPEC a `forge read` boundary test that rejects leaked next-round text and proves an older story branch receives the default branch’s traps, so SPEC can pass before ROUNDS.
   Disposition: cut: the SPEC note now names a forge read test for both cases in tests/test_readloop_prompt.py.


## Round 21

No findings.
