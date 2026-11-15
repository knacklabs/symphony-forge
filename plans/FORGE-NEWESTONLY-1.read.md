---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-15T15:51:01.025074+00:00
seconds: 704.987
read_hash: 4a2f5fcbce22f7cab40315c6b7bc209ae6ef3d84
round: 2
passed: no
doc_seen: 4a2f5fcbce22f7cab40315c6b7bc209ae6ef3d84
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: ee8b8bc2d2c0346d669a835bd5622d4a02a5555f
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1dfc9-6fd4-72e0-98be-17f45f7dc257
session:
loop_choice: more
loop_reason: The owner chose: cut the tests now, refusal later. This story removes the earlier-adopted test cases, the old-release test data and the readers of old record formats and rewrites the test rule; the refusal on an older pin, the one-step upgrade and the migrate notice move to a second story
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

1. Blocking: Not done: A host hook can still run an older release through uv.
   Raise: Not done  
   Case: normal use - Codex starts a hook with a limited PATH, and uvx is available but Forge is not on that PATH.  
   [sync.py:75](/src/forge/sync.py:75) generates a launcher that runs the repo’s pinned release through uvx. The plan deletes its test but leaves that launcher in place.  
   Gain 4, Work 2, Harm 3
    Disposition: cut: the launcher's uvx branch goes in REFUSE, and test_2's launcher case checks it.

2. Blocking: Not done: A merge conflict makes the worker’s recovery command repeat itself.
   Raise: Not done  
   Case: normal use - An open fix and the merged upgrade both changed the same guide.  
   [worker.py:149](/src/forge/worker.py:149) aborts the conflicting merge and prepares instructions for the worker. The planned pin check then sees the old pin and says to run `forge work` again, so the worker never receives those instructions. The planned branch test covers a clean merge.  
   Gain 4, Work 2, Harm 3
    Disposition: cut: inside an older branch's folder the line now says git merge origin/<default>, resolve conflicts and commit, then rerun; from the main checkout forge work keeps handing the conflict to the worker as today (table row branch_older).

3. Blocking: Functional: A stale local default branch is told to upgrade an already-upgraded repo.
   Raise: Functional  
   Case: normal use - The human merges the upgrade on GitHub, but the local default branch has not yet been pulled.  
   The plan’s `older` response says `forge upgrade`; [upgrade.py:97](/src/forge/upgrade.py:97) fetches the default branch and refuses because it already pins that release. The proposed next step therefore cannot resolve the mismatch.  
   Gain 4, Work 2, Harm 3
    Disposition: cut: the stop path fetches the default branch first, and a behind default checkout gets git pull (table row behind).

4. Blocking: Not done: The suggested upgrade can skip the installed release.
   Raise: Not done  
   Case: normal use - A repo pins 1.2.40, the laptop has 1.2.41, and 1.2.42 has just been published.  
   The planned refusal says `forge upgrade`, but [upgrade.py:88](/src/forge/upgrade.py:88) selects GitHub’s newest release when no release is named. The hand-off installs 1.2.42 and then refuses the 1.2.40 pin, instead of making the promised one-step upgrade to 1.2.41.  
   Gain 4, Work 2, Harm 3
    Disposition: cut: every next step names the release, forge upgrade v<installed>, so GitHub's newest is never used by the flow.

5. Blocking: Not done: The release test does not ensure the previous-release value moves.
   Raise: Not done  
   Case: normal use - A release fix updates the current version and its existing version assertions but forgets the previous-release value.  
   [test_release_version.py:16](/tests/test_release_version.py:16) uses fixed expected versions. The planned assertion of `PREVIOUS == "1.2.39"` also stays green if both that value and its assertion are forgotten, leaving the next release unable to upgrade the immediately preceding one.  
   Gain 4, Work 2, Harm 3
    Disposition: cut: the release before is derived (last number minus one); only an x.y.0 release sets __previous__, and the release test fails offline when it is missing or left over.

