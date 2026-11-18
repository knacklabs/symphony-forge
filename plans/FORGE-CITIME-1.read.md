---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-18T09:39:37.516278+00:00
seconds: 302.209
read_hash: ae84f5c417e607b1343503396b09a3e5ba8e82ca
round: 6
passed: no
doc_seen: 7d1fa33871c27f42d7e07068c4361ceebe0f37ab
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 1411a349105f64f6d40612b677e8d6977fb6dcb3
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1ecb9-0d2c-7ba3-967f-9b980e7a0a1b
session:
loop_choice: accept
loop_reason: Owner accepted read round 5 on 18 Nov 2026: notes 51-53 are covered by one group rule in the builders' section (groups at most the file count, extra jobs pass, zero files fail, untimed files fill empty groups first)
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

1. Blocking: Not done: the default-branch test command does not exist.
   Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:90); [fasttest.py](/src/forge/fasttest.py:19).
   Case: normal use - After a merge, `forge test --change --base <before>` is rejected because `forge test` has no `--base` option. Its existing `--pytest` option takes a different path and does not run the starter’s `fast_test`. The required command change is outside MERGE’s Scope.
   Gain 5, Work 3, Harm 3
   Disposition: cut - moved to a separate story (owner, 18 Nov 2026), with this fix carried into its draft

2. Blocking: Not done: the red-branch check cannot recognize the planned push result.
   Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:89); [prcheck.py](/src/forge/prcheck.py:119).
   Case: normal use - On a push, both generated workflow shapes name the result `tests (other event)`, while the plan looks for `tests`. A failed post-merge run can therefore be missed. The planned workflow assertion does not check the result’s name.
   Gain 5, Work 2, Harm 3
   Disposition: cut - moved to a separate story (owner, 18 Nov 2026), with this fix carried into its draft

3. Blocking: Plan gap: MERGE’s Scope excludes the workflow wiring it requires.
   Raise: Plan gap — [task table](/plans/FORGE-CITIME-1.md:122); [prcheck.py](/src/forge/prcheck.py:74).
   Case: normal use - The push needs the previous commit in `BASE_SHA` and a different test command. MERGE may change only triggers and job `if` lines, but the current base value and command are elsewhere in the workflow generator.
   Gain 4, Work 1, Harm 2
   Disposition: cut - moved to a separate story (owner, 18 Nov 2026), with this fix carried into its draft

4. Blocking: Plan gap: a persistent failure on the default branch has no permitted repair path.
   Raise: Plan gap — [plan](/plans/FORGE-CITIME-1.md:89); [fullrun.py](/src/forge/fullrun.py:75).
   Case: normal use - A real regression makes the default branch red. The rule blocks the repair pull request as well, and a full run can test only the current default-branch commit. The refusal’s instruction to fix the branch cannot be completed through the stated flow.
   Gain 5, Work 3, Harm 3
   Disposition: cut - moved to a separate story (owner, 18 Nov 2026), with this fix carried into its draft

5. Blocking: Not done: the red-branch rule does not cover human merges.
   Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:32); [land.py](/src/forge/land.py:163).
   Case: normal use - Human merge is the default. Forge hands the person a pull-request link without calling `merge.merge`, the only place assigned the red-branch wait, so the promised rule does not stop that merge.
   Gain 5, Work 3, Harm 3
   Disposition: cut - moved to a separate story (owner, 18 Nov 2026), with this fix carried into its draft

6. Blocking: Not done: a later commit’s green check can hide the latest failure.
   Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:89); [merge.py](/src/forge/merge.py:108).
   Case: normal use - Two changes merge while their default-branch checks run concurrently. The newer commit’s narrow check finishes green first; the older commit’s check then fails. Walking commits newest first finds the green result and permits another merge even though the latest finished run is red.
   Gain 4, Work 2, Harm 3
   Disposition: cut - moved to a separate story (owner, 18 Nov 2026), with this fix carried into its draft

