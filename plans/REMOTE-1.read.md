---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-17T13:33:31.948771+00:00
seconds: 839.897
read_hash: 312d2115211fba900caea5b773005b2a874239d3
round: 4
passed: no
doc_seen: 3dc285e04fafe845247aa1f35b6e55703cd8e691
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 11195c7c18264cee6f18f0135e3e0ceaa3155b4a
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1e964-e202-7e63-964c-f3f99effee22
session:
loop_choice: accept
loop_reason: Owner accepted read round 4: fixes for 32, 34 and 35 put in the builders' section; 33 kept as a known issue; 36 and 37 advisory follow-ups
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

1. Blocking: Data loss: finishing a round deletes uncommitted work.
   Raise: Data loss  
   Case: normal use - A worker finishes with changes it could not commit, and the commit reminder also leaves them uncommitted. [The plan](/plans/REMOTE-1.md:115) removes the remote folder and only prints their names. Today, [worker.py](/src/forge/worker.py:432) leaves those files available after warning.  
   Adds work: preserve uncommitted changes after a normally ended round; F 2 x H 2 = 4; 2 x C = 4.  
   Gain 3, Work 3, Harm 4
   Disposition: cut - finish no longer deletes a run folder with uncommitted changes: it keeps it and the warning names it, and the item's next round refuses until the developer commits or deletes them there (Done-when details 2 and 4; What changes for you says so).

2. Blocking: Data loss: turning the machine off can delete a new commit.
   Raise: Data loss  
   Case: normal use - A remote worker is still running when the developer turns the feature off. [The plan](/plans/REMOTE-1.md:135) fetches branches before stopping workers. A commit made after the fetch is absent from the laptop when the remote folder is deleted. The existing [stop command](/src/forge/machine.py:623) confirms processes have ended; the planned off test does not cover a running worker.  
   Gain 5, Work 2, Harm 4
   Disposition: cut - turn-off now reads first and refuses, deleting nothing, while any driver still runs, while a run folder has uncommitted changes, or while a branch holds commits not in this clone; the fetch-then-delete step is gone (detail 5, test_5 covers each refusal).

3. Blocking: Data loss: cleanup can stop an unrelated process.
   Raise: Data loss  
   Case: normal use - An item remains stopped while the Linux machine runs other jobs, and the operating system reuses the old process number. [The plan](/plans/REMOTE-1.md:132) stops the group named by the saved number without checking its identity. [Codex’s existing process check](/src/forge/codex.py:857) also records start time because numbers can be reused.  
   Adds work: verify the remote process identity before stopping it; F 1 x H 2 = 2; 2 x C = 4.  
   Gain 2, Work 2, Harm 4
   Disposition: cut - Forge no longer stops any process on the machine: the .pid file and every kill step are deleted; a still-running round is found by its unique driver file path (pgrep -f) and makes the next round or turn-off refuse instead.

4. Blocking: Security: a later trust change can leave a worker running without Forge’s checks.
   Raise: Security  
   Case: normal use - A developer removes or changes the machine’s Codex trust entry after setup. [The plan](/plans/REMOTE-1.md:113) relies on the earlier setup check. [The current driver](/src/forge/codex_turn.py:187) says Codex skips project hooks when it does not trust them, while [the current runner](/src/forge/codex.py:564) checks trust on every turn.  
   Adds work: check the machine’s trust before a remote turn; F 1 x H 2 = 2; 2 x C = 2.  
   Gain 3, Work 2, Harm 4
   Disposition: cut - choose reads the machine's Codex settings in its existing ssh call and sends the round to the laptop with the reason `Codex there no longer trusts <clone>; run forge lanes --box setup` when the trust entry is gone.

