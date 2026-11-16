---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-15T16:29:49.054547+00:00
seconds: 465.246
read_hash: 0bc2f4e537c568d94f3aaea81575fe7ba6265f4c
round: 4
passed: no
doc_seen: 52695986bc6a796b9478ed445f11a0cdae876769
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 2f5bdb99ae6170f4526ab990bf81c539f4b671bc
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1dfc9-6fd4-72e0-98be-17f45f7dc257
session:
loop_choice: accept
loop_reason: The owner accepts the read: the three round-4 notes are handed to the builders in the plan's builders' part; the release hold is dropped for this story; the title is 'Forge tests each rule on a new repo only'
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

## Round 3

26. Blocking: Data loss: An old work branch can lose its saved chat binding after the repo reaches v1.2.40.
    Raise: Data loss  
    Case: normal use - One teammate upgrades the default branch while another has an unfinished branch and a local Claude chat started on v1.2.2.  
    The [v1.2.2 worker](/tests/fixtures/forge-v1.2.2/src/forge/worker.py:115) did not record which worker ran. The first teammate’s upgrade cannot move a chat stored on the second laptop. When that branch later runs under the new release, the planned removal of the fallback makes [worker.py](/src/forge/worker.py:253) clear the saved session binding and start a replacement. The release hold checks the repo pin, not those local branches; the old binding does not stay on disk as Risks says.  
    Gain 4, Work 2, Harm 4
    Disposition: cut: CODE left this story (owner, 15 Nov 2026: "Tests only in this story"); worker.py and the old chat fallback do not change, so no chat binding can be lost.

27. Advisory: Gate: Removing hook trust changes the Codex worker flow.
    Raise: Gate  
    Case: normal use - A repo on v1.2.2 starts a Codex worker while its upgrade waits to merge and Codex has not trusted its old hook.  
    [CODE](/plans/FORGE-NEWESTONLY-1.md:78) removes recognition of that hook. [codex_turn.py](/src/forge/codex_turn.py:191) then refuses the turn and requires a person to review the hook. This is a changed flow even though the amended plan says `Design: none`; the refusal also contradicts Risks’ claim that no command fails with an error.  
    Gain 4, Work 2, Harm 2
    Disposition: cut: CODE left this story; codex.EARLIER_COMMANDS stays, so the Codex worker flow does not change.

28. Advisory: Functional: Adopting an existing app can put a self-reference in its instructions.
    Raise: Functional  
    Case: normal use - An existing app has a `CLAUDE.md` that imports its `AGENTS.md`.  
    The plan deletes the entire old-line list, including `@AGENTS.md`. [sync.py](/src/forge/sync.py:189) currently excludes that line when moving instructions into `AGENTS.md`; without it, the file gains a reference to itself. The existing [sync test](/tests/test_sync_moves_claude_md_into_agents_md.py:19) checks this current-client behavior.  
    Gain 3, Work 2, Harm 3
    Disposition: cut: CODE left this story; sync.EARLIER stays, with its @AGENTS.md line.

29. Advisory: Functional: Installing the new release can change the status shown for an unupgraded repo.
    Raise: Functional  
    Case: normal use - A laptop has another repo pinned before v1.2.11 with a ready pull request.  
    Read-only commands skip the pin check in [cli.py](/src/forge/cli.py:147), so the installed release supplies the board even in that older repo. Removing the old ready-record reader in [nextstep.py](/src/forge/nextstep.py:886) can show its ready pull request as waiting for checks. The plan describes this effect only after an upgrade.  
    Gain 3, Work 2, Harm 3
    Disposition: cut: CODE left this story; the old ready-record reader in nextstep.py stays.