7. Blocking: Not done: an up-to-date branch rule forces another check for a non-overlapping change.
   Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:31); [merge.py](/src/forge/merge.py:220).
   Case: normal use - GitHub can require a pull request to include the current default branch before merging. Forge’s existing response to `BEHIND` runs close again, including a new check, even when the files do not overlap. The plan’s test uses a permissive GitHub stub.
   Gain 4, Work 2, Harm 3
   Disposition: cut - moved to a separate story (owner, 18 Nov 2026), with this fix carried into its draft

8. Blocking: Not done: an item’s own guide edits are mistaken for a merge repair.
   Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:87); [merge.py](/src/forge/merge.py:128).
   Case: normal use - A ready item edits a Forge guide and the default branch gains an unrelated file. The existing comparison sees the item’s guide edits in the combined tree, sets `overlap`, and starts another check even though no guide repair occurred.
   Gain 3, Work 2, Harm 3
   Disposition: cut - moved to a separate story (owner, 18 Nov 2026), with this fix carried into its draft

9. Blocking: Plan gap: TIME and OXLINT cannot start together with their stated Scopes.
   Raise: Plan gap — [plan](/plans/FORGE-CITIME-1.md:129); [task.py](/src/forge/task.py:516).
   Case: normal use - Both parts own the guide template, both host copies and the brief. Forge checks whole-file Scope overlap across started stories; different sections do not allow two unreviewed parts to start together.
   Gain 4, Work 1, Harm 2
   Disposition: cut - TIME no longer touches guide files; the text moved to a new RULES part that starts after OXLINT merges; guide copies are refreshed by `forge sync` and left out of every Scope.

10. Blocking: Not done: the small-change rule drops a shared setting before checking it.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:82); [docskip.py](/src/forge/docskip.py:130).
    Case: normal use - A change to `conftest.py` matches the prescribed test-file globs and is dropped before the shared-settings check. It is then classified as small, although the plan explicitly requires all groups for that file.
    Gain 3, Work 1, Harm 3
    Disposition: cut - the lockfile and shared-settings check now runs on all changed paths before test files are dropped; the GROUPS test has a `conftest.py` case.

11. Blocking: Not done: five commits are not five pushes.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:77); [close.py](/src/forge/close.py:419).
    Case: normal use - A developer pushes several commits at once. The previous push’s tested head can fall outside the last five commits even though it is among the last five pushes, so close and doctor can miss the slower run the owner chose to report.
    Gain 3, Work 2, Harm 3
    Disposition: cut - Forge reads the last 30 commits and takes the last five that have check runs (a push's head), so pushes, not commits, are counted; the TIME test has a three-commit push.

12. Blocking: Not done: close can refuse before the failed run’s other jobs finish.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:79); [checks.py](/src/forge/checks.py:331).
    Case: normal use - One job fails while another still runs. The current wait refuses as soon as it sees the failure, so it cannot print the promised time from the first start through the last completion. The planned failure case has only one test group.
    Gain 3, Work 2, Harm 3
    Disposition: cut - on a red refusal the line covers the jobs that ended and says how many were still running; What changes says so and the TIME test has a two-group case.

13. Blocking: Plan gap: the required live starter test demands the old browser behavior.
    Raise: Plan gap — [plan](/plans/FORGE-CITIME-1.md:105); [test_starter_tree.py](/tests/test_starter_tree.py:343).
    Case: normal use - Its live web-change check requires `web:e2e`, Playwright and the Docker stack. A starter that implements the new web-only behavior fails this required test.
    Gain 4, Work 1, Harm 2
    Disposition: cut - STARTER updates the live web-change listing in `tests/test_starter_tree.py` to expect no `web:e2e` and no Playwright.

14. Blocking: Unproven: item 3: the named test can pass without running API files in parallel.
    Raise: Test — [plan](/plans/FORGE-CITIME-1.md:103); [test_starter_tree.py](/tests/test_starter_tree.py:585).
    Case: normal use - The live part runs only with `FORGE_STARTER_LIVE=1`, and the named test does not establish that files ran concurrently. Three ordinary passing invocations can therefore leave the current serial setting in place.
    Gain 3, Work 2, Harm 3
    Disposition: cut - STARTER adds a static assertion that the API config no longer sets `fileParallelism: false`, and the builder runs the live test three times with `FORGE_STARTER_LIVE=1` and puts the times in the pull request.

