# Tests run once per change, in one place per repo, and CI is optional

3 parts · Risks: none · New moving parts: a nightly scheduled job in the generated GitHub workflow

## What changes for you

- Each repo picks one place for its change tests: its CI, or the laptop. A repo with no GitHub CI can ship, with an empty checks list. Close's clean review and its laptop test result are then the merge gate. A repo with CI no longer runs the tests twice.
- Each change runs only its related tests plus lint and type checks, in that one place. The pull request's CI run does the same, not the full suite.
- A repo can split its CI tests into several parallel jobs with one setting, for any test runner. A large suite then fits in the job's time limit: four jobs run a 2,300-test suite in about 8 to 10 minutes.
- The full suite runs nightly on main, in a scheduled GitHub workflow where the repo has CI, or on the laptop when it is quiet. A failed night opens a fix that names the failing tests.
- A release or a client sign-off waits for a green full run on the current main. Everyday merges never wait for it.
- Setup asks once whether the repo runs GitHub Actions. Yes gives CI tests, no gives laptop tests; your agent can answer from the repo's settings. Existing repos move to the new setting on upgrade: CI when their settings name checks, the laptop when they name none. The upgrade message says so, and the settings file can switch back.

Design: none (no screens; it changes how close, merge, the generated CI and the release gates run tests)

## Why

Every change runs its tests twice, on the laptop at close and again in the pull request's CI with the full suite, close refuses an empty checks list, and the merge waits for CI, so a repo without GitHub CI cannot ship.

## Done when

1. **A repo set to test on the laptop, with no GitHub CI and an empty checks list, closes and merges a change on its laptop test result and a clean review. Close and merge do not wait for GitHub checks.**
2. **Each change runs its related tests and the lint and type checks in the repo's test command once, in the chosen place: on the laptop at close, or in the pull request's CI, split across as many parallel jobs as the settings name, for any test runner. It runs every test only when it changes a shared test input, such as a lock file or a shared test fixture.**
3. **The full suite runs nightly on main: in a scheduled GitHub workflow in a CI repo, or on the laptop in a laptop repo, where Forge asks for it once a day and the agent runs it when the machine is quiet.**
4. **A failed full run opens a fix that names the failing tests.**
5. **A release tag push or a client sign-off is refused until the latest commit on main has a green full run. Everyday merges never wait for it.**
6. **Setup asks once whether a new repo runs GitHub Actions: yes gives CI tests, no gives laptop tests. Existing repos move on upgrade: CI when their checks list names checks, the laptop when it is empty. The upgrade says so, and the settings file can switch back.**

## Risks

Risks: none

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

### Shared names

- **The setting (pinned by SETTING).** `test_place` in forge.toml, values `"ci"` and `"local"`,
  read as `repo.config(top)["test_place"]` (and `repo.default_config(top)["test_place"]` in
  merge). Add it to `repo.KEYS` (str) and `repo.CHOICES`. When forge.toml does not write it,
  `_config_text` derives it: `"ci"` when `checks` is non-empty, else `"local"`. It is not a
  forge.local.toml key.
- **`forge test --change` (pinned by CISEL).** A flag on the existing `forge test` command
  (fasttest.COMMANDS; no new command, so the ceiling of 25 in tests/test_rules.py holds). It runs
  exactly the run close makes in a local repo: `review.test_run(top, review.close_test(top, base),
  base)` with `base = origin/<default>`, and prints the same report. It uses bare `forge test`'s
  missing-base refusal unchanged.