5. Blocking: Security: the planned test can pass while the remote commit hook never runs.
   Raise: Security  
   Case: normal use - Setup writes the hook with ordinary non-executable file permissions. [The plan](/plans/REMOTE-1.md:104) requires the file and tests that it exists, but Git ignores a non-executable hook. [The existing installer](/src/forge/sync.py:694) sets executable permissions.  
   Adds work: verify that the remote commit hook runs; F 2 x H 2 = 4; 2 x C = 2.  
   Gain 3, Work 2, Harm 4
   Disposition: cut - setup makes the pre-commit file executable (chmod 755, as sync.install_shims does), and test_1 proves it runs: a commit on a branch Forge did not start, in a worktree of the clone, is refused.

6. Blocking: Not done: the first trust refusal loses the folder needed for setup to finish.
   Raise: Not done  
   Case: normal use - On first setup, the developer follows the printed trust instructions and runs setup again. [The plan](/plans/REMOTE-1.md:104) creates a randomly named folder before checking trust, but saves its record only after trust passes. It says a missing record creates a new folder, so the retry asks for trust of a different path. [The current trust check](/src/forge/doctor.py:44) requires the exact path.  
   Gain 5, Work 2, Harm 3
   Disposition: cut - the clone folder name is now fixed per clone (main checkout name plus the first 6 hex digits of the SHA-256 of its absolute path), so a setup retried after the trust refusal finds the same path; test_1 adds the trust lines for the printed path and the next setup passes.

7. Blocking: Not done: setup accepts a machine that cannot create Git commits.
   Raise: Not done  
   Case: normal use - A new Linux user has Git installed but no author name or email configured. [Setup](/plans/REMOTE-1.md:97) does not check that prerequisite, so the remote worker cannot commit. The planned stand-in inherits the laptop environment, including the test Git configuration set by [the repo fixture](/tests/conftest.py:547), so its commit can pass.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - every setup sets the clone's user.name and user.email to the laptop's (refusing when the laptop has none); the test machine drops GIT_CONFIG_GLOBAL, GIT_CONFIG_NOSYSTEM and the GIT_AUTHOR/COMMITTER values, and test_2 checks the commit's author.

8. Blocking: Not done: saved commits are skipped when the feature is turned off.
   Raise: Not done  
   Case: normal use - A cut-off round leaves commits on the machine, then the developer turns the feature off. [The off step](/plans/REMOTE-1.md:135) fetches them into separate Git references, but [the recovery choice](/plans/REMOTE-1.md:110) returns immediately when the setting is off. The next round therefore starts from the old branch. Recovery is also only called for non-native Codex rounds.  
   Gain 4, Work 2, Harm 3
   Disposition: cut - the bring-back now runs at the start of every forge work whose item record names a host, whatever the worker, route or boxes setting; turn-off no longer fetches into separate refs but refuses while commits have not come back, naming forge work <item> as the next step.

9. Blocking: Not done: changing the local machine name can prevent turn-off.
   Raise: Not done  
   Case: normal use - A developer changes or removes their local host setting before cleaning up the former machine. [The plan](/plans/REMOTE-1.md:88) treats its saved record as absent when the names differ, so [turn-off](/plans/REMOTE-1.md:87) reports nothing to delete and does not retrieve its commits. The local settings file is shared across worktrees, as [repo.py](/src/forge/repo.py:700) shows.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - bring-back and turn-off use the record's own host; only choose compares it with forge.local.toml; setup with another host named refuses until the old one is turned off; test_5 turns off after removing the host from forge.local.toml.

10. Blocking: Not done: a sleeping laptop does not necessarily end the remote round.
    Raise: Not done  
    Case: normal use - The laptop sleeps while its SSH connection is established. [The planned SSH options](/plans/REMOTE-1.md:90) run their keepalive checks on the laptop, which is asleep. [The remote driver](/src/forge/codex_turn.py:123) ends only when its input closes, which sleep alone does not guarantee.  
    Gain 5, Work 3, Harm 3
    Disposition: cut - What changes for you, Accepted limits and the details no longer say the round ends: the laptop stops following it, the machine's round can go on until Codex ends its turn, and the next round and turn-off refuse while it still runs, then bring its work back (test_4 still-running case).