15. Blocking: Unproven: item 3: shared configuration changes can still run browser tests.
    Raise: Test — [plan](/plans/FORGE-CITIME-1.md:104); [affected.mjs](/src/forge/templates/starter-python/scripts/affected.mjs:15).
    Case: normal use - Changing `package.json` selects all parts, and the Python starter’s full command includes browser tests. The proposed no-browser assertion covers a web-file change, so it can pass while this pull-request path still runs them.
    Gain 3, Work 2, Harm 3
    Disposition: cut - any run with a base skips browser tests and the browser install, also when everything is selected; the starter tests add a root `package.json` case.

16. Blocking: Unproven: item 3: a clean Python web-only run can lose its installation steps.
    Raise: Test — [plan](/plans/FORGE-CITIME-1.md:85); [test.mjs](/src/forge/templates/starter-python/scripts/test.mjs:47).
    Case: normal use - The current `stack` condition controls dependency installation as well as Docker. Setting it to API-only leaves a fresh web run without the packages needed by `api-types` and the web checks. The proposed `--list` test does not execute those commands.
    Gain 3, Work 2, Harm 3
    Disposition: cut - the Docker-only-for-API change is dropped; `stack` stays as it is, and the Python test checks that a web-only listing keeps the installs.

17. Blocking: Plan gap: MERGE omits its train regression from the Tests cell.
    Raise: Plan gap — [task table](/plans/FORGE-CITIME-1.md:122); [test_train_land_all.py](/tests/test_train_land_all.py:317).
    Case: normal use - The plan asks for an extended train test, but the Tests cell names only the two new merge tests. Existing train tests also expect three disjoint changes to form a train, contrary to the new rule.
    Gain 4, Work 2, Harm 2
    Disposition: cut - moved to a separate story (owner, 18 Nov 2026), with this fix carried into its draft

18. Advisory: Plan gap: the five-item train limit conflicts with “every” overlapping item.
    Raise: Plan gap — [plan](/plans/FORGE-CITIME-1.md:88); [land.py](/src/forge/land.py:37).
    Case: normal use - Six ready changes edit different lines of the same file. The stated five-item limit leaves one outside the single shared run promised for every overlapping item.
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

19. Advisory: Plan gap: an even-sized sample has no single median pull request.
    Raise: Plan gap — [plan](/plans/FORGE-CITIME-1.md:80); [doctor.py](/src/forge/doctor.py:313).
    Case: normal use - With 20 measured pull requests, the median can fall between the tenth and eleventh times. The plan does not say which pull request supplies “the slowest job of the median one.”
    Gain 3, Work 1, Harm 2
   Disposition: keep - below the bar (follow-up)

## Round 2