6. Blocking: Not done: The planned exceptions contradict the command refusal.
   Raise: Not done  
   Case: normal use - An upgrade waits for merge and someone starts a fix from the default branch, or runs `forge lanes` in the older checkout.  
   The plan retains the waiting-upgrade return in [repo.py:993](/src/forge/repo.py:993) and explicitly expects `forge lanes` to succeed. Done-when 1 says every command except upgrade stops.  
   Gain 4, Work 1, Harm 3
    Disposition: cut: the exceptions are listed in the owner's text and in Done-when 1; the waiting-upgrade case is narrowed to the upgrade fix's own commands.

7. Blocking: Not done: An old work branch is not told to merge the waiting upgrade.
   Raise: Not done  
   Case: normal use - A person runs `forge close` on an open fix while the upgrade pull request waits for merge.  
   For that branch, the plan selects `older`, whose next step is `forge upgrade`; [upgrade.py:78](/src/forge/upgrade.py:78) refuses that command outside the default branch. The promised instruction to merge the waiting upgrade is absent.  
   Gain 3, Work 1, Harm 3
    Disposition: cut: while an upgrade fix waits, every other command prints the waiting line with forge close <fix> (table row waiting).

8. Blocking: Test: Sync can change the host plugin before the pin refusal.
   Raise: Test  
   Case: normal use - A person runs `forge sync` in a repo with an older pin.  
   [cli.py:143](/src/forge/cli.py:143) updates the user-scoped plugin before checking the pin; [sync.py:761](/src/forge/sync.py:761) can also print a warning. The proposed refusal test does not run sync, so it can pass while this command changes the plugin and prints more than the refusal.  
   Gain 3, Work 2, Harm 3
    Disposition: cut: the check now runs before install_mod for sync, and test_2 runs forge sync and checks no claude plugin call.

9. Blocking: Functional: A newer repo pin makes doctor’s repair unreachable.
   Raise: Functional  
   Case: normal use - A developer opens a repo after a teammate upgraded its pin and runs `forge doctor --fix` on a laptop with the preceding release.  
   The widened check refuses doctor before [doctor.py:334](/src/forge/doctor.py:334) can install the newer pinned release, although the plan says that repair stays.  
   Adds work: keep the existing newer-pin repair available; F 2 x H 2 = 4; 2 x C = 2.  
   Gain 3, Work 2, Harm 3
    Disposition: cut: doctor stops like every command and its pin repair goes; the stop line gives the same install command, and the owner's text says so.

10. Blocking: Plan gap: TESTS-4 removes fixtures before their dependent tests are removed.
    Raise: Plan gap  
    Case: normal use - CI runs the suite for TESTS-4 before REFUSE and CODE.  
    [test_codex_trusts_earlier_forge_hooks.py:21](/tests/test_codex_trusts_earlier_forge_hooks.py:21) still reads the fixture that TESTS-4 deletes; its deletion is assigned to CODE. The retained `True` cases in [test_worker_and_reader_chats_survive_rounds.py:146](/tests/test_worker_and_reader_chats_survive_rounds.py:146) also use that fixture and do not match the deletion regex.  
    Gain 4, Work 2, Harm 2
    Disposition: cut: the folders move to a last FIXTURES part after CODE, and the bare-True earlier-adopted cases are counted and assigned to the TESTS parts.

11. Blocking: Plan gap: REFUSE deletes modules that retained tests import.
    Raise: Plan gap  
    Case: normal use - CI collects the suite after REFUSE deletes the named old-pin test files.  
    [test_tasks_inherit_the_upgraded_forge_release.py:13](/tests/test_tasks_inherit_the_upgraded_forge_release.py:13) imports helpers from one deleted file and retains new-repo cases. Other retained tests import from the other deleted file, so collection fails unless those shared helpers are accounted for.  
    Gain 4, Work 2, Harm 2
    Disposition: cut: a part moves each helper a kept test imports before it deletes the file; the known helpers are named.