11. Blocking: Not done: laptop readiness checks can prevent a ready remote machine from being used.
    Raise: Not done  
    Case: normal use - A developer coordinates with Claude and has set up Codex on the remote machine, but has no local Codex kit or local trust entry. [Worker readiness](/src/forge/worker.py:213) checks both on the laptop before [the planned machine choice](/plans/REMOTE-1.md:110) runs. Skipping the later check in `codex.run` does not skip these checks.  
    Gain 3, Work 2, Harm 3
    Disposition: keep - the laptop is the fallback for every round that the machine cannot take (Done-when 4), so it must be ready to run Codex itself; What changes for you now says the laptop still needs Codex ready.

12. Advisory: Not done: the machine’s place count misses rounds from other developers.
    Raise: Not done  
    Case: normal use - Three developers use separate accounts on one four-processor machine. [The plan](/plans/REMOTE-1.md:110) counts the current laptop’s rows and the remote user’s rows, but remote workers are launched directly and each user has a separate [lane record](/src/forge/machine.py:104). All three can start while the promised limit is two.  
    Gain 4, Work 4, Harm 3
   Disposition: keep - below the bar (follow-up)

13. Blocking: Plan gap: the test machine does not reproduce a stopped SSH connection.
    Raise: Plan gap  
    Case: normal use - The stop test ends the local SSH process while the remote driver is waiting. [The stand-in](/plans/REMOTE-1.md:140) gives the remote child the same input and output pipes in a separate session. The child keeps the output pipe open, while [the laptop runner](/src/forge/codex.py:624) waits for output before closing input. The planned stop test can hang with the remote child still running.  
    Gain 3, Work 2, Harm 3
    Disposition: cut - the test machine now relays stdin, stdout and stderr through its own pipes like ssh, so ending it closes the child's stdin and ends the laptop's read; the stop test cannot hang on the child.

14. Blocking: Unproven: item 2: the remote worker’s test command runs.
    Raise: Test  
    Case: normal use - The transferred checkout lacks a usable `origin/main` reference, so [forge test](/src/forge/fasttest.py:356) refuses. [The planned round test](/plans/REMOTE-1.md:125) can still pass: [the Codex stand-in](/tests/stubs/codex-app-server:163) commits but does not run `forge test`.  
    Gain 3, Work 2, Harm 3
    Disposition: cut - the stub app server gets STUB_CODEX_RUN, and test_2 runs `forge test` in the round's folder on the machine with a fast_test command; its output comes back in the commit and must show the test ran and passed.

15. Advisory: Not done: fallback is silent when a developer has not named a machine.
    Raise: Not done  
    Case: normal use - The shared repo enables remote rounds, but one developer has not configured their local host. [The plan](/plans/REMOTE-1.md:110) explicitly returns without a line, although [Done when 4](/plans/REMOTE-1.md:40) promises the reason when the machine is not set up. [The current local settings reader](/src/forge/repo.py:700) permits that per-developer state.  
    Gain 3, Work 1, Harm 1
   Disposition: keep - below the bar (follow-up)

16. Advisory: Trap: the new local host key breaks commands on older pinned branches.
    Raise: Functional  
    Case: normal use - A developer enables the feature after upgrading the main branch while an existing task still pins the previous Forge release. That release’s [local settings reader](/src/forge/repo.py:711) rejects `host`, so commands on the older task, such as `forge test`, refuse before they can run. [The plan](/plans/REMOTE-1.md:63) does not cover this pinned-release case.  
    Adds work: preserve commands on older pinned branches after adding the local setting; F 2 x H 2 = 4; 2 x C = 4.  
    Gain 4, Work 3, Harm 3
   Disposition: cut - by the owner's answer of 17 Nov 2026 the name goes with `forge lanes --box setup --host <name>` and lives in Forge's record; forge.local.toml gets no new key, so earlier pinned releases are unaffected.

## Round 2