20. Blocking: Unproven: item 3: the live proof can run every API file serially.
    Raise: Test — [plan](/plans/FORGE-CITIME-1.md:95); [worker cap](/src/forge/node_workers.cjs:5).
    Case: normal use - On a busy laptop, `forge test` can allocate one CPU, which limits Vitest to one worker. The live test inherits that limit, so all three runs can pass serially after `fileParallelism: false` is removed. The [shared invite-log lookup](/src/forge/templates/starter/apps/api/test/helpers.ts:34) can take another file’s token when the files do run concurrently.
    Gain 3, Work 2, Harm 3
    Disposition: cut - STARTER's live proof forces `--maxWorkers=2` or more, and the invite-log helper reads only its own file's data by a per-file key (builders' section only).

21. Blocking: Unproven: item 3: the new shared-settings test can miss an indirect browser run.
    Raise: Test — [plan](/plans/FORGE-CITIME-1.md:94); [Python test script](/src/forge/templates/starter-python/scripts/test.mjs:59).
    Case: normal use - A `package.json` change selects everything. If the browser-install step is removed but the existing `pnpm test` fallback remains, `--list` prints only `pnpm test`; the proposed absence checks pass even though that [package script](/src/forge/templates/starter-python/package.json:17) runs `test:browser`.
    Gain 3, Work 2, Harm 3
    Disposition: cut - the browser check now follows the `package.json` scripts that each listed command runs, so `pnpm test` reaching `test:browser` fails it (builders' section only).

22. Advisory: Not done: a test group reported as cancelled at its time limit is omitted from CI time.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:70); [checks.py](/src/forge/checks.py:287).
    Case: normal use - Forge already recognizes a test job cancelled near its time limit as timed out. The new calculation discards every cancelled run, so it can omit that group’s time and fail to name it as timed out, contrary to the accepted limit.
    Gain 3, Work 2, Harm 3
    Disposition: cut - a cancelled test job that ran to its time limit counts in the CI time, marked timed out, using `checks._tests_timeout`'s rule (builders' section only).

23. Advisory: Not done: the lockfile check omits `Pipfile.lock`.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:75); [fasttest.py](/src/forge/fasttest.py:402).
    Case: normal use - A grouped Python repo changes `Pipfile.lock` and one code file. Forge recognizes that lockfile as a shared test input, but the planned list does not, so the change runs one group despite the promise to run all groups for a lockfile change.
    Gain 3, Work 2, Harm 3
   Disposition: keep - Owner accepted read round 2: notes 20 and 21 and advisory 22 fixed in the builders' section

24. Advisory: Not done: cancelled pushes can move the five-push window too far back.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:70); [workflow concurrency](/src/forge/prcheck.py:52).
    Case: normal use - A new push cancels an earlier push before any of its jobs finish. Because that push has no counted check, the proposed selection skips it and can report a slower run from before the last five pushes.
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

25. Advisory: Unproven: item 2: the group test does not check the runner’s group count.
    Raise: Test — [plan](/plans/FORGE-CITIME-1.md:90); [workflow](/src/forge/prcheck.py:85).
    Case: normal use - The matrix can start only group 1 while `FORGE_GROUPS` still says 2. The proposed test checks the matrix and gate, so it can pass while the runner executes only the first half of the selected tests and the required check passes.
    Gain 3, Work 2, Harm 3
   Disposition: keep - Owner accepted read round 2: notes 20 and 21 and advisory 22 fixed in the builders' section

26. Advisory: Not done: external checks are counted as GitHub runner minutes.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:70); [checks.py](/src/forge/checks.py:515).
    Case: normal use - A pull request also has a check posted by an external scanning app. The planned sum includes that check’s elapsed time even though it did not use a GitHub Actions runner, overstating the reported runner minutes.
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

27. Advisory: Plan gap: TIME can start before the record-commit fix that changes the same module.
    Raise: Plan gap — [task table](/plans/FORGE-CITIME-1.md:104); [task admission](/src/forge/task.py:619).
    Case: normal use - The local issue 1656 fix is still working and changes `checks.py`, which TIME also owns. The plan says that fix goes first but gives TIME no dependency on it; Forge’s started-work overlap check scans task branches, not fix branches.
    Gain 4, Work 1, Harm 2
   Disposition: keep - Owner accepted read round 2: notes 20 and 21 and advisory 22 fixed in the builders' section

## Round 3

28. Blocking: Not done: grouped CI jobs lack their own test setup.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:88); [workflow](/src/forge/prcheck.py:82).
    Case: normal use - GitHub runs each matrix group on a separate runner. The plan runs package installation and the Docker stack only in group 1, so group 2 has neither the installed test tools nor the API and database its tests need. The required check fails for a grouped run.
    Gain 5, Work 3, Harm 3
    Disposition: cut - fixed in the builders section: every group runs its own setup (install, Prisma generate, the Docker stack); only lint, type check, build and the health check run in group 1.