12. Blocking: Gate: The deletion regex catches a new live-app adoption case.
    Raise: Gate  
    Case: normal use - Forge is first installed into an existing app.  
    [test_board_running_review.py:70](/tests/test_board_running_review.py:70) calls current `forge init` for its `existing` case and checks the board plugin. That ID matches the plan’s regex and is absent from its listed exclusions: deleting it weakens new-repo coverage, while keeping it makes the stated zero-match proof fail.  
    Gain 3, Work 1, Harm 3
    Disposition: cut: the existing and upgraded ids were read one by one; the live-app and not-a-release ids are excluded by name.

13. Blocking: Plan gap: The migrate notice contradicts a retained test.
    Raise: Plan gap  
    Case: normal use - CI runs the existing full migration test after REFUSE adds the notice.  
    [test_migrate.py:174](/tests/test_migrate.py:174) requires the real run’s output to start with the migration report. The plan makes the notice its first line but does not assign this test’s update.  
    Gain 4, Work 1, Harm 4
    Disposition: cut: the notice is the last line of stderr, so test_migrate.py:174 stays green unchanged.

14. Blocking: Gate: P1 — `Design: none` covers a changed flow.
    Raise: Gate  
    Case: normal use - A team upgrades Forge while a story is in progress.  
    The plan changes when work stops, how the upgrade is merged, and how workers resume; [worker.py:141](/src/forge/worker.py:141) is part of that existing flow. The reason given for no design only says there is no screen.  
    Gain 4, Work 2, Harm 2
    Disposition: cut: the owner's text now has a six-step list of what a team sees during an upgrade, and Design: none gives that reason.

15. Blocking: Split: TESTS-4 → smaller fixture and test-removal parts.
    Raise: Plan gap  
    Case: normal use - A builder reviews and validates the TESTS-4 pull request.  
    The task includes about 10,200 lines of fixture deletion as well as 267 cases; [story.py in the fixture](/tests/fixtures/forge-v1.2.2/src/forge/story.py:1) alone has 761 lines. This is well beyond the requested roughly 400 changed-line task size.  
    Gain 4, Work 2, Harm 2
    Disposition: cut: the old-release folders are a pure-deletion FIXTURES part of their own; TESTS-4 removes only cases.

## Round 2

16. Blocking: Gate: The revised plan still has `Design: none` for a changed flow.  
    Raise: Gate  
    Case: normal use - A team upgrades while a story is in progress.  
    The six-step description documents the changed flow, but [the plan](/plans/FORGE-NEWESTONLY-1.md:26) still says `Design: none`. The flow includes the worker’s merge in [worker.py:141](/src/forge/worker.py:141). The stated gate treats this as P1, so finding 14 is not closed.  
    Gain 4, Work 2, Harm 2
    Disposition: cut: the changed upgrade flow left this story (owner, 15 Nov 2026: "Cut the tests now, refusal later"); nothing a person sees changes except Forge's own test rule, and Design: none now says so.

17. Blocking: Not done: Existing branches keep the hook that runs the pin through uv.  
    Raise: Not done  
    Case: normal use - After the upgrade merges, Codex opens an older work branch with uvx available but Forge absent from its hook PATH.  
    The tracked [hooks.sh:7](/.forge/hooks.sh:7) still runs that branch’s pinned release through uvx. Changing the launcher generated by sync updates the upgrade branch; an open branch retains its existing launcher until it merges the default branch. The proposed test checks only a newly synced launcher, so finding 1 is not closed for existing branches.  
    Gain 4, Work 2, Harm 3
    Disposition: cut: the hooks' uvx fallback and every launcher change left this story; the hooks stay as they are, and the second story holds this case.

18. Advisory: Not done: The upgrade still runs the repo’s pin through uv.  
    Raise: Not done  
    Case: normal use - A repo upgrades from the preceding release to the installed release.  
    The plan keeps `run_release` for upgrade and keeps the existing upgrade steps. [upgrade.py:194](/src/forge/upgrade.py:194) sets the fix’s pin, then [upgrade.py:222](/src/forge/upgrade.py:222) runs that pinned release through uv for sync. This contradicts Done-when items 1 and 5.  
    Gain 4, Work 2, Harm 3
    Disposition: cut: the uv runner and the upgrade stay as they are; the refusal and one-step upgrade left this story.

