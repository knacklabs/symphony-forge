---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-12T17:31:42.459446+00:00
seconds: 536.54
read_hash: 802630fd5d9056bd0535d971971801b25e7c77a4
round: 4
passed: no
doc_seen: 802630fd5d9056bd0535d971971801b25e7c77a4
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 44eb8ddc1726ea0b5051051a3b7e9c5875145385
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1d08a-3b0f-7ba3-8056-a21706cc3701
session:
loop_choice: more
loop_reason: The owner chose one more round with a simpler rule for how Forge knows its boxes
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

1. Blocking: Data loss: the documented retry deletes a Docker box.
   Raise: Data loss
   Case: normal use - After signing in, a developer follows the printed `forge lanes --box setup` next step, or the printed `--copy` command. Neither includes `--docker`, so the rule in [the plan](/plans/FORGE-PROVIDER-1.md:81) deletes the existing Docker box, including its sign-ins and approved files. The setup test retries only the light box.
   Gain 5, Work 2, Harm 4
   Disposition: cut - `--docker` now counts only when setup makes the kept box; the record keeps the type, a later setup without `--docker` uses it, and a differing `--docker` refuses and names `forge lanes --box off`; setup never deletes a kept box (Shared "Machine type", `test_2`).

2. Blocking: Data loss: committed work is deleted when both pushes fail.
   Raise: Data loss
   Case: normal use - GitHub becomes unreachable or the box’s GitHub credential expires after a builder commits. [The plan](/plans/FORGE-PROVIDER-1.md:122) tries a second push to the same remote, then deletes the copy when the run ends. If both pushes fail, the commits never reach the laptop.
   Gain 5, Work 3, Harm 4
   Disposition: defer - build rounds moved to the second story (Notes, Out of scope); this story's copies push nothing.

3. Blocking: Data loss: a stopped or failed copy can keep pushing.
   Raise: Data loss
   Case: normal use - A provider outage prevents both polling and deletion of a running copy. [The plan](/plans/FORGE-PROVIDER-1.md:114) makes deletion best effort and returns to the laptop; its stop rule also frees the row after a failed delete. The remote builder can still push after the laptop starts another round, contrary to the promise at line 22.
   Gain 5, Work 3, Harm 4
   Disposition: defer - build rounds moved to the second story (Notes, Out of scope); a test copy only fetches, so a copy that agent37 failed to delete can cost money but cannot change the branch (item 1).

