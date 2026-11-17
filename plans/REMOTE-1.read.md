---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-17T12:16:47.499089+00:00
seconds: 743.998
read_hash: e1224145830b90ee6fd10b28a55b471d6b6c6ab9
round: 1
passed: no
doc_seen: e1224145830b90ee6fd10b28a55b471d6b6c6ab9
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1e964-e202-7e63-964c-f3f99effee22
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
   Disposition: keep - below the bar (follow-up)