- **The groups setting (pinned by CISEL).** `groups` in forge.toml, a whole number of 1 or more,
  `repo.KEYS` int, checked like the other keys. When forge.toml does not write it, the default is
  today's automatic rule in `prcheck.ships()`: 6, with `--splits {groups} --group {group}` added to
  a direct pytest `test` command, when the repo lists pytest-split; else 1. Written `groups`
  replaces that rule and adds no suffix. Forge fills `{group}` and `{groups}`
  in `test` and `fast_test` wherever it runs them (close, workers' `forge test`, `--change`,
  `--full`, the picker's own reads of `test`), from the `FORGE_GROUP` and `FORGE_GROUPS`
  environment variables, and with 1 and 1 when they are unset. One helper does it, beside the
  existing `{base}` fill.
- **The full-run fact (FULLRUN).** A GitHub commit status with context `forge-full-suite` on the
  tested commit of main, state `success` or `failure`. Only the release and sign-off gates read
  it. GitHub holds the fact; Forge writes no record of it.

### Done-when details

1. Local mode in close (src/forge/close.py): the `no_checks` refusal applies only when
   `test_place` is `"ci"`; reword it to say that forge.toml runs change tests in CI but names no
   checks, with the next step to name the checks or set `test_place = "local"`. In local mode
   close runs the tests alongside the review as today, then skips `checks.wait`. The steps after
   the wait stay (mark the draft ready, bring in main again, rerun close if HEAD moved). The Ready
   line says the change has a clean review and its tests passed on this machine.
   Merge (src/forge/merge.py) skips `checks.wait` when the default branch's `test_place` is
   `"local"`; its existing BEHIND/DIRTY handling after `gh pr merge` stays the conflict path.
   Doctor (src/forge/doctor.py, about line 393) prints its no-checks line only in CI mode. Land
   needs no change: it goes through close and merge.
   Known limit, no guard: a local repo whose branch protection still requires checks gets
   GitHub's own refusal at merge until its checks are emptied.
   Test `tests/test_testplace_settings.py::test_1_local_repo_ships_without_ci` (platform mark): a
   repo with `test_place = "local"`, `checks = []` and `merge = "agent"` closes a fix: the test
   command runs once, the stub review is clean, close prints Ready, and the stub gh log has no
   check-runs, statuses or `pr checks` call from close or merge; `forge merge` merges;
   `forge doctor` prints no no-checks line. The existing refusal case `_no_checks_named` in
   tests/test_close.py sets `test_place = "ci"` and asserts the new wording.
2. One place per change.
   - CI mode in close (SETTING): close never calls `review.test_run`, including the
     rerun-failed-tests and already-passed branches; it drops any `tests` left in the item state;
     the review prompt's `tested=` text says CI runs the change's related tests on the pull request
     and close waits for them after the review.
   - CI mode for workers (SETTING): workers in a CI repo do not run the change's tests before they
     stop. src/forge/templates/brief.md line 243's run step becomes a `$test_step` placeholder that
     src/forge/worker.py fills by `test_place`; worker.py's session brief line (about line 598) and
     `COMMIT_NUDGE` take the same two texts. Local: as today. CI: commit your work; the pull
     request's CI runs the change's related tests, lint and type checks, so do not run them here;
     run `forge test` only for a test you are writing, to watch it fail. The skill's continued-round
     paragraph (src/forge/templates/skill.md, about line 1266) says the same.
   - Selection (CISEL): `review.close_test(..., closing=True)` uses the picker whenever
     `fast_test` is empty, in both modes (drop the `"tests" in cfg["checks"]` condition). Remove
     `FORGE_CLOSE_TESTS` from `review.test_run` and the large-selection skip (`fasttest.LARGE` and
     its `closing` branch in `pytest_tests`): no full suite runs behind it any more, so a broad
     selection runs. Shared test inputs (conftest, lock files, requirements, pyproject outside its
     harmless keys) still run every test: that is the exception Done-when 2 names. Change the texts
     that promise CI's full suite (the `review.GAP` line in `pytest_tests`, the worker
     broad-selection line) to say the nightly full run covers the rest.
   - Lint and type checks (CISEL): no new setting; they are the parts of `test` or `fast_test` that
     are not a test runner. Today `pytest_tests` returns before it runs the command when no test is
     picked (fasttest.py about line 478), so those parts never run. Change that one return: with
     nothing picked, run each `&&` part of the command that `quicktest.test_parts` does not class as
     `python`, in order, stop at the first failure, and return its status; print that no test was
     picked. A command the picker cannot narrow (a script such as the starter's
     `node scripts/test.mjs`, or Go) still runs whole unless `fast_test` is set, as today; the skill
     says so.
   - Generated CI (CISEL, src/forge/prcheck.py `WORKFLOW` and `ships()`): in CI mode the `tests`
     job installs the Forge release the checked-out forge.toml pins (`uv tool install .` in Forge's
     own repo, `sync.install_line` otherwise) and runs `forge test --change` in place of the `test`
     command. Its matrix has `groups` jobs, each with `FORGE_GROUP` set to its matrix number and
     `FORGE_GROUPS` to `groups`, so a command such as `vitest run --shard={group}/{groups}` or
     `pytest --splits {groups} --group {group}` runs one shard per job. The automatic pytest-split
     rule stays as the default (shared names), so a repo with six groups today keeps six, Forge's
     own repo included; only the mechanism becomes general. A group whose shard of the related
     tests is empty passes, as today's exit-status-5 handling does; check that the picker's
     deselection runs before pytest-split's split. With 1 group there is one job. Keep the
     docs-check job, the parent-tests reuse, the Node setup, the Node 30-minute timeout, the
     `tests-passed` job and the one required `tests` check name. On a `windows-*` runner keep the
     PowerShell retry wrapper around `forge test --change`; the test command inside it runs the way
     close runs it on Windows. In local mode the workflow has no tests jobs, whatever `checks`
     says. Doctor's workflow check (doctor.py about line 425) accepts the new step: in CI mode with
     a `tests` check, the workflow must contain `forge test --change`; drop its `--splits` form.
     Forge's own `.github/workflows/forge.yml` is regenerated by sync.
   Test `tests/test_testplace_selection.py::test_2_change_tests_run_once_in_one_place` (platform
   mark), one repo with two Python test files and a `test` command of
   `<lint script> && pytest tests` where the lint script writes a marker: (a) CI mode: close runs
   no test command (no marker, no pytest run), waits for checks, and the worker brief tells the
   worker not to run the change's tests; (b) local mode, a changed module one test names: close
   runs the lint part and only that test file; (c) a changed source file no test names: close runs
   the lint part, no pytest, and a failing lint fails the run; (d) `forge test --change` in the
   same tree runs the same selection as close; (e) a change that selects more than a third of the
   test files still runs them; (f) the generated forge.yml in CI mode has one tests job whose run
   step is `forge test --change` and no `--splits`, `forge doctor` accepts it, and in local mode it
   has no tests job; (g) with `groups = 4` and a `test` command of `<shard script> {group}/{groups}`
   (any runner; the script records its argument), the generated forge.yml has four matrix jobs
   with `FORGE_GROUP` 1 to 4 and `FORGE_GROUPS` 4, `FORGE_GROUP=2 FORGE_GROUPS=4 forge test --change`
   runs the script with `2/4`, and a local close runs it with `1/1`. Adopted case: in the upgrade test
   (item 6) an adopted client with a direct pytest command and pytest-split listed keeps six
   matrix jobs after the upgrade with no forge.toml edit, and the same client with `groups = 3`
   written gets three.
   Tests CISEL changes: delete tests/test_close_skips_large_test_selections.py (its rule is gone);
   adjust tests/test_close_always_tests.py (line 81), tests/test_close_names_untested_source_files.py,
   tests/test_close_runs_only_related_tests.py, tests/test_lanes_tests.py and
   tests/test_worker_tests_stay_bounded.py for the new texts; existing workflow tests that assert
   the automatic six groups keep passing; tests that assert the old run line (for example
   tests/test_ci_reuses_tested_trees.py and tests/test_ci_limits_pull_requests_to_linux.py) and
   doctor's workflow-check tests change to the `forge test --change` step. Tests SETTING changes: add `test_place = "local"` to the forge.toml of each existing
   test that expects close to run tests locally (among them tests/test_close.py, tests/test_land.py,
   tests/test_fix_close_skips_tests_for_docs_only_changes.py, tests/test_docs_only_test_checks.py,
   tests/test_fix_close_reruns_the_full_test_command_even.py, tests/test_run_records.py and the
   pytest-picker tests), and update worker-brief tests that match the old run line. Name each in
   the handoff.