29. Blocking: Not done: the shared web configuration breaks new Python starter apps.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:85); [init.py](/src/forge/init.py:202).
    Case: normal use - Python starter apps copy the TypeScript starter’s web Vitest configuration, but their scripts come from `starter-python`. The planned configuration references the new sequencer, which is added only to the TypeScript starter, so the Python app cannot load its web test configuration.
    Gain 5, Work 2, Harm 3
    Disposition: cut - fixed in the builders section: the sequencer is set only in the TypeScript starter's configs; the Python starter gets an unchanged copy of today's web config under `starter-python`, which overrides the copied file.

30. Blocking: Unproven: item 3: the proposed two-worker override can still be capped to one.
    Raise: Test — [plan](/plans/FORGE-CITIME-1.md:108); [worker cap](/src/forge/node_workers.cjs:19).
    Case: normal use - When the live test inherits a one-CPU Forge allocation, the Node preload rewrites an explicit `--maxWorkers=2` to `--maxWorkers=1`. The proposed proof can therefore still run all three times serially.
    Gain 3, Work 2, Harm 3
    Disposition: cut - fixed in the builders section: the live API run passes `--maxWorkers=2` and sets `FORGE_TEST_CPUS=2`, so Forge's worker cap cannot lower it to one.

31. Advisory: Unproven: item 5: the test never runs the timings refresh command.
    Raise: Test — [plan](/plans/FORGE-CITIME-1.md:111); [API test helper](/src/forge/templates/starter/apps/api/test/helpers.ts:7).
    Case: normal use - On a clean developer machine, a refresh that starts the API tests without their Docker stack cannot reach the test API. The planned test exercises placement and command listing, so it can pass while the documented refresh command fails.
    Gain 3, Work 3, Harm 2
    Disposition: cut - fixed in the builders section: the refresh is `node scripts/test.mjs --timings`, the starter's own full run with its Docker stack, so no separate script can miss the stack; the builder seeds the timings with it.

32. Advisory: Unproven: item 5: the test never runs Vitest with the new sequencer.
    Raise: Test — [plan](/plans/FORGE-CITIME-1.md:111); [starter configuration](/src/forge/templates/starter/apps/web/vitest.config.ts:14).
    Case: normal use - The placement helper and `--list` can pass even if the Vitest configuration does not load the sequencer. A grouped run would then use Vitest’s existing file-count split instead of recorded times.
    Gain 3, Work 3, Harm 3
    Disposition: cut - fixed in the builders section: the live run runs `--group 1/2` and `--group 2/2` and checks that the API files split into the whole set with none twice, which needs the sequencer loaded.

33. Advisory: Plan gap: the existing-app guide omits the wiring needed for timed groups.
    Raise: Plan gap — [plan](/plans/FORGE-CITIME-1.md:90); [group warning](/src/forge/quicktest.py:19).
    Case: normal use - An existing app follows the listed copy steps, but they do not include registering the sequencer in its Vitest configuration or adding group placeholders to its Forge commands. Copying the listed files alone does not enable timed groups.
    Gain 3, Work 2, Harm 2
    Disposition: cut - fixed in the builders section: the existing-app guide step now names registering the sequencer, `--shard` on each Vitest run, the `{group}`/`{groups}` placeholders, per-group setup and a refresh command.

34. Advisory: Not done: placement starts over for each affected project.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:84); [starter test script](/src/forge/templates/starter/scripts/test.mjs:65).
    Case: normal use - A change selects two library projects, each with one timed test file. The script starts Vitest separately for each project, so each placement starts with empty group totals and can assign both files to the same group. The groups can remain uneven even with current timings.
    Gain 3, Work 3, Harm 2
    Disposition: keep - each Vitest run balances its own files by time, so each project's split is even; balancing across projects needs one placement shared between separate Vitest runs, which is more code than the gain while the starter has few projects; the group time line shows it if it matters.