19. Advisory: Not done: A teammate on the published older Forge does not get the new refusal.  
    Raise: Not done  
    Case: normal use - A teammate has v1.2.40 installed and pulls a repo upgraded to v1.2.41.  
    The new check cannot change the already-published v1.2.40 executable. Its [pin check](/src/forge/repo.py:1005) runs the newer pin through uv for a state-changing command, instead of stopping with the promised install step.  
    Gain 4, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)

20. Advisory: Not done: The upgrade checkout bypasses the waiting stop.  
    Raise: Not done  
    Case: normal use - An agent starts another fix from the upgrade fix’s folder while that upgrade waits for merge.  
    The upgrade folder pins the installed release, so the plan’s [first matching-pin row](/plans/FORGE-NEWESTONLY-1.md:117) returns before its waiting check. [fix start](/src/forge/task.py:699) can then start work stacked on that upgrade, although the plan says other work stops.  
    Gain 3, Work 1, Harm 3
    Disposition: cut: the waiting-upgrade stop left this story with the refusal.

21. Advisory: Plan gap: `forge work` both merges before the check and must refuse before merging.  
    Raise: Plan gap  
    Case: normal use - A person runs `forge work` inside an older fix folder after the upgrade merges cleanly.  
    The plan keeps [worker.prepare](/src/forge/worker.py:141) before the pin check, but its new test expects `forge work` to print the older-branch refusal. A clean merge updates the pin before that check, so the command proceeds instead.  
    Gain 3, Work 2, Harm 3
    Disposition: cut: the forge work refusal left this story with the refusal.

22. Advisory: Plan gap: The fake release cannot use its planned previous-version override.  
    Raise: Plan gap  
    [test_upgrade_command.py:27](/tests/test_upgrade_command.py:27) uses v9.9.9. The plan sets its `__previous__` to the repo’s pin, but its new rule reads that override only for a release ending in zero; v9.9.9 instead derives v9.9.8. The existing successful upgrade tests therefore refuse under the specified fake.  
    Gain 4, Work 2, Harm 2
    Disposition: cut: the previous-release value and the fake release's override left this story.

23. Advisory: Functional: The release notice can recommend skipping a required upgrade.  
    Raise: Functional  
    Case: normal use - A repo and laptop are on v1.2.41 when v1.2.43 is published.  
    The unchanged [release notice](/src/forge/upgrade.py:267) recommends upgrading directly to v1.2.43. The planned hand-off installs that release and then refuses the repo’s v1.2.41 pin because v1.2.42 must come first.  
    Gain 3, Work 2, Harm 3
    Disposition: cut: the one-step upgrade left this story; the release notice stays as it is.

24. Advisory: Plan gap: A migrate refusal prints after the supposed final notice.  
    Raise: Plan gap  
    [migrate.py:174](/src/forge/migrate.py:174) can raise a refusal. The planned `finally` prints the notice while unwinding; [cli.py:177](/src/forge/cli.py:177) then prints the refusal, so the notice is not the last line as the amended plan promises.  
    Gain 2, Work 1, Harm 4
    Disposition: cut: the forge migrate notice left this story; migrate stays as it is.

25. Advisory: Split: FIXTURES → smaller fixture-deletion parts.  
    Raise: Plan gap  
    The new FIXTURES part still removes about 10,200 lines; [story.py](/tests/fixtures/forge-v1.2.2/src/forge/story.py:1) alone has 761. Moving the deletion out of TESTS-4 leaves a part above the requested roughly 400-line limit.  
    Gain 4, Work 2, Harm 2
    Disposition: keep - FIXTURES is a pure deletion of test data with no code or test logic; the size rule counts no lines under tests/, and the one git grep for readers is its whole review, which five parts would only repeat.