3. `forge test --full` (FULLRUN, new module src/forge/fullrun.py; fasttest.py only adds the flag
   and calls it). It fetches the default branch once and refuses, each with one plain line, when
   HEAD is not `origin/<default>`'s commit (the full run records its result on main's latest
   commit; Next: `git switch <default> && git pull`, then `forge test --full`) or when
   `git status --porcelain` shows any change (the run must test only committed files; Next: commit
   or set aside the changes, then `forge test --full`). It then runs forge.toml's `test` whole
   through `review.test_run(..., always=True)`, so it waits in the machine's one test lane (that is
   "when the machine is quiet"). It posts the status (shared names) on that commit with
   `gh api --method POST repos/{owner}/{repo}/statuses/<sha>`, with `target_url` set to the Actions
   run when `GITHUB_RUN_ID` is set, and exits with the test command's status. With no `test`
   command it says so and exits 0, as bare `forge test` does.
   Nightly in CI mode (prcheck.py `WORKFLOW`): add `schedule` (one fixed daily cron) and
   `workflow_dispatch` triggers and a `full-suite` job that runs only on those events, with
   `statuses: write` and `GH_TOKEN`: checkout with full history, the same setup steps as the tests
   job, install the pinned Forge, run `forge test --full`. The existing jobs run only on pull
   request events; check that each `if:` still excludes the new events. Local mode gets no
   schedule.
   Daily ask in local mode (src/forge/nextstep.py, one call beside `upgrade.release_notice`):
   `fullrun.notices(top) -> list[str]` reads the newest `forge-full-suite` status on the last 30
   commits of the default branch in one `gh api graphql` call (`{owner}`/`{repo}` placeholders).
   When `test_place` is `"local"` and there is no run, or the newest is over 24 hours old, it adds
   one line: the daily full run on main is due; when this machine is quiet, run `forge test --full`
   in the main checkout. Any gh failure gives no lines and never blocks next, as the release notice
   does. Ceiling: a run older than 30 commits counts as none.
   Test `tests/test_testplace_fullrun.py::test_3_full_run_is_nightly_and_daily` (platform mark):
   local repo, the stub GraphQL answers no run: next shows the due line; `forge test --full` on
   main's commit runs the whole command (a test outside any selection runs) and posts `success`;
   with a run 2 hours old next shows no line, 25 hours old it shows it; a CI-mode repo never shows
   it; `forge test --full` on a task branch, and on main with an uncommitted edit, is refused with
   the lines above and posts nothing; CI mode's generated forge.yml has the schedule,
   `workflow_dispatch` and a `full-suite` job running `forge test --full` with `statuses: write`,
   and local mode's has none. Adopted case: the adopted-release client (fixture as in item 6)
   upgraded with `checks = []` shows the due line and its full run posts `success`; upgraded with
   its checks, sync's forge.yml gains the `full-suite` job.
