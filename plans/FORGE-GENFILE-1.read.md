---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-11T08:21:14.019341+00:00
seconds: 697.345
read_hash: d07db25a99645f4ad63e0e6d76544d8b5fbbc36b
round: 1
passed: no
doc_seen: d07db25a99645f4ad63e0e6d76544d8b5fbbc36b
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1c9a7-c377-7881-953a-6d7117ffcf1a
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

1. Blocking: Not done: The new rule conflicts with shipped instructions for generated files.  
   Raise: Not done  
   Case: normal use - a client changes an API or database schema.  
   The [plan](/plans/FORGE-GENFILE-1.md:59) says files written by a script are made at build time and not committed. The shipped [database guide](/src/forge/templates/conventions/database.md:69) requires committing generated migration SQL, and the [Python guide](/src/forge/templates/conventions/python.md:182) requires committing both generated API files. Both guides remain outside the task’s Scope.  
   Gain 4, Work 2, Harm 4
   Disposition: cut - the planner rule now says to keep a file a script can make at build time out of git and Scope, and to give a file committed on purpose (as the API-types and migration conventions do) to one part the others wait for, or chain them; the note's advice says the same (Settled 3, 5).

2. Blocking: Not done: A newly published story can be missed.  
   Raise: Not done  
   Case: normal use - a teammate publishes a story after this computer’s last fetch.  
   The [plan](/plans/FORGE-GENFILE-1.md:30) says published stories count, but [`_stories`](/src/forge/nextstep.py:598) reads local remote-tracking branches and [`forge read`](/src/forge/story.py:163) does not fetch them. Two parts in the current plan and a third in the newly published story therefore produce no note.  
   Gain 4, Work 2, Harm 3
   Disposition: cut - the note counts only the plan being read; other stories get one guide sentence and a possible later fix in Notes (Settled 2).

3. Blocking: Not done: The guide makes the advice a condition of approval.  
   Raise: Not done  
   Case: normal use - a read finds three parts sharing a file.  
   The [plan](/plans/FORGE-GENFILE-1.md:9) says the note does not stop approval, but its [coordinator instruction](/plans/FORGE-GENFILE-1.md:59) says to follow the advice **before** asking for approval. That requires a fix or a plan change even when the owner would accept the shared file.  
   Gain 4, Work 1, Harm 2
   Disposition: cut - the guide now says the note is advice and the agent does not hold the approval for it; a test case approves a plan that has the note (Settled 5, Done-when detail 1).

4. Blocking: Not done: An unrelated story’s conflict can stop the read.  
   Raise: Plan gap  
   Case: normal use - two teammates make conflicting edits to another published story.  
   The prescribed [`_stories` call](/src/forge/nextstep.py:605) invokes [`_plan`](/src/forge/story.py:613), which refuses on conflicting local and published edits. The plan gives no way for this advisory scan to continue; at its prescribed location, the read may already have been recorded before that refusal.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - the read no longer reads other stories, so another story's plan cannot stop it (Settled 2).

5. Blocking: Plan gap: The task’s Scope is not parsed as the listed paths.  
   Raise: Plan gap  
   Case: normal use - another task owns the Codex guide while this task changes both guides.  
   The [Scope cell](/plans/FORGE-GENFILE-1.md:81) joins the two guide paths with “and” and adds descriptions to paths. [`cell_list`](/src/forge/task.py:84) splits only on commas, so the Codex guide is not a separate scope entry. The [review matcher](/src/forge/review.py:313) also treats the annotated paths as outside Scope.  
   Gain 3, Work 1, Harm 3
   Disposition: cut - the Scope cell is now plain comma-separated paths with notes moved below the table, and the note reads entries with story._cell_paths, the parser the overlap check uses (Settled 1).

6. Blocking: Not done: A folder scope can produce a false shared-file note.  
   Raise: Not done  
   Case: normal use - one part scopes `src/api/**`, while two other parts scope different files beneath it.  
   [`_overlap`](/src/forge/task.py:631) matches the folder to each file, although the two files do not overlap each other. The [specified note](/plans/FORGE-GENFILE-1.md:54) would say all three list the same entry and run one after another, even though the two file-specific parts can run together.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - only an exact file path listed by three or more parts counts; a folder or glob entry never counts, and a test case proves a folder plus two files gives no note (Settled 1, Done-when detail 1).

7. Blocking: Functional: The plan misstates when shared-file parts can start.  
   Raise: Functional  
   Case: normal use - stacking is enabled, as it is by default, and a shared-file part has been reviewed.  
   [`can_start`](/src/forge/task.py:518) permits a part to start on its reviewed base despite their shared Scope. The [existing command test](/tests/test_stack_start.py:198) starts such a pair before the base merges. The plan and note nevertheless say Forge never starts two parts that change the same file.  
   Gain 3, Work 1, Harm 3
   Disposition: cut - the plan now states from can_start and stack_base that a part sharing a file starts on top of one reviewed part when stacking is on, otherwise waits for the merge, so the parts are built one after another (evidence, What changes for you).

8. Blocking: Scale: Each read scans completed story history.  
   Raise: Scale  
   Case: normal use - a repository has 88 stories, including 81 completed ones.  
   The prescribed [`_stories` call](/src/forge/nextstep.py:581) checks completion for every story. In two read-only measurements in this checkout, that portion alone took 9.4 and 13.9 seconds; the second issued 430 Git history commands. The [plan](/plans/FORGE-GENFILE-1.md:57) only reports a delay over two seconds.  
   Adds work: reduce repeated completed-story history reads; F 2 x H 2 = 4; 2 x C = 4.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - no scan of other stories during the read; the note uses only the plan's own parsed table (Settled 2).

9. Blocking: Unproven: Item 1 for native plan reads.  
   Raise: Test  
   Case: normal use - the coordinating app runs its own reader and receives the result through handback.  
   The [planned test](/plans/FORGE-GENFILE-1.md:63) uses the stub reader. Native reads instead return a [JSON instruction](/src/forge/native.py:122) and finish on handback. The planned assertions can pass if the shared-file note is missing from handback or corrupts that JSON.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - the note prints in story.read_result, so it shows in forge handback's output for a session read and never in forge read's JSON; a test case parses that JSON and checks the handback output (Settled 3, Done-when detail 1).

10. Blocking: Unproven: Item 3’s existing-file preservation check.  
    Raise: Test  
    Case: normal use - an earlier-adopted repository has an approved plan and application files.  
    The specified [earlier-adopted setup](/tests/test_scope_overlap_explains_waits.py:19) copies a fixture with no plans, runs sync, and commits before returning. The proposed `git diff --quiet -- plans/` can therefore pass without checking an existing approved plan, and it does not check application files.  
    Gain 3, Work 1, Harm 3
    Disposition: cut - Done-when 3 no longer claims that a client's own files stay unchanged; the earlier-adopted case proves the rule after sync and the note from the new release (Done-when detail 3).