17. Blocking: Data loss: a checkout name can hide a running worker from turn-off.
    Raise: Data loss  
    Case: normal use - The laptop checkout is named `project(2)`. [The plan](/plans/REMOTE-1.md:93) puts that name in the remote path and passes it to `pgrep -f` as a pattern. Parentheses have special meaning in that pattern, so it does not match the literal driver path. [The turn-off check](/plans/REMOTE-1.md:146) can consequently delete the folder while the worker is already running. [The pgrep manual](https://github.com/procps-ng/procps/blob/master/man/pgrep.1) specifies that the pattern is a regular expression.  
    Gain 4, Work 2, Harm 4
    Disposition: cut - name matching is gone: each round writes its process id and start time to its own `.pid` file, and Forge reads exactly those files; no pattern holds a checkout or item name.

18. Blocking: Plan gap: the running-worker check can find its own inspection shell.
    Raise: Plan gap  
    Case: normal use - A round finishes and Forge sends the specified `pgrep -f` command over SSH to check it. The remote shell’s command line contains the path being searched for, so `pgrep` can match that shell and report that the finished worker still runs. [The plan](/plans/REMOTE-1.md:137) then refuses instead of bringing the commits back. [The pgrep manual](https://github.com/procps-ng/procps/blob/master/man/pgrep.1) describes matching full command lines and the separate option for excluding ancestors.  
    Gain 5, Work 2, Harm 3
    Disposition: cut - no pgrep: a round runs only while `ps -o lstart= -p <id>` prints the saved start time, so the checking shell can never match.

19. Blocking: Security: the suggested stop command can stop another item’s worker.
    Raise: Security  
    Case: normal use - Tasks `BOARD/UI` and `BOARD/UI-FORM` run on the same machine. The planned pattern for `BOARD/UI` ends in `BOARD-UI-`, which also matches the other task’s driver path. Following [the suggested `pkill` command](/plans/REMOTE-1.md:138) can therefore stop work the developer did not choose to stop. Both task names are accepted by [the item-name rule](/src/forge/repo.py:1113).  
    Adds work: identify the requested item’s process separately from other items; F 2 x H 2 = 4; 2 x C = 4.  
    Gain 3, Work 2, Harm 4
    Disposition: cut - runs live in `runs/<item>/` (the item's `/` is a folder level), Forge lists only that folder, and the printed stop line is `kill -TERM -- -<id>` for that one recorded id; test_4 checks that a running round of `<item>-FORM` does not affect `<item>`.

20. Blocking: Data loss: a task can merge while its remote commits remain stranded.
    Raise: Data loss  
    Case: normal use - A remote round commits work, its connection breaks, and the next round runs on the laptop while the machine is unreachable. [The plan](/plans/REMOTE-1.md:142) allows that round to proceed without the remote work, but adds recovery only to `forge work`. [Close](/src/forge/close.py:81) can then publish the laptop branch without those commits; after merge, [work refuses the finished item](/src/forge/worker.py:104), so the planned recovery step no longer works.  
    Adds work: prevent unfinished remote work from being bypassed at close; F 2 x H 2 = 4; 2 x C = 4.  
    Gain 4, Work 2, Harm 4
    Disposition: cut - `close.close` (and land through it) and `merge.merge` refuse while the item's record names a host, with `forge work <item>` as the next step; no ssh call; test_4 checks close after a cut-off round.

21. Blocking: Security: the commit-reminder turn skips the remote trust recheck.
    Raise: Security  
    Case: normal use - A developer revokes trust while the first remote turn is running, and that turn leaves uncommitted changes. [The new check](/plans/REMOTE-1.md:114) runs when choosing the machine, but [the reminder](/plans/REMOTE-1.md:118) starts a second turn without another check. [The driver](/src/forge/codex_turn.py:187) can then run without the project hooks.  
    Adds work: check remote trust before the reminder turn; F 1 x H 2 = 2; 2 x C = 2.  
    Gain 3, Work 2, Harm 4
    Disposition: cut - `box_ssh.trusted(where)` runs before every turn on the machine, the commit reminder included; when trust is gone Forge starts no turn there and refuses; test_4 has a trust case.

22. Advisory: Not done: setup’s retry instruction omits the required machine name.
    Raise: Not done  
    Case: normal use - First setup asks the developer to add the trust entry. [Its next step](/plans/REMOTE-1.md:109) says to rerun setup without `--host`, but [the record is saved only after trust passes](/plans/REMOTE-1.md:110). The retry therefore asks for the machine name instead of completing setup.  
    Gain 4, Work 1, Harm 2
    Disposition: cut - every setup refusal after step 1 names `--host {host}` in its Next line until the record has the name.

23. Advisory: Plan gap: finish cannot both refuse and return the uncommitted-file warning.
    Raise: Plan gap  
    Case: normal use - The worker and its reminder both leave an uncommitted file. [Finish](/plans/REMOTE-1.md:119) calls bring-back and expects its file list, but [bring-back](/plans/REMOTE-1.md:139) refuses on that file. The warning required by the amended test is therefore not produced as specified.  
    Gain 3, Work 1, Harm 2
    Disposition: cut - finish calls the bring-back without its two refusals and returns the uncommitted files for the warning, keeping the folder.

24. Advisory: Not done: turning off can leave fetched work outside its task branch.
    Raise: Not done  
    Case: normal use - Bring-back fetches a remote commit but its merge conflicts and is aborted. The commit is now in the laptop’s separate recovery reference, but not its task branch. [Turn-off](/plans/REMOTE-1.md:146) checks only whether the commit is in the clone, and [the next bring-back](/plans/REMOTE-1.md:137) clears the item’s host when the box record is gone. The next round can miss that commit.  
    Gain 4, Work 2, Harm 3
    Disposition: cut - turn-off counts a branch's commit as back only when it is an ancestor of the clone's branch of the same name, so a commit only fetched to refs/forge-host after a refused merge blocks turn-off.

## Round 3

25. Blocking: Security: the remote worker loses Forge’s worker restrictions.
    Raise: Security  
    Case: normal use - A remote worker encounters the fix-size limit and runs `forge fix allow-large`. In [the launch command](/plans/REMOTE-1.md:117), `FORGE_WORKER=1` applies to `echo`, not the subsequent driver; SSH does not normally forward the laptop’s environment. The remote worker can therefore pass [the person-only allowance check](/src/forge/task.py:733). The [test machine](/plans/REMOTE-1.md:153) inherits the laptop’s environment and can hide the defect. [Bash environment rules](https://www.gnu.org/software/bash/manual/bash.html), [OpenSSH environment rules](https://man.openbsd.org/ssh_config#SendEnv).  
    Adds work: pass and test the worker marker on the remote driver; F 3 x H 2 = 6; 2 x C = 2.  
    Gain 4, Work 2, Harm 4
    Disposition: cut - the round's command now exports FORGE_WORKER (with the test CPU caps) before it starts the driver; the test machine drops every FORGE_* and PYTEST_* value as ssh does, and test_2 checks that the driver's command sees FORGE_WORKER=1.

26. Blocking: Data loss: finish can remove a folder while its remote worker still runs.
    Raise: Data loss  
    Case: normal use - An SSH connection breaks and the laptop reconnects while the remote turn is still running. [Finish](/plans/REMOTE-1.md:120) assumes the driver has ended and bypasses the running-process refusal, although [the plan](/plans/REMOTE-1.md:23) says the turn can continue after a break. If the checkout is clean when inspected, cleanup can remove it while the worker is still using it.  
    Not done: item 4: keep the remote work until the running round has ended.  
    Gain 4, Work 2, Harm 4
    Disposition: cut - by the owner's answer, Forge deletes no run folder by itself; finish and the bring-back only fetch and merge commits and detach ended folders, so a folder in use is never removed.

27. Blocking: Data loss: cleanup deletes ignored non-cache files left by a worker.
    Raise: Data loss  
    Case: normal use - A worker leaves useful local notes in an ignored file. [The bring-back check](/plans/REMOTE-1.md:139) uses `git status` without ignored files, then removes the apparently clean folder. Git’s [worktree removal code](https://github.com/git/git/blob/master/builtin/worktree.c) uses a similar status check before deleting the directory. The existing [cleanup rule](/src/forge/task.py:817) keeps ignored data outside recognized caches.  
    Not done: item 5: retain ignored non-cache work that has not come back.  
    Gain 3, Work 2, Harm 4
    Disposition: cut - no automatic delete remains; turn-off lists each run folder's ignored files outside the caches (and uncommitted ones) and deletes only with --yes after the developer agrees.

28. Blocking: Data loss: close on another clone cannot see the unfinished-work guard.
    Raise: Data loss  
    Case: normal use - A developer’s remote round is cut off, and a teammate picks up an existing pull request from another clone and closes it. [The new guard](/plans/REMOTE-1.md:121) checks the first clone’s unshared item record; [the second clone can pick up the published branch](/src/forge/task.py:239) without that record. It can publish and merge without the remote commits, after which [work refuses the merged item](/src/forge/worker.py:104).  
    Adds work: make the unfinished-work check visible across clones; F 2 x H 3 = 6; 2 x C = 6.  
    Gain 4, Work 4, Harm 4
    Disposition: keep - by the owner's answer, a known issue in Accepted limits: a teammate closing the same task from another clone does not see commits still on your machine.

29. Blocking: Data loss: turn-off deletes stashed remote work.
    Raise: Data loss  
    Case: normal use - A worker stashes edits while resolving a merge and leaves the stash behind. [Finish](/plans/REMOTE-1.md:139) checks the worktree and branch, and [turn-off](/plans/REMOTE-1.md:148) checks branches but not stashes. Git keeps a stash under `refs/stash`, outside those branches, so deleting the remote clone deletes that work. [Git stash documentation](https://git-scm.com/docs/git-stash).  
    Not done: item 5: retain remote stashes whose work has not come back.  
    Gain 3, Work 2, Harm 4
    Disposition: cut - turn-off lists the clone's stashes with everything else and deletes only with --yes after the developer agrees.

30. Advisory: Not done: setup names the wrong trust file when `CODEX_HOME` is set.
    Raise: Not done  
    Case: normal use - The remote user configures a custom Codex home. [Setup](/plans/REMOTE-1.md:104) reads its `config.toml`, but [the refusal](/plans/REMOTE-1.md:110) tells the developer to edit `~/.codex/config.toml`. Following that step leaves the checked file unchanged, so setup refuses again. [Forge’s existing doctor](/src/forge/doctor.py:479) also supports `CODEX_HOME`.  
    Gain 3, Work 1, Harm 2
    Disposition: cut - the trust refusal names the config file that setup read on the machine (${CODEX_HOME:-$HOME/.codex}/config.toml, resolved there).

31. Advisory: Not done: committed submodule code does not reach the remote checkout.
    Raise: Not done  
    Case: normal use - A repo’s build uses code in a Git submodule. [The planned transfer](/plans/REMOTE-1.md:117) pushes the main repository and creates a worktree, but does not transfer or initialize the submodule. A main-repository commit contains a reference to the submodule commit, not its files. [Git submodule documentation](https://git-scm.com/docs/gitsubmodules). The [planned round test](/plans/REMOTE-1.md:132) has no submodule and can pass.  
    Gain 3, Work 4, Harm 2
    Disposition: cut - a repo with a .gitmodules file keeps its rounds on the laptop with the reason `this repo has git submodules, which do not reach the machine yet`; test_4 has the case.

## Round 4

32. Blocking: Data loss: turn-off can delete work without first showing it.

    Raise: Data loss  
    Case: normal use - A developer runs `forge lanes --box off --yes` directly. [The plan](/plans/REMOTE-1.md:150) reads the folder but deletes it without printing its contents or requiring an earlier preview. The developer can therefore agree to deletion without seeing uncommitted files, stashes, or commits that will be lost.  
    Not done: item 5: list the work before the developer agrees to delete it.  
    Gain 4, Work 2, Harm 4
    Disposition: cut - turn-off prints the full list of what the folder holds before it deletes, also when `--yes` is given at once (For the builders, item 5).

33. Blocking: Data loss: a commit made in a kept folder escapes the close guard.

    Raise: Data loss  
    Case: normal use - A remote round leaves an uncommitted file. Forge keeps its folder, detaches it, and [clears the item’s host record](/plans/REMOTE-1.md:145). The developer returns to that folder, checks out the task branch, and commits the file. From the same laptop, close now passes [the host-record guard](/plans/REMOTE-1.md:123) and can merge without that commit. This does not require the separate-clone case accepted in finding 28.  
    Adds work: detect commits added to kept folders before close; F 2 x H 3 = 6; 2 x C = 4.  
    Gain 4, Work 3, Harm 4
    Disposition: keep - by the owner's answer, a known issue in Accepted limits: a commit made by hand in a kept round folder after its round ended is not seen by close.

34. Blocking: Data loss: a failed process lookup can leave a running round unprotected.

    Raise: Data loss  
    Case: normal use - A Linux machine has BusyBox `ps`, which [does not support the planned options](https://busybox.net/BusyBox.html). [The launch command](/plans/REMOTE-1.md:119) still starts the driver because `echo` succeeds, but its process file has no usable start time. [Turn-off](/plans/REMOTE-1.md:150) has no required refusal for that failed lookup, so it can treat the running round as ended and delete its work. The existing [process identity check](/src/forge/codex.py:895) treats an unreadable identity as potentially running.  
    Adds work: refuse deletion when the remote process identity cannot be read; F 2 x H 3 = 6; 2 x C = 4.  
    Gain 3, Work 2, Harm 4
    Disposition: cut - setup refuses a machine whose `ps -o lstart` shows no start time (BusyBox), with one line naming procps; a `.pid` file Forge cannot read counts as running, so nothing is deleted on a guess.

35. Blocking: Not done: a conflicted run cannot release its task branch for the next round.

    Raise: Functional  
    Case: normal use - A worker is asked to resolve a default-branch merge and ends with conflicts still in its remote folder. [The new bring-back step](/plans/REMOTE-1.md:145) runs `git checkout --detach` there, but [Git refuses that checkout while the index has unresolved conflicts](https://github.com/git/git/blob/master/builtin/checkout.c). The branch remains checked out, so the next remote round cannot start in a fresh folder as planned.  
    Adds work: handle a kept folder whose unresolved conflicts prevent detachment; F 2 x H 2 = 4; 2 x C = 4.  
    Gain 5, Work 2, Harm 3
    Disposition: cut - a folder that cannot be detached stays as it is with one line; each round pushes a new refs/forge-runs/<id> ref, checks the machine's branch is an ancestor of it, and makes its folder with `worktree add -f -B`, so the next round starts in a new folder.

36. Advisory: Unproven: turn-off cannot compare branches whose commits exist on different machines.

    Raise: Test  
    Case: normal use - A cut-off remote round leaves a commit that never reached the laptop; while the machine is unreachable, a laptop round makes a different commit. Neither machine has both branch tips, so [the planned `git merge-base` check](/plans/REMOTE-1.md:150) cannot compare them without transferring history. The planned test pushes a laptop commit to the machine, so both sides already have it and the test can pass without covering this case.  
    Not done: item 5: list commits that have not come back.  
    Gain 3, Work 2, Harm 2
    Disposition: keep - below the bar (follow-up)

37. Advisory: Gate: the new turn-off flow is marked as needing no design.

    Raise: Gate  
    Case: normal use - The agent presents a list of work, asks the developer to agree to deletion, and then runs the confirmed turn-off command. [The plan](/plans/REMOTE-1.md:30) gives “no screen” as its reason for `Design: none`, but the cold-read rule also requires a design when a part changes a flow.  
    Gain 3, Work 4, Harm 2
    Disposition: keep - below the bar (follow-up)