35. Advisory: Plan gap: doctor may lack the workflow needed to recognize an old timeout.
    Raise: Plan gap — [plan](/plans/FORGE-CITIME-1.md:74); [timeout check](/src/forge/checks.py:298).
    Case: normal use - In a fresh clone after squash merges, old pull-request commits need not exist locally. The reused rule reads each commit’s workflow with `git show`; when that commit is absent, it cannot identify a cancelled job at its time limit.
    Gain 3, Work 2, Harm 2
    Disposition: keep - when an old commit's workflow cannot be read, the cancelled run is left out as before; this needs a fresh clone, a squash merge and a time-limit cancel together, and the timed-out group still shows in the close line on the machine that ran close.

36. Advisory: Unproven: item 3: password-reset tests still read each other’s log events.
    Raise: Test — [API test](/src/forge/templates/starter/apps/api/test/api.e2e-spec.ts:7); [organisation test](/src/forge/templates/starter/apps/api/test/organisations.e2e-spec.ts:111).
    Case: normal use - Parallel files request password resets against the same API. Both look for the latest reset link in its shared log, so one can take the other file’s token. Three passing live runs do not establish that this ordering cannot occur.
    Gain 3, Work 2, Harm 3
    Disposition: cut - fixed in the builders section: the per-file key applies to every lookup of a link in the shared log, including password-reset links.

37. Advisory: Plan gap: an existing starter test still requires the old init command.
    Raise: Plan gap — [task table](/plans/FORGE-CITIME-1.md:123); [starter test](/tests/test_starter_app.py:62).
    Case: normal use - TIMEGROUPS changes the new TypeScript starter’s `test` setting to include `--group`, while this existing test asserts that the setting equals the old command. The task does not identify that assertion for update, so the full test suite fails after the planned change.
    Gain 4, Work 1, Harm 2
    Disposition: cut - fixed in the builders section: TIMEGROUPS updates the `COMMAND` assertion in `tests/test_starter_app.py:62` and has that file in its Scope and Tests.

## Round 4

38. Blocking: Plan gap: the grouped-run test still requires group 2 to skip Docker.
    Raise: Plan gap — [setup rule](/plans/FORGE-CITIME-1.md:88); [test](/plans/FORGE-CITIME-1.md:111).
    Case: normal use - For an API change, group 2 must start its own Docker stack, but the required `--list` test asserts that group 2 has no Docker step. A correct implementation cannot pass that test.
    Gain 5, Work 1, Harm 3
   Disposition: keep - Owner accepted read round 3: notes 28-30 fixed in the builders' section

39. Blocking: Plan gap: STARTER’s live proof requires the later TIMEGROUPS task.
    Raise: Plan gap — [live proof](/plans/FORGE-CITIME-1.md:108); [task order](/plans/FORGE-CITIME-1.md:123).
    Case: normal use - STARTER must pass its live test with `--group 1/2` and `--group 2/2`, but TIMEGROUPS adds that option and cannot start until STARTER finishes.
    Gain 5, Work 2, Harm 3
   Disposition: keep - Owner accepted read round 3: notes 28-30 fixed in the builders' section

40. Advisory: Unproven: item 5: the live split can pass without the new sequencer.
    Raise: Test — [plan](/plans/FORGE-CITIME-1.md:108); [pinned Vitest](/src/forge/templates/starter/package.json:60).
    Case: normal use - Vitest’s existing file-count sharding also divides the files between two groups with none repeated. The new union check therefore passes if the custom sequencer is never loaded.
    Gain 3, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)

41. Advisory: Plan gap: the Python starter copy test requires two different web configurations.
    Raise: Plan gap — [plan](/plans/FORGE-CITIME-1.md:85); [Python starter test](/tests/test_python_starter.py:69).
    Case: normal use - The override makes the Python app’s web configuration differ from the TypeScript one. The existing test checks the first commit against both the Python starter files and every file in the TypeScript `apps/web` tree, so it fails after the planned change.
    Gain 4, Work 2, Harm 2
   Disposition: keep - Owner accepted read round 3: notes 28-30 fixed in the builders' section