4. A failed full run gives one fix command, with every failing test, by one path per mode.
   - CI mode: the nightly `full-suite` job is a scheduled run of forge.yml, so the existing
     scheduled-run report (`nextstep._failed_schedules`, fed by `board_facts.failed_schedules`,
     which reads the failed job's log for the failing pytest tests) names the failing tests and the
     `forge fix start` command, and claims an open fix whose why names `(forge.yml)`. FULLRUN adds
     nothing to it; `fullrun.notices` prints no fix line.
   - Local mode: `forge test --full` reads every failing id from the results file
     `review.test_run` already fills (`review.results_path`; lines `failed <nodeid>` and
     `error <nodeid>`), prints them all, and prints the fix to start with every id in the why:
     `forge fix start "The full test run on main failed: <ids>" --done "The full test run passes on
     main"`. With no names (a non-pytest runner) the why says the full test run failed and the
     output names the log. The status description is only a short summary for the gates.
   Test `tests/test_testplace_fullrun.py::test_4_failed_full_run_opens_a_fix` (platform mark):
   local mode, a full run with thirteen failing tests posts `failure`, prints all thirteen ids and
   the command; running the command starts the fix with that why. CI mode: a stub failed scheduled
   forge.yml run makes `forge next` print exactly one `forge fix start` line, naming its failing
   tests. Adopted case: the upgraded adopted client in local mode prints the same command from a
   failing full run.
5. Gates. Both read `fullrun.green(top) -> str`: empty when main's latest commit, as just fetched,
   has a `success` status; otherwise the reason (no full run, or it failed). The next step names
   the way to get a run: `gh workflow run forge.yml --ref <default>` in CI mode, `forge test --full`
   in the main checkout in local mode.
   - Release: `forge hook pre-push` (src/forge/githooks.py) refuses a push of `refs/tags/<tag>`
     whose tag name matches `releases.VERSION` unless the tag's commit (`<sha>^{commit}`) is
     main's latest commit and `fullrun.green` is empty. Other tags and branch pushes are untouched.
   - Client sign-off: `forge decision accept` of a `client-signoff` record
     (src/forge/records.py, in the `if signed:` block) refuses on the same rule.
   - Merges: neither close nor merge reads the full-run status.
   Docs: docs/guide.md "Releasing Forge" step 2 asks for a green `forge.yml` full run
   (`gh workflow run forge.yml --ref main`) beside the existing `forge-next.yml` platform run.
   Test `tests/test_testplace_fullrun.py::test_5_release_and_signoff_wait_for_a_green_full_run`
   (platform mark): pushing tag `v1.0.0` is refused with no status, with a `failure` status and
   with the tag on an older commit, and goes through with `success` on main's latest commit; a
   non-release tag pushes freely; a client sign-off accept is refused without a green run and
   accepted with one; a `forge merge` while main's full run is red merges and its gh log has no
   statuses read. Adopted case: the upgraded adopted client's release tag push is refused without
   a green run. Existing sign-off accept tests (tests/test_approval.py, tests/test_aha_demo.py,
   tests/test_aha_review.py, tests/test_design_first.py and others that accept a client-signoff)
   add a stub `success` status; name each in the handoff.
6. New repos: `forge init` (new repo and adoption) takes a required `--actions yes|no` answer to
   "Does this repo run GitHub Actions?". The agent answers from what it sees, for example
   `gh api repos/{owner}/{repo}/actions/permissions` (`enabled`). `yes` writes `test_place = "ci"`
   with the checks as today. `no` writes `test_place = "local"` and `checks = []`; an adoption then
   adds no `forge-pr-check` and does not ask for `--checks`; branch protection still requires pull
   requests, and its printed line names no checks. A missing answer is refused before anything
   changes: a new repo with its own one-line refusal naming the question and the gh call, an
   adoption by adding `--actions` to the existing `answers` refusal's list. The skill's setup and
   "Adopt a live app" lines name the question. Existing init tests add `--actions yes`; name each
   in the handoff. Existing repos: no forge.toml rewrite; the
   derived value (shared names) applies. `forge sync` prints one line while forge.toml does not
   write `test_place` (read the file's raw TOML, not the derived config): it names the place Forge
   chose and why (the checks list is or is not empty), and the line to write to switch. The
   upgrade streams the new release's sync, so the upgrade output carries that line. Writing
   `test_place` stops the line. Forge's own forge.toml writes `test_place = "ci"`.
   Decision record (SETTING): `forge decision new test-place` (number 0107 today), filled and
   accepted with the owner's name, since he made these choices on 24 October 2026 (Notes). Front
   matter `stories: [FORGE-TESTPLACE-1]` and `supersedes: ""`: it supersedes 0092 only in part, and
   naming 0092 there would mark all of it superseded. Its Consequences say: "Supersedes in part:
   0092's 'CI is the proof' bullet (close runs tests in one place, CI or the laptop; the pull
   request runs related tests; the full suite runs nightly), its 'the full suite keeps running on
   every PR as a hard gate', and its consequences that local runs are not proof and that a repo
   whose CI runs no tests has no proof. 0092's review loop and the rest stand."
   Test `tests/test_testplace_settings.py::test_6_new_and_existing_repos_pick_a_test_place`:
   `forge init --actions yes` writes `test_place = "ci"` and today's checks; `forge init --actions
   no` writes `test_place = "local"` and `checks = []`, and a close there runs local tests and waits
   for no checks; an adoption with each answer writes the same; `forge init` with no answer is
   refused before it writes anything; writing `test_place = "local"` with `checks = []` later
   switches a CI repo's close to local tests. Upgrade test
   `tests/test_testplace_upgrade.py` (uses tests/fixtures/adopted-v1.2.2/client advanced to the
   previous release, as tests/test_lanes_upgrade.py does): with its checks the upgrade output says
   Forge runs change tests in CI, close runs no local tests and waits for checks, and the worker
   brief has the CI text; with `checks = []` it says the laptop, and close runs the tests and does
   not wait; every other forge.toml setting is unchanged. FULLRUN's adopted cases (items 3 to 5)
   reuse this test's setup helper.

### New and existing repos

- **New repos** (init or adoption): setup asks whether the repo runs GitHub Actions. Yes:
  `test_place = "ci"`, checks as today, and the generated workflow runs related tests on each pull
  request and the full suite nightly. No: `test_place = "local"`, `checks = []`, tests on the
  laptop and the daily full run there. Either can be switched in forge.toml.
- **Existing repos** (on upgrade): nothing to edit. Non-empty checks read as CI: close and
  workers stop their local runs, and after the upgrade's sync the pull request runs related tests
  and the nightly job appears. Empty checks read as local: close stops refusing and runs the tests
  on the laptop, and `forge next` asks for the daily full run. Sync's line says which, until
  forge.toml writes it. A repo with six automatic pytest-split groups today keeps six; `groups` in
  forge.toml can change the count.

### Guide and skill

- SETTING: the skill's continued-round paragraph (about line 1266) and the "## Closing" lines on
  close's checks wait and the empty-checks refusal; brief.md's `$test_step`.
- CISEL: the "## Closing" paragraphs on the picker, its large-selection skip, `always_test`, the
  no-selection run of lint and type checks and the generated workflow's test groups (about lines
  1508 to 1565) describe one place per repo, `forge test --change` and the `groups` setting; brief.md
  drops its "CI runs the full suite" wording and updates the Windows retry line; docs/guide.md's
  test section matches.
- FULLRUN: a short new skill section "## Full test run" covering `forge test --full`, the daily
  line in local repos, the two fix paths, and the release and sign-off gates; docs/guide.md's
  release step.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| SETTING | One test place per repo | The `test_place` setting and its derived default, the sync line, local close and merge with no check wait and no empty-checks refusal, CI close and CI workers with no local test run, init writing `test_place = "ci"`, the decision record, skill and brief lines | 1, 2, 6 | src/forge/repo.py, src/forge/close.py, src/forge/merge.py, src/forge/doctor.py, src/forge/init.py, src/forge/sync.py, src/forge/worker.py, src/forge/templates/brief.md, src/forge/templates/skill.md, docs/decisions/, forge.toml | tests/test_testplace_settings.py, tests/test_testplace_upgrade.py, plus the existing tests listed under item 2 for SETTING | | no | |
| CISEL | Related tests in the chosen place | The picker at close in both modes with the large-selection skip removed, lint and type checks run when no test is picked, `forge test --change`, the `groups` setting and its `{group}`/`{groups}` fill, the generated pull request tests job as a `groups`-wide matrix of `forge test --change`, doctor's workflow check, skill, brief and guide lines | 2 | src/forge/review.py, src/forge/fasttest.py, src/forge/prcheck.py, src/forge/doctor.py, src/forge/templates/skill.md, src/forge/templates/brief.md, docs/guide.md, .github/workflows/forge.yml | tests/test_testplace_selection.py, plus the existing tests listed under item 2 for CISEL | SETTING | no | |
| FULLRUN | Nightly full run and its gates | `forge test --full` and the full-run status, the nightly and on-demand job in the generated workflow, the daily line in `forge next`, the local fix line, the release tag and client sign-off gates, skill and guide lines | 3, 4, 5 | src/forge/fullrun.py, src/forge/fasttest.py, src/forge/prcheck.py, src/forge/nextstep.py, src/forge/githooks.py, src/forge/records.py, src/forge/templates/skill.md, docs/guide.md, .github/workflows/forge.yml | tests/test_testplace_fullrun.py, plus the existing sign-off tests listed under item 5 | CISEL | no | |

The parts run in a chain, and each edits files an earlier one touched only after it merges:
doctor.py, skill.md and brief.md (SETTING, then CISEL), fasttest.py, prcheck.py, docs/guide.md and
forge.yml (CISEL, then FULLRUN). CISEL needs SETTING's `test_place`; FULLRUN needs CISEL's workflow
and `forge test` flags. Module sizes: review.py is at 1,191 lines, so CISEL's changes there must be
net zero or less; close.py, nextstep.py and repo.py stay under 1,200.

New moving parts: a scheduled nightly job in the generated GitHub workflow (Done-when 3)

## Notes

- Owner decisions (24 Oct 2026, settled): one place per repo, `ci` or `local`, never both; local
  repos may have empty checks and merge on close's clean review and local tests; each change runs
  only related tests plus lint and type checks, and the pull request's CI does the same, reusing
  the picker; full suite nightly on main, in a scheduled workflow with CI or on the laptop when
  quiet, and a failure opens a fix naming the failing tests; a release or client sign-off waits
  for a green full run on current main, and everyday merges never do; new repos default by GitHub
  remote (refined 25 Oct: init asks whether the repo runs GitHub Actions), existing repos move on upgrade with a message and can switch back.
- Planner choices the owner did not make: (1) superseded by the owner's 25 Oct answer: init
  asks once whether the repo runs GitHub Actions (yes gives CI, no gives local); (2) existing repos read as CI when their checks list is
  non-empty, else local, so a repo that waits for its own checks today keeps waiting; (3) shared
  test inputs still run every test, as the picker does today; (4) lint and type checks stay part
  of the test command, with no new setting; (5) the full-run result is a GitHub commit status for
  the gates, and the fix comes from the existing scheduled-run report in CI or from
  `forge test --full`'s own output on the laptop.
- Owner decision (25 Oct 2026): CI test sharding for any runner through a `groups` setting; a
  client's 2,300-test vitest suite passed the job's 30-minute limit on a 2-core runner, and four
  shards take about 8 to 10 minutes. Existing repos keep their group count (six automatic pytest-split groups stay the default),
  and Forge's own repo keeps its six.
- Forge's own `.github/workflows/forge-next.yml` keeps its Windows platform subset on pull
  requests and its full runs on main merges, tags and its own nightly. It is Forge's own file; a
  separate fix can trim it.
- FORGE-LANES-1 has landed (agent lane, test lane, `forge test`); this story builds on its
  `review.test_run` lane and adds flags to its command.