30. Advisory: Unproven: item 1: The kept upgrade test does not use the initialized repo the plan describes.
    Raise: Test  
    The designated [upgrade test](/tests/test_upgrade_to_installed_release.py:25) uses a fixture that writes a small `forge.toml` by hand and runs sync; it never runs `forge init`. The fixture in [test_close.py](/tests/test_close.py:264) omits settings a real init writes, so the designated test can pass while an upgrade loses one of those settings.  
    Gain 3, Work 2, Harm 3
    Disposition: cut: the plan now describes the kept upgrade test as it is (its repo comes from the test's own setup, a hand-written forge.toml and forge sync, not forge init) and says what it does not prove.

31. Advisory: Disputed keep 25: The retained fixtures make the stated deletion proof fail.
    Raise: Plan gap  
    The plan keeps both fixture folders and requires a search under `tests` to find no old-folder names. The retained [README](/tests/fixtures/before-test-runner/README.md:3) and [picker replay data](/tests/fixtures/release-v1.2.6-picker/changes.json:71) contain those names, so the proof remains red after the five scheduled folders are deleted.  
    Gain 4, Work 1, Harm 2
    Disposition: cut: no proof greps for folder names now; the proof uses collected test ids and whether each folder exists.

32. Advisory: Test: An earlier-adopted lane case is invisible to the deletion proof.
    Raise: Test  
    [test_lanes_tests.py](/tests/test_lanes_tests.py:109) names the case `[upgrade]`, which matches none of the plan’s three selection rules. Its [helper](/tests/test_lanes_upgrade.py:17) copies the v1.2.2 adopted-client fixture. The collected-ID proof can therefore pass while this earlier-adopted case remains.  
    Gain 3, Work 1, Harm 2
   Disposition: keep - below the bar (follow-up)

33. Advisory: Plan gap: CODE leaves a new-client test expecting the deleted guide text.
    Raise: Plan gap  
    CODE removes the chat-migration paragraph, but the retained `new-init` case in [test_worker_and_reader_chats_survive_rounds.py](/tests/test_worker_and_reader_chats_survive_rounds.py:359) asserts that paragraph is present. It does not feed a deleted reader, so the plan’s instruction to delete tests that do so does not account for this failure.  
    Gain 4, Work 1, Harm 4 (floor: migration)
    Disposition: cut: CODE left this story; the guide paragraph and its test stay.

34. Advisory: Test: Deleting an old-chat test also removes current-client sync coverage.
    Raise: Test  
    The `new-client` cases in [test_sync_not_blocked_by_other_runs.py](/tests/test_sync_not_blocked_by_other_runs.py:24) check that sync writes its files while another item’s worker or land command holds a lock. They also assert old-chat migration behavior that CODE removes. Deleting the whole failing test would leave that current sync rule without this command-level proof.  
    Gain 3, Work 2, Harm 4 (floor: migration)
    Disposition: cut: CODE left this story; test_sync_not_blocked_by_other_runs.py stays whole.

35. Advisory: Not done: The stated model cost conflicts with the planned re-review.
    Raise: Not done  
    The plan says model cost does not change, but also says an item reviewed before v1.2.5 is reviewed again. For an ordinary code change, [close.py](/src/forge/close.py:354) runs a model review when the previous review is no longer reusable, adding a model call in that named case.  
    Gain 2, Work 1, Harm 2
   Disposition: keep - below the bar (live with)

## Round 4

36. Advisory: Plan gap: The deletion proof rejects a test the plan keeps.
    Raise: Plan gap  
    The proof requires rule 1 to match no collected case beyond the exceptions named in rule 2. The retained [old-hook test](/tests/test_codex_trusts_earlier_forge_hooks.py:36) has a `[v1.2.2]` case that matches rule 1 and is absent from those exceptions.  
    Gain 4, Work 1, Harm 2
    Disposition: keep - handed to the builders: the plan's builders' part names this case as an exception (rule from round 4, note 36), as the owner accepted on 16 Nov 2026.

37. Advisory: Plan gap: The keep rule conflicts with the scheduled fixture deletion.
    Raise: Plan gap  
    The plan says to keep a selected case when it reaches a listed old-release path, including `codex.preserve_chats`. Every successful [sync](/src/forge/sync.py:707) calls that function, including the [previous-release fixture case](/tests/test_close_refuses_binary_test_fixtures.py:43) that TESTS-1 explicitly deletes.  
    Gain 4, Work 1, Harm 2
    Disposition: keep - handed to the builders: the plan's builders' part says a case is kept only when older-release behaviour is the subject of its assertions (rule from round 4, note 37), as the owner accepted on 16 Nov 2026.

38. Advisory: Disputed keep 32: Rule 4 misses cases that import an old-repo helper.
    Raise: Test  
    [test_fast_test_ignores_own_package_version.py](/tests/test_fast_test_ignores_own_package_version.py:92) checks the same rule on a new client and an earlier-adopted client. The latter has no parameter ID for rules 1–3, and its file does not name an old fixture folder for rule 4: it imports a helper that [copies the fixture](/tests/test_upgrade_command.py:499). The proof can pass with that second run still present.  
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)