42. Advisory: Scale: grouped nightly runs can repeat the whole browser suite.
    Raise: Scale — [full-run matrix](/src/forge/prcheck.py:326); [starter script](/src/forge/templates/starter/scripts/test.mjs:80).
    Case: normal use - Each nightly group runs without a base, and the plan shards Vitest runs but gives no group rule for the browser suite. The existing no-base path selects the whole browser suite in every group.
    Adds work: run the browser suite in one group; F 2 x H 2 = 4; 2 x C = 2
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

43. Advisory: Plan gap: each group’s Docker setup still builds the app.
    Raise: Plan gap — [plan](/plans/FORGE-CITIME-1.md:88); [Dockerfile](/src/forge/templates/starter/Dockerfile:19).
    Case: normal use - Each fresh runner starts its own stack, whose image runs the full app build. The plan’s statement that build runs only in group 1 therefore does not cover the repeated container builds.
    Adds work: avoid rebuilding the test image on each runner; F 2 x H 2 = 4; 2 x C = 6
    Gain 2, Work 4, Harm 2
   Disposition: keep - below the bar (live with)

## Round 5

44. Blocking: Not done: Vitest rejects more groups than API test files.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:89); [API config](/src/forge/templates/starter/apps/api/vitest.config.ts:5); [Vitest 3.2.4](https://github.com/vitest-dev/vitest/blob/v3.2.4/packages/vitest/src/node/pool.ts#L207-L219).
    Case: normal use - A new app sets `groups = 16` for 16 runner slots. The starter has 15 API test files, and its API config does not enable `passWithNoTests`. On a shared-settings change, every group passes `--shard` to the API suite; Vitest rejects the group count before calling the planned sequencer. The required check fails even when all tests pass.
    Gain 5, Work 2, Harm 3
    Disposition: cut - fixed in the builders section: each Vitest run under groups counts its files and caps the group count at that number; a group above the file count skips that run and passes; the TIMEGROUPS test covers it.

45. Advisory: Not done: a test-only change can bypass the new `.forge` exception.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:80); [test-only classifier](/src/forge/templates/review-tests.py:55).
    Case: normal use - A pull request changes an existing Python test and `.forge/review-tests.py`. The test-only classifier excludes `.forge/` and can return true. Although the new small-change check returns false, `tests_only or small` still selects one group, contrary to the new all-groups exception.
    Gain 3, Work 2, Harm 3
    Disposition: cut - fixed in the builders section: `one-group` is false whenever the shared check (Forge's picker script, CI files, lockfiles, shared settings) holds, also for a test-only change; the GROUPS test has that case.

46. Advisory: Not done: the selection stage excludes the actual test picker.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:76); [picker](/src/forge/fasttest.py:793).
    Case: normal use - Forge’s own CI runs the Python test picker inside the `forge test --change` job step. The proposed calculation counts that entire step as tests, so time spent selecting files appears as test time. A slow picker can therefore lead the owner to investigate the wrong stage.
    Gain 3, Work 3, Harm 2
    Disposition: cut - fixed in the builders section: the test step's stage is named `tests (with in-step selection)`, so picking inside the test command is not hidden as pure test time.

47. Advisory: Not done: setup after `parent-tests` is absent from the stage totals.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:76); [workflow](/src/forge/prcheck.py:103).
    Case: normal use - The generated workflow restores caches, sets up Node and installs Forge after `parent-tests`. The plan counts setup only before that step and counts the test step separately, leaving those setup minutes out. A group can exceed ten minutes without receiving its over-budget line.
    Gain 3, Work 2, Harm 2
    Disposition: cut - fixed in the builders section: setup counts every step except `parent-tests` and the test step, including those after `parent-tests`.