4. Blocking: Not done: the sign-in terminal opens as the wrong user.
   Raise: Not done
   Case: normal use - A developer follows the setup command in [the plan](/plans/FORGE-PROVIDER-1.md:135). Agent37’s [SSH instructions](https://www.agent37.com/docs/agents-api/ssh.md) say the default login is `root`, while its [base image](https://raw.githubusercontent.com/agent37-platform/templates/main/images/b2b/base/Dockerfile) runs commands as `node`. The tools and sign-ins therefore live in different home directories from those checked by Forge.
   Gain 5, Work 2, Harm 3
   Disposition: cut - the terminal and SSH are gone: Forge starts GitHub's own code-and-link sign-in (`gh auth login --web`) with exec, as the same user that runs every box command, and prints only the code and the link (item 2 step 4).

5. Blocking: Not done: first-time terminal access needs an unplanned setup step.
   Raise: Not done
   Case: normal use - A developer has not registered an SSH key with agent37. Its [SSH instructions](https://www.agent37.com/docs/agents-api/ssh.md) require registration before connecting; the documented setup also saves the provider key to a local file. [The plan](/plans/FORGE-PROVIDER-1.md:135) gives neither that prerequisite nor a path consistent with its shell-only key rule. The fake test writes sign-in markers and does not exercise terminal access.
   Gain 4, Work 2, Harm 3
   Disposition: cut - no SSH key, no `npx agent37 ssh setup` and no key file: the sign-in is GitHub's device sign-in started by exec, and the fake exercises it through a stub `gh` that prints the code and waits for approval (item 2, `test_2`).

6. Blocking: Not done: the install command is lost on the first sign-in retry.
   Raise: Not done
   Case: normal use - Setup starts with `--install`, then stops for the developer to sign in. The printed retry omits `--install`, and [the setup steps](/plans/FORGE-PROVIDER-1.md:135) run that command only when it is given. The box can be marked ready without the packages its tests need; the planned setup test has no install-command case.
   Gain 4, Work 2, Harm 3
   Disposition: cut - `--install` is stored in the record on first use and reused by every later setup and by copies; `test_2` checks a second setup with no options reruns it.

7. Blocking: Not done: a model key can incorrectly pass the GitHub sign-in check.
   Raise: Not done
   Case: normal use - A developer sets an Anthropic or OpenAI key but has not signed in to GitHub. [The plan](/plans/FORGE-PROVIDER-1.md:135) says each sign-in check passes when either model key is present, including `gh auth status`. A model key cannot authorize the planned clone or push.
   Gain 4, Work 1, Harm 3
   Disposition: cut - model keys are out of this story; the check is GitHub's own: `gh auth status --hostname github.com` and `git ls-remote` of this repo's https URL must both pass (item 2 step 4).

8. Blocking: Not done: `--copy` accepts files that Git does not ignore.
   Raise: Not done
   Case: normal use - A developer approves an untracked configuration file that is not ignored. The checks in [the plan](/plans/FORGE-PROVIDER-1.md:138) reject tracked files but do not require the file to be ignored, so uncommitted content is sent to the provider despite item 3.
   Gain 3, Work 2, Harm 3
   Disposition: cut - `--copy` now requires `git check-ignore -q -- <file>` to pass, so tracked files and untracked files that git does not ignore are refused with one message; `test_2` checks both.

9. Blocking: Not done: some test commands contain laptop-only paths.
   Raise: Not done
   Case: normal use - A Python repo has no `fast_test`, or close selects tests without one. [Current test selection](/src/forge/review.py:363) constructs a command containing the laptop’s Python executable and Forge installation path. [The plan](/plans/FORGE-PROVIDER-1.md:113) sends that command unchanged to Linux, where those paths do not exist. The fake runs on the laptop and can still see them.
   Gain 4, Work 2, Harm 3
   Disposition: cut - a test command that holds this Forge's install folder (the laptop picker command that `close_test` builds without `fast_test`) stays on the laptop with its own reason line; `test_4` has the case.

10. Blocking: Not done: a detached checkout can report a passing run without the task’s tests.
    Raise: Not done
    Case: normal use - A Python task has a broad changed-test selection and names its tests in the task table. [The plan](/plans/FORGE-PROVIDER-1.md:113) checks out tests detached; [the picker](/src/forge/fasttest.py:725) then cannot identify the task and can return success without running its named tests.
    Gain 4, Work 2, Harm 3
    Disposition: cut - the copy checks out `-B <the laptop's current branch> FETCH_HEAD`, so `branch_item` finds the task as on the laptop; a checkout not on a branch stays on the laptop; `test_1` checks the copy's branch.

11. Blocking: Not done: a fresh box does not populate Git submodules.
    Raise: Not done
    Case: normal use - A repository’s committed application or tests include a Git submodule. [The planned clone and fetch](/plans/FORGE-PROVIDER-1.md:136) do not initialize it, so the box lacks files present in the laptop checkout. Forge already handles repositories with submodules in [its tests](/tests/test_doctor_fix.py:326).
    Gain 3, Work 2, Harm 3
    Disposition: cut - a repo with `.gitmodules` stays on the laptop with its reason line; submodules in boxes are a follow-up story; `test_4` has the case.

12. Blocking: Not done: a failed box test does not rejoin the laptop queue.
    Raise: Not done
    Case: normal use - A copy fails after its test starts. [The fallback rule](/plans/FORGE-PROVIDER-1.md:86) removes `admitted` but leaves `started_at`; [the current queue](/src/forge/machine.py:165) treats either field as admission. The test can start while the laptop is full, with the copy’s allocation still counted.
    Gain 4, Work 2, Harm 3
    Disposition: cut - `back_to_laptop` now clears `box`, `box_copy`, sets `admitted` False, `started_at` None and `processes` 0, then waits; `test_4` checks the row waits behind the held entry with `started_at` null.

13. Blocking: Not done: direct pytest-picker runs stay in the laptop queue.
    Raise: Not done
    Case: normal use - A developer runs the documented `forge test --pytest <base>` while the test lane is full. [The plan](/plans/FORGE-PROVIDER-1.md:111) explicitly leaves [that command’s own queue entry](/src/forge/fasttest.py:341) unchanged, so it does not go to a box.
    Gain 3, Work 2, Harm 3
    Disposition: cut - Done-when 1 and What changes now name test runs that a builder or close starts; a direct `forge test --pytest <base>` stays on the laptop by design, and the guide says so.

14. Blocking: Not done: a test backlog is missed when deciding where a build runs.
    Raise: Not done
    Case: normal use - Enough tests are waiting that Forge pauses new builds, while an agent place is otherwise free. [The proposed stand-in](/plans/FORGE-PROVIDER-1.md:84) lacks the backlog field that [the current queue](/src/forge/machine.py:609) assigns to real entries. Forge decides the build would not wait, then queues it on the laptop.
    Gain 3, Work 2, Harm 3
    Disposition: defer - build rounds moved to the second story (Notes, Out of scope); this story calls `machine.full` only for test runs.

15. Blocking: Not done: changed dependency manifests can leave stale packages in the box.
    Raise: Not done
    Case: normal use - A Python project installs dependencies from `pyproject.toml` without a lock file, and a task changes those dependencies. [The planned reinstall check](/plans/FORGE-PROVIDER-1.md:89) checks only lock and requirements files, although [the current picker](/src/forge/fasttest.py:368) recognizes `pyproject.toml` as a shared test input. The box can test with old dependencies.
    Gain 3, Work 2, Harm 3
    Disposition: cut - the dependency list now uses the shared test inputs that `fasttest.related` names, including `pyproject.toml`, plus `package.json`, `pnpm-lock.yaml` and `yarn.lock`; with an install command the copy reinstalls, without one the run stays on the laptop with a reason that names the fix; `test_1` and `test_4` have the cases.

16. Blocking: Not done: a question from the commit reminder is lost.
    Raise: Not done
    Case: normal use - A builder leaves changes uncommitted and asks a question during the follow-up commit reminder. [The planned box route](/plans/FORGE-PROVIDER-1.md:117) returns only `final`, while [the existing worker](/src/forge/worker.py:418) checks both the first answer and the reminder’s answer for questions. The planned reminder test only commits the file.
    Gain 3, Work 2, Harm 3
    Disposition: defer - build rounds and the commit reminder moved to the second story (Notes, Out of scope).

17. Blocking: Plan gap: the first part requires a test run that a later part implements.
    Raise: Plan gap
    Case: normal use - KEEP runs its assigned contract test before it can finish. [That test](/plans/FORGE-PROVIDER-1.md:153) requires a box test run, but TESTS owns that route and waits for KEEP. [The current test runner](/src/forge/review.py:416) has no box route.
    Gain 4, Work 1, Harm 2
    Disposition: cut - KEEP's tests and its part of the contract case use only setup, copy and off; TESTS adds the fork and test-run calls to the contract case after KEEP.

18. Blocking: Plan gap: the shared copy runner has no pinned interface.
    Raise: Plan gap
    Case: normal use - KEEP builds the runner used by setup, TESTS and BUILD. [The task order](/plans/FORGE-PROVIDER-1.md:183) names the shared runner but gives it no function name or inputs and outputs, although the later parts depend on it.
    Gain 4, Work 1, Harm 2
    Disposition: cut - Shared "The interface between the two parts" pins `ProviderError`, `PROVIDERS`, `provider`, `record`, `run_script`, `drop` and the `box_agent37` functions with exact signatures; KEEP commits them and `test_2` crosses both sides.

19. Blocking: Gate: the box integrations have no pinned CLI versions.
    Raise: Gate
    Case: normal use - Two developers set up boxes at different times. [The plan](/plans/FORGE-PROVIDER-1.md:134) installs the model CLIs without naming versions, then depends on their flags and output. [The current Codex integration](/src/forge/codex.py:34) pins its version; this plan leaves the new boundary without that required contract.
    Gain 4, Work 2, Harm 3
    Disposition: cut - `box.TOOLS` pins GitHub CLI 2.103.3 and uv 0.13.7 with exact download URLs, Forge installs at the repo pin, setup reinstalls on a pin change, and the contract case checks the install script names the pins; the model CLIs are out of this story.

20. Blocking: Gate: `Design: none` covers a new setup and turn-off flow.
    Raise: Gate
    Case: normal use - A developer enables boxes, signs in, approves files one by one, and later deletes the boxes. [The plan](/plans/FORGE-PROVIDER-1.md:38) marks design as none even though KEEP changes that flow; [the current command](/src/forge/machine.py:25) only displays lanes.
    Gain 4, Work 2, Harm 3
    Disposition: keep factually wrong: no screen, page or app shell is added; setup and turn-off are terminal lines whose exact words the builders' section pins, and the machine view gains only the words "in a box"; the plan's Design line now states this reason.

## Round 2

21. Blocking: Security: turn-off can report deletion while sign-ins remain at the provider.
    Raise: Security  
    Case: normal use - agent37 rejects a delete while the developer turns boxes off. [The plan](/plans/FORGE-PROVIDER-1.md:83) makes `drop` return an error string, but [turn-off](/plans/FORGE-PROVIDER-1.md:152) has no failure branch: it removes the record and says the boxes were deleted. The surviving box can retain the GitHub sign-in and approved files, and a second turn-off finds no record.  
    Gain 5, Work 2, Harm 4
    Disposition: cut - turn-off counts a box as deleted only when agent37 confirms it (`200` with `deleted: true`, or `404`); on any failure it keeps the record, names each box left, says its GitHub sign-in and copied files are still at agent37, and exits 1 with `Next: forge lanes --box off`; `test_5` has the failure case.

22. Blocking: Not done: first-time setup cannot pass the private-repository check.
    Raise: Not done  
    Case: normal use - A developer approves GitHub sign-in for a private repository. [Setup](/plans/FORGE-PROVIDER-1.md:127) requires `git ls-remote` to succeed before it runs `gh auth setup-git`. The [pinned GitHub CLI](https://raw.githubusercontent.com/cli/cli/v2.103.3/pkg/cmd/auth/shared/login_flow.go) does not configure Git’s credential helper during this noninteractive login, so Git cannot use the new sign-in. The fake maps the URL to an unauthenticated local repository and misses the failure.  
    Gain 5, Work 2, Harm 3
    Disposition: cut - the sign-in steps now run `gh auth status`, then `gh auth setup-git --hostname github.com`, then `git ls-remote` of the https URL, and repeat all three after the device sign-in; the fake's unauthenticated ls-remote fails until the stub `setup-git` runs after an approved sign-in, so `test_2` fails on the wrong order.

23. Blocking: Not done: setup can record a package version it has not installed.
    Raise: Not done  
    Case: normal use - The default branch updates its dependencies, then a developer reruns setup after a Forge upgrade. [Setup](/plans/FORGE-PROVIDER-1.md:128) fetches the new default branch without checking it out, runs the install command against the old checkout, and records the new default-branch commit as the installed baseline. [The changed-package check](/plans/FORGE-PROVIDER-1.md:90) then skips installation for tasks based on that new commit. Their tests can pass using old dependencies.  
    Gain 5, Work 2, Harm 3
    Disposition: cut - setup now checks out the fetched `origin/<default branch>` commit detached, runs the install there, and records that commit as `head` only after the install passes; `test_2` moves the default branch and checks the checkout comes before the install and `head` is the new commit.

24. Advisory: Not done: one read truncates results from a realistic large test run.
    Raise: Not done  
    Case: normal use - A close runs roughly 4,000 tests. [The results hook](/src/forge/fasttest.py:552) writes each passing test name twice; this repo’s [.test_durations](/.test_durations:1) contains 3,962 names totaling about 471 KB. [The plan](/plans/FORGE-PROVIDER-1.md:117) reads the resulting file with one `cat`, but [agent37 cuts the middle of output over 512 KB](https://www.agent37.com/docs/agents-api/exec.md). Test results and the invocation record used for retries can be lost.  
    Gain 4, Work 2, Harm 3
    Disposition: cut - results and logs are read in parts of at most 400 KB through `box.read_file` until a short part, under agent37's 512 KB cap; the fake cuts output at 512 KB and `test_1` moves a 1.2 MB results file whole.

25. Advisory: Not done: a retry can use file paths from the other machine.
    Raise: Not done  
    Case: normal use - A box test fails, and a laptop place becomes free before close retries it. [The results hook](/src/forge/fasttest.py:552) records failed files as absolute box paths; [the retry](/src/forge/fasttest.py:503) uses those paths unchanged. The amended [second admission](/plans/FORGE-PROVIDER-1.md:114) can select the laptop, where those paths do not exist. The same problem occurs in the other direction.  
    Gain 3, Work 2, Harm 3
    Disposition: cut - results going to the laptop map the box checkout prefix to the laptop checkout, and a retry's results going to a box map it back, so each machine gets its own paths; `test_1` checks the laptop file names only laptop paths.

26. Advisory: Unproven: item 2: setup can execute commands before a restarted box is ready.
    Raise: Test  
    Case: normal use - A developer copies an approved file into the stopped kept box. [The plan](/plans/FORGE-PROVIDER-1.md:130) starts it and writes the file, although start can return `202` while the box is still starting. [Agent37’s exec contract](https://www.agent37.com/docs/agents-api/exec.md) rejects commands in that state. No setup rule or test pins waiting for readiness after start.  
    Gain 3, Work 2, Harm 3
    Disposition: cut - `box.ready` waits for `running` and a passing `true` exec after every `create`, `start` and `copy`, including `--copy`; the fake's `start` answers `202` and refuses exec for two seconds in `test_2`.

27. Advisory: Unproven: item 4: a failed code push has no specified laptop fallback.
    Raise: Plan gap  
    Case: normal use - GitHub is unreachable when Forge pushes the temporary code reference. [The plan](/plans/FORGE-PROVIDER-1.md:118) specifies fallback for `ProviderError`, but not for a failed Git command; the existing [Git helper](/src/forge/repo.py:405) raises `CalledProcessError`. The planned failure test covers a provider fork failure, so it can pass without covering this path.  
    Gain 3, Work 2, Harm 3
    Disposition: cut - the code-ref push runs through `repo.run`, and a non-zero exit sends the run back to the laptop with `the code could not reach GitHub: ...`; `test_4` has the case.

28. Advisory: Not done: Forge’s test picker reduces the box’s four-processor allocation.
    Raise: Functional  
    Case: normal use - A repository uses this checkout’s [`fast_test`](/forge.toml:7), which starts `forge test --pytest`. The [box environment](/plans/FORGE-PROVIDER-1.md:117) has no parent lane entry in the copy, so [the picker](/src/forge/fasttest.py:345) joins its own lane and replaces the four-processor setting. On a four-processor box, the existing [allocation rule](/src/forge/machine.py:89) gives it two.  
    Gain 3, Work 2, Harm 2
    Disposition: cut - `machine.test_slots` returns all cores when `FORGE_BOX=1`, as for `GITHUB_ACTIONS`, and the copy sets it, so the picker in the copy uses its 4 processors; `test_1` checks the picker's worker count.

## Round 3

29. Blocking: Data loss: setup can overwrite an approved settings file in the kept box.
    Raise: Data loss  
    Case: normal use - After a developer copies an ignored settings file, the default branch begins tracking a file at the same path. [Setup](/plans/FORGE-PROVIDER-1.md:132) now checks out that branch in the kept box. [Git overwrites ignored files by default](https://git-scm.com/docs/git-checkout), so the saved settings are lost without warning. The laptop file may since have changed or been removed.  
    Gain 5, Work 2, Harm 4
    Disposition: cut - approved files now live in `FILES_DIR` (`$HOME/forge-files`), outside the checkout, so no checkout in the kept box or a copy can overwrite them; a run copies them in only where its commit tracks no file at that path; `--copy` of a file already there refuses unless `--replace` is given; `test_2` covers the tracked-later case and the refusal.

30. Blocking: Security: a replacement kept box can make a surviving copy unfindable.
    Raise: Security  
    Case: normal use - Turning boxes off fails to delete a copy but deletes the kept box. [Turn-off](/plans/FORGE-PROVIDER-1.md:156) retains the old record, but if the developer later enables boxes and runs setup, [setup](/plans/FORGE-PROVIDER-1.md:128) replaces the gone kept box. The record has only one kept-box ID, so later turn-off looks for copies of the new box and misses the old copy with its GitHub sign-in. The failure test only rejects deletion of the kept box.  
    Gain 5, Work 2, Harm 4
    Disposition: cut - names now come from the GitHub owner and repo and the developer's hashed git email, with no box id (`forge-keep-<o>-<r>-<dev>`, `forge-copy-<o>-<r>-<dev>-<entry>`); setup finds the kept box and turn-off finds every box and copy through the provider's list by those names, whatever the record says, and turn-off also deletes leftover code refs under `refs/forge-box/<dev>/`; `test_5` deletes boxes the record does not know.

31. Advisory: Not done: chunked reads can corrupt multilingual test output.
    Raise: Not done  
    Case: normal use - A large test log or results file contains non-English text at a chunk boundary. [The new reader](/plans/FORGE-PROVIDER-1.md:85) cuts by bytes, but each exec response is a string. A UTF-8 character split between responses cannot be reconstructed by concatenating those strings. The [results hook](/src/forge/fasttest.py:552) writes UTF-8 text, while the large-file test can pass with ASCII alone.  
    Gain 3, Work 2, Harm 3
    Disposition: cut - `read_file` now moves 300 KB parts base64-encoded and returns bytes; callers decode the whole text once, so no character is cut; `test_1` puts a non-English character across each part boundary.

32. Advisory: Unproven: item 1: a large retry file may not fit in an exec request.
    Raise: Test  
    Case: normal use - A large failing test run is retried in another box. [The plan](/plans/FORGE-PROVIDER-1.md:121) transfers the previous results into that copy, but pins no transfer method. [Agent37 caps an exec request body at 1 MB](https://www.agent37.com/docs/agents-api/exec.md), so the planned 1.2 MB example cannot be sent in one request. The large-file test only reads results back from a box.  
    Gain 3, Work 2, Harm 3
    Disposition: cut - the retry file reaches the copy through `box.write_file`, base64 parts of 300 KB, each request far under agent37's 1 MB cap; the fake answers `413` above 1 MB, and `test_1`'s close case sends a 1.2 MB retry file to a box.

33. Advisory: Not done: an immediate install retry reuses the failed provider command.
    Raise: Not done  
    Case: normal use - A temporary download failure makes the kept-box tool installation fail, and the developer immediately reruns setup. [Setup](/plans/FORGE-PROVIDER-1.md:130) uses the same `forge-install-<version>` name. [Agent37 retains a command name for five minutes](https://www.agent37.com/docs/agents-api/exec.md), so the retry cannot start a fresh identical command during that time. The fake records these install commands without running them.  
    Gain 3, Work 2, Harm 3
    Disposition: cut - every exec name now ends with a part unique to the attempt (`forge-install-<version>-<unix seconds>`, `forge-sign-in-<unix seconds>`, `forge-run-<lane entry id>`); the fake answers a reused name with another command with `400`, as agent37 documents.

34. Advisory: Plan gap: the two parts do not pin the name of the box checkout.
    Raise: Plan gap  
    Case: normal use - Setup runs in the main checkout and a builder tests from a task worktree. [The plan](/plans/FORGE-PROVIDER-1.md:132) shares `$HOME/work/<repo name>` between KEEP and TESTS without defining whether the name comes from GitHub, the main checkout, or the current checkout. [Forge names task worktrees differently](/src/forge/task.py:228), so the parts can select different paths while a test that sets up and runs in one checkout passes.  
    Gain 4, Work 1, Harm 2
    Disposition: cut - `checkout_dir(top)` is pinned in KEEP as `$HOME/work/<GitHub repo name>`, from `github_repo(top)`, the same from the main checkout and any task worktree; TESTS uses it for the checkout and the path mapping.

35. Advisory: Unproven: item 2: the setup test never executes the tool installer.
    Raise: Test  
    Case: normal use - The install script contains the pinned version strings but fails before installing the tools. [The fake](/plans/FORGE-PROVIDER-1.md:147) records `forge-install-*` scripts without running them and supplies a `gh` stub separately. The planned setup and contract tests can therefore pass while the first real setup has no working installed tools.  
    Gain 3, Work 2, Harm 3
    Disposition: cut - the fake now serves the pinned `gh` and uv downloads, `FORGE_BOX_DOWNLOADS` points the real install script at them, and setup checks `gh`, `uv` and `forge` versions in the box after the install; `test_2` has a case whose `gh` download gives the wrong version and expects the install refusal.

## Round 4

36. **Blocking: Security: two repositories can share the same kept box.**  
    Raise: Security  
    Case: normal use - A developer uses `acme/payment_api` and `acme/payment-api`, both [valid GitHub repository names](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository). [The new naming rule](/plans/FORGE-PROVIDER-1.md:80) gives both the same name. Setup for the second repo finds the first repo’s box, and its test copies receive the first repo’s approved files. Turning off boxes from the second repo can also delete the first repo’s box and copies.  
    Gain 5, Work 2, Harm 4

37. **Blocking: Security: changing the Git email leaves credentialed boxes behind.**  
    Raise: Security  
    Case: normal use - A developer changes `git config user.email` after setup, then turns boxes off. [Box names](/plans/FORGE-PROVIDER-1.md:79) now contain a different hash, so [turn-off](/plans/FORGE-PROVIDER-1.md:165) finds nothing, reports that there is nothing to delete, and removes the record. The original kept box and copies can remain at agent37 with the GitHub sign-in and approved files.  
    Gain 5, Work 2, Harm 4

38. **Blocking: Data loss: teammates with the same Git email can delete each other’s boxes.**  
    Raise: Data loss  
    Case: normal use - Two developers use the same team email as their Git author email in one repo. [The developer name](/plans/FORGE-PROVIDER-1.md:79) is derived only from that email, so both get the same provider names. One developer’s setup can reuse the other’s GitHub sign-in, and [turn-off](/plans/FORGE-PROVIDER-1.md:165) can delete the other developer’s kept box and copies.  
    Gain 5, Work 2, Harm 4

39. **Blocking: Not done: approved files are unavailable to the kept-box installer.**  
    Raise: Not done  
    Case: normal use - A repo needs an ignored `.npmrc` to install private packages. The developer approves it, then reruns setup with `--install "npm ci"`. [The file is stored outside the checkout](/plans/FORGE-PROVIDER-1.md:82), but [setup runs the installer in the checkout](/plans/FORGE-PROVIDER-1.md:141) without putting the approved file there. npm reads [project configuration from the project root](https://docs.npmjs.com/files/npmrc/), so installation fails even after approval. The planned test uses `true` as the install command.  
    Gain 5, Work 2, Harm 3

40. **Blocking: Not done: recovering a kept box loses its install command.**  
    Raise: Not done  
    Case: normal use - A developer sets up the same repo from a second clone after the default branch changes dependencies. That clone has no local record, but [setup finds the existing box](/plans/FORGE-PROVIDER-1.md:137). The provider list supplies the box type, but not the [recorded install command](/plans/FORGE-PROVIDER-1.md:73). Setup without `--install` can record the new commit without reinstalling; later runs at that commit then skip installation and can report results using old packages.  
    Gain 5, Work 2, Harm 3

41. **Advisory: Not done: large approved files exceed Linux’s shell argument limit.**  
    Raise: Not done  
    Case: normal use - A developer copies an approved 150 KB settings file, within the plan’s 256 KB limit. [The writer](/plans/FORGE-PROVIDER-1.md:93) puts its roughly 200 KB base64 encoding in one command passed to `sh -c`. On Linux with 4 KB pages, [one argument is limited to 128 KB](https://man7.org/linux/man-pages/man2/execve.2.html), so the command cannot start even though it fits agent37’s HTTP request limit.  
    Gain 4, Work 1, Harm 3