48. Advisory: Not done: the jobs request can omit groups after a rerun.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:76); [GitHub jobs endpoint](https://docs.github.com/en/rest/actions/workflow-jobs#list-jobs-for-a-workflow-run).
    Case: normal use - A 16-group workflow is rerun in full. The requested endpoint includes both attempts but returns 30 jobs per page by default. One request cannot return all their jobs, so the report can omit a group’s stages or its over-budget line.
    Gain 3, Work 2, Harm 2
    Disposition: cut - fixed in the builders section: the jobs request asks for 100 per page and is read with `gh api --paginate`.

49. Advisory: Unproven: item 4: the selection-chain test can pass when no tests run.
    Raise: Test — [plan](/plans/FORGE-CITIME-1.md:108); [Python starter](/src/forge/templates/starter-python/scripts/test.mjs:68).
    Case: normal use - For a web change, `--list` prints the Vitest command without executing it. That command uses `--changed` and `--passWithNoTests`, so the proposed assertion can pass even when Vitest selects no files for the change.
    Gain 3, Work 2, Harm 3
    Disposition: cut - fixed in the builders section: the live chain run executes the inner picker and fails unless Vitest reports at least one test ran.

50. Advisory: Not done: the request count no longer matches the stated cost.
    Raise: Not done — [cost](/plans/FORGE-CITIME-1.md:16); [stage calculation](/plans/FORGE-CITIME-1.md:76).
    Case: normal use - A successful close needs the new GraphQL request for push history and a separate jobs request for stages. Doctor also needs the history request and at least one jobs request. The stated cost of one additional request each understates the GitHub traffic.
    Gain 2, Work 1, Harm 2
    Disposition: cut - the cost line now says close makes two more GitHub requests and doctor two or three.

## Round 6

51. Blocking: Not done: zero discovered files make every group skip the suite.
    Raise: Not done — [plan](/plans/FORGE-CITIME-1.md:89); [Vitest’s list command](https://github.com/vitest-dev/vitest/blob/v3.2.4/packages/vitest/src/node/cli/cac.ts#L309-L337).
    Case: normal use - A change to the API Vitest configuration accidentally makes its include pattern match no files. `vitest list --filesOnly` returns an empty list, so every group number is above the file count and every group skips the API run. The required check can pass with no API tests, where the current API configuration would fail.
    Gain 5, Work 2, Harm 4
    Disposition: keep - the owner's group rule (18 Nov 2026), now in TIMEGROUPS, STARTER and the existing-app recipe: a run that discovers zero files fails with one clear line, so no group can pass without the suite.

52. Blocking: Not done: an untimed file can leave an active group empty.
    Raise: Not done — [placement and group cap](/plans/FORGE-CITIME-1.md:85); [Vitest’s empty-run result](https://github.com/vitest-dev/vitest/blob/v3.2.4/packages/vitest/src/node/test-run.ts#L79-L110).
    Case: normal use - An app has 16 groups, 15 recorded API test files and one new untimed file. If the new path hashes to a group already holding a recorded file, another group gets no files. The count is still 16, so no group is skipped by the cap; Vitest fails the empty group and the required check turns red.
    Gain 5, Work 2, Harm 3
    Disposition: keep - the owner's group rule (18 Nov 2026): files are placed only across the groups in use, and untimed files fill any empty group first, so no group in use is empty.

53. Blocking: Plan gap: the existing-app recipe omits the new group limit.
    Raise: Plan gap — [starter limit](/plans/FORGE-CITIME-1.md:89); [existing-app instructions](/plans/FORGE-CITIME-1.md:92); [Vitest 3.2.4](https://github.com/vitest-dev/vitest/blob/v3.2.4/packages/vitest/src/node/pool.ts#L207-L219).
    Case: normal use - An existing app with 16 runner slots and 15 API test files follows the guide. It copies the sequencer and passes the uncapped group count directly to Vitest. Vitest rejects the count before calling the sequencer, so the required check fails. The new cap exists only in the starter script, which the recipe does not copy.
    Gain 5, Work 2, Harm 3
    Disposition: keep - the owner's group rule (18 Nov 2026) is now in the existing-app recipe too: each run uses at most as many groups as it has files, extra jobs pass with nothing to do, zero files fail, no group in use is empty.
