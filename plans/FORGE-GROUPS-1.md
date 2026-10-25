# Split any test runner's CI tests into parallel groups

2 parts · Risks: none · New moving parts: none

## What changes for you

- A client with a slow test suite on any runner, such as vitest or jest, can set the number of parallel test groups in forge.toml. The test command gets each group's number and the group count filled in, so the runner's own shard flag splits the tests.
- Each group runs only its share of the change's related tests. A group that gets no tests passes.
- A repo that gets the six automatic pytest groups today keeps six after upgrade. Its groups now run the change's related tests, not the full suite. A pytest repo that sets a different number gets the split without a change to its test command. A new repo starts with one group.
- A group never counts another group's pass as its own, also when the groups run one after another on one self-hosted runner.
- A test listed to always run passes or fails only in the group that runs it, and the other groups do not fail because of it.

Design: none (no screens; it changes the generated CI test job and how Forge runs the test command in each group)

## Why

A client's 2,300-test vitest suite went past the CI job's fixed 30-minute limit on a 2-core runner. Only pytest repos are split automatically today, so other test runners have no way to share the load. Four groups would take about 8 to 10 minutes.

## Done when

1. **A `groups` setting in forge.toml splits a pull request's test job into that number of parallel jobs, for any test runner. A group with no tests to run passes.**
2. **Forge fills `{group}` and `{groups}` in the test command with the group number and the group count, so a vitest or jest command can use its own shard flag. A run on the laptop is group 1 of 1.**
3. **A repo that gets six automatic pytest groups today still runs six groups after upgrade when it sets no `groups`, each with its share of the change's related tests. A pytest repo that sets `groups` gets the split options without a change to its test command. A new repo runs one group.**
4. **A group never reports another group's pass as its own, also when all groups run on one machine.**
5. **A test listed to always run passes or fails only in the group that runs it, and does not fail the other groups.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

This story starts after FORGE-TESTPLACE-1's CISEL part merges. CISEL makes the pull request's
`tests` job run `forge test --change` (close's related-test run) as one job, and keeps today's
six-group pytest-split job (the `test` command plus `--splits 6 --group ${{ matrix.group }}` and
the exit-status-5 fallback) for repos that have it. This story takes the cached-pass, split-options
and always_test notes (9 to 11) that FORGE-TESTPLACE-1's plan read deferred to it.

### Shared names

- **The setting (pinned by ANYRUNNER).** `groups` in forge.toml, a whole number of 1 or more.
  Add `"groups": int` to `repo.KEYS`, and give `_config_problem` (src/forge/repo.py about line
  791) a new `kind is int` branch beside the `str` and `list` branches that refuses any value but
  a whole number of 1 or more with `groups must be a whole number of 1 or more` (check
  `type(value) is int and value >= 1`, so `0`, `true` and `"3"` are refused).
  No entry in `repo.DEFAULTS`: readers use `cfg.get("groups")`, and a missing value means
  "derive" (today's rule: six for a direct pytest command in a repo that lists pytest-split, else
  one). Not a forge.local.toml key.
- **The group variables (pinned by ANYRUNNER).** The generated `tests` job sets
  `FORGE_GROUP: ${{ matrix.group }}` and `FORGE_GROUPS: '<groups>'` in its `env`, for every
  group count. Every other run (close, bare `forge test`, the nightly full run) has neither, and
  reads as group 1 of 1.
- **`repo.grouped(top, command) -> str` (pinned by ANYRUNNER).** Returns `command` with
  `{group}` and `{groups}` replaced by `FORGE_GROUP` and `FORGE_GROUPS` (each `"1"` when unset).
  PYGROUPS extends its body only (the pytest split options), never its signature or callers.
- **The empty-group pass (PYGROUPS).** One place in `review.test_run`, which every grouped
  command reaches (the picker wrapper, a direct `fast_test`, close's direct `test`): after an
  attempt, when `FORGE_GROUPS` is above 1 and the command exited with status 5 (pytest collected
  nothing for this group), the attempt counts as status 0 and its output gets the line
  `This group got no tests to run.`

### Done-when details

1. Generated CI (src/forge/prcheck.py, `ships()`): the group count is `cfg["groups"]` when
   forge.toml writes it, else today's derived count. When `groups` is written, the tests job runs
   `forge test --change` in that many matrix groups (`name: test group N of <groups>`, matrix
   `[1..N]`), whatever the runner, with no `--splits` suffix and no exit-status-5 shell fallback.
   A repo that writes no `groups` keeps CISEL's job byte for byte, apart from the two new `env`
   lines. The Node 30-minute timeout, the Windows retry wrapper, docs-check, parent-tests reuse
   and the one required `tests` check (`tests-passed`, which already needs every group) stay as
   they are. Doctor already accepts a `forge test --change` run step; check that the grouped job
   passes `forge doctor` with no new doctor code. A group with no tests passes: vitest and jest
   already get `--passWithNoTests` from `fasttest.close_tests`; the pytest case is PYGROUPS's
   (item 3).
   Test `tests/test_groups_any_runner.py::test_1_groups_split_the_test_job` (platform mark):
   a repo with `groups = 3`, `test = "vitest run --shard={group}/{groups}"` and a `tests` check;
   after `forge sync`, forge.yml's tests job has matrix `[1, 2, 3]`, the name `of 3`, the
   `FORGE_GROUP` and `FORGE_GROUPS: '3'` env lines and the run step `forge test --change`, has no
   `--splits`, and `forge doctor` prints no workflow problem. Adopted case: the
   `tests/fixtures/adopted-v1.2.2/client` repo (as `adopt_earlier` in
   tests/test_close_always_tests.py sets it up), upgraded with `groups = 3` written, gets the same
   job.
2. Placeholders: call `repo.grouped(top, ...)` where Forge reads a test command to run it:
   `review.test_run` (the `command` it gets, before the cached-pass key and the run),
   `fasttest.close_tests` (forge.toml's `test`), and `fasttest.test`'s `--pytest` path (the raw
   `test` it reads from forge.toml). `review.test_run`, not `review.close_test`, is the site for
   a direct command, so a direct `fast_test` (after its `{base}` replacement), close's direct
   `test`, and FORGE-TESTPLACE-1 FULLRUN's `review.test_run(..., always=True)` call on raw `test`
   (the nightly full run, src/forge/fullrun.py) all get the placeholders filled, with no change in
   fullrun.py. The nightly `full-suite` job has no matrix and sets no group variables, so it runs
   group 1 of 1. With no group variables, both placeholders become `1`, so a
   laptop run of `vitest run --shard={group}/{groups}` runs `--shard=1/1` (all tests). No
   refusal when `groups` is above 1 and the command has no `{group}`: every group then runs the
   same tests, which is slower but correct; the skill tells the agent to add the shard flag.
   Test `tests/test_groups_any_runner.py::test_2_test_command_gets_group_numbers` (platform
   mark), with the stub `node_modules/.bin/vitest` (and its `.cmd` shim) from
   tests/test_node_test_worker_budget.py writing its arguments to a file: `FORGE_GROUP=2
   FORGE_GROUPS=3 forge test --change` passes the stub `--shard=2/3` together with Forge's own
   `--changed <merge base> --passWithNoTests`; bare `forge test` passes `--shard=1/1`; with
   `fast_test = "vitest run --shard={group}/{groups}"` (the direct path that the nightly full run
   also takes through `review.test_run`), `FORGE_GROUP=2 FORGE_GROUPS=3 forge test --change`
   passes the stub `--shard=2/3`. Adopted case: the same runs in the adopted repo.
   Test `tests/test_groups_any_runner.py::test_1_groups_refuses_a_bad_value` (platform mark):
   with `groups = 0`, `groups = true` and `groups = "3"` in turn, `forge test` exits non-zero and
   prints `groups must be a whole number of 1 or more`. Adopted case: `groups = 0` in the adopted
   repo.
3. Six pytest groups on upgrade (PYGROUPS): move prcheck's detection (the `direct` pytest regex,
   no `;&|`, pytest-split listed in pyproject.toml or requirements*.txt) into
   `repo.pytest_split(top, command) -> bool`; prcheck's derived count calls it. `repo.grouped`
   then appends ` --splits {groups} --group {group} --splitting-algorithm least_duration` before
   it fills the placeholders when `FORGE_GROUPS` is above 1, the command has no `{group}`, and
   `repo.pytest_split` holds. With that, every repo's tests job (derived six or written `groups`)
   runs `forge test --change` per group: delete the `--splits` suffix, the bash and PowerShell
   exit-status-5 fallbacks in prcheck, and doctor's `" --splits "` workflow match
   (src/forge/doctor.py about line 445, and its comment). Add the empty-group pass (shared names)
   in `review.test_run`; `fasttest.pytest_tests` gets no exit-status-5 code. Close's one retry of
   failed files must not be split again: pytest-split would deal the failed files out anew and
   could leave this group empty, so status 5 would turn a real failure green. So the results hook
   (`fasttest.RESULTS`) makes its `pytest_configure` `tryfirst`, and its retry branch (where it
   sets `config.args` to the failed files) also sets `config.option.splits` and
   `config.option.group` to `None`, so pytest-split does not register and the retry runs this
   group's failed files whole. Init writes `groups = 1` in `init._settings` (new and adopted repos alike, and the
   starters), so a new pytest-split repo starts with one group; upgrade writes nothing, so an
   existing repo with no `groups` keeps its derived count. Forge's own repo writes no `groups`
   and keeps six; sync regenerates `.github/workflows/forge.yml` to the `forge test --change`
   form.
   Test `tests/test_groups_pytest.py::test_3_pytest_repos_keep_six_groups_and_new_repos_start_with_one`
   (platform mark): (a) `forge init` in a repo that lists pytest-split writes `groups = 1`, and
   forge.yml has one group; (b) adopted case: the adopted-v1.2.2 client with a direct pytest
   command, pytest-split listed and no `groups`, after the upgrade's sync, has six groups running
   `forge test --change`, no `--splits` in forge.yml, and `forge doctor` accepts it; (c) in that
   repo with `groups = 2` written and a change that two test files name, `FORGE_GROUP=1` and
   `FORGE_GROUP=2` runs of `forge test --change` (with `FORGE_GROUPS=2`) each pass and run a
   different one of the two files, and a `FORGE_GROUPS=3` group that gets no test passes; (d) in
   that repo with a direct pytest `fast_test` (no picker), a `FORGE_GROUPS=3` group that gets no
   test passes with the line `This group got no tests to run.`; (e) with `groups = 2` and one of
   the two files failing every time, of the two group runs of `forge test --change` exactly one
   fails after its one retry, its output names the failed test, and neither prints
   `This group got no tests to run.`.
   Existing tests PYGROUPS changes from the `--splits` form to the `forge test --change` form:
   tests/test_ci_job_budgets.py, tests/test_fix_gate_on_split_checks.py,
   tests/test_windows_client_retries.py, tests/test_windows_suite_retries.py,
   tests/test_windows_ci_uses_fast_storage.py, and any init test that matches forge.toml's text.
4. Cached pass (ANYRUNNER): `review.passed_record`'s key adds the resolved group number and group
   count (`FORGE_GROUP` and `FORGE_GROUPS`, each `"1"` when unset) to the hashed parts. Today the
   key is only the command and the committed files, and the picker's command is the same
   `python -c ... close_tests(...)` wrapper (or the same `fast_test`) in every group, so on a
   self-hosted runner group 2 skips its run on group 1's record (`review.test_run`, the
   `passed.exists()` branches). A laptop run and a one-group CI run share a key, which is right:
   they run the same tests.
   Test `tests/test_groups_any_runner.py::test_4_groups_never_reuse_another_groups_pass`
   (platform mark), the same stub vitest, changed to write its arguments to a file outside the
   checkout (the test's `tmp_path`, named by an environment variable) so `git status --porcelain`
   stays empty and the cached pass stays on, and set to fail when its arguments hold
   `--shard=2/2`: `FORGE_GROUP=1 FORGE_GROUPS=2 forge test --change` passes; a second
   `FORGE_GROUP=1` run on the same commit prints the "already passed" line and does not call the
   stub (the cache is active); then `FORGE_GROUP=2` on the same commit and machine runs the stub
   and fails, and its output has no "already passed" line. Without the key repair the last run
   would skip on group 1's record and pass. Adopted case: the same three runs in the adopted
   repo.
5. Always-run tests (PYGROUPS): pytest-split's own selection is `trylast`, so each always_test
   entry lands in one group, and the other groups never run it. In `fasttest.SELECTION`'s
   `pytest_sessionfinish`, skip the "ran no test" check when `FORGE_GROUPS` is above 1 (read
   from `os.environ`; the plugin is a string). One-group runs keep the check. pytest itself still
   stops every run on an entry whose file or node does not exist. Mark the ceiling with a
   `ponytail:` comment: in a grouped run, an entry that a mark or `-k` removes is not reported.
   Test `tests/test_groups_pytest.py::test_5_always_tests_pass_in_their_owning_group` (platform
   mark): a pytest-split repo with `groups = 2`, two test files and
   `always_test = ["tests/test_b.py::test_b"]`, a change named only by tests/test_a.py; both group
   runs of `forge test --change` pass, and `test_b` ran in exactly one of them. tests/test_close_always_tests.py
   keeps its one-group cases unchanged. Adopted case: the same two runs in the adopted repo.

### Skill, brief and guide

- ANYRUNNER: src/forge/templates/skill.md gets one row or line near the runner setting (about
  line 134): set `groups = N` in forge.toml for a slow CI test job, and add the runner's shard
  flag with `{group}` and `{groups}` to `test` or `fast_test` (for example
  `vitest run --shard={group}/{groups}`); a laptop run is group 1 of 1. docs/guide.md's tests-check
  paragraph (about line 330) says the same. The worker brief needs no change: workers never run
  CI groups.
- PYGROUPS: the same skill line and guide paragraph add that a pytest command in a repo that lists
  pytest-split gets the split options by itself, that a repo with no `groups` keeps today's count,
  and that each group runs its share of the change's related tests.

## Tasks

<!-- One row per task. Covers: the Done-when numbers it delivers, at most three. Scope: the paths
it may change. Tests: the tests it adds or changes. After: the tasks it waits for. When two tasks
share a function, field, file format or command, the first task pins it: it commits the shared
names and stubs plus one test that crosses both sides, and the tasks that use it list it under
After. Split tasks so each owns its files; shared lines (command table, guide list, registry) go
to one task or a small last wiring task; After only when a task needs another task's code. The
Developer column is optional: the lead fills or changes a GitHub username here, below For the
builders, without another approval. Leave it blank for an unassigned part. Forge next uses
the caller's GitHub login; another developer may start it with a warning. Existing tables
without Developer still work. The moving-parts line stays last: "none", or each new dependency, service, datastore,
queue, background job or abstraction layer, with the Done-when item that needs it. -->

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| ANYRUNNER | Groups for any test runner | The `groups` setting and its check, the group variables in the tests job, `repo.grouped` at the three places Forge reads a test command to run it, the grouped `forge test --change` job for a written `groups`, the group in the cached-pass key, skill and guide lines | 1, 2, 4 | src/forge/repo.py, src/forge/prcheck.py, src/forge/review.py, src/forge/fasttest.py, src/forge/templates/skill.md, docs/guide.md, .github/workflows/forge.yml | tests/test_groups_any_runner.py, plus existing tests that match the tests job's text (the two new env lines) | FORGE-TESTPLACE-1/CISEL | no | |
| PYGROUPS | Pytest groups on related tests | `repo.pytest_split` moved from prcheck, the automatic split options in `repo.grouped`, every tests job on `forge test --change` with the `--splits` form and its fallbacks deleted from prcheck and doctor, the empty-group pass in `review.test_run`, the unsplit retry, the grouped always_test check, `groups = 1` from init, skill and guide lines | 3, 5 | src/forge/repo.py, src/forge/prcheck.py, src/forge/doctor.py, src/forge/review.py, src/forge/fasttest.py, src/forge/init.py, src/forge/templates/skill.md, docs/guide.md, .github/workflows/forge.yml | tests/test_groups_pytest.py, plus the existing tests listed under item 3 | ANYRUNNER | no | |

The parts run in a chain: PYGROUPS edits repo.py, prcheck.py, review.py, fasttest.py, skill.md, guide.md and
forge.yml after ANYRUNNER merges, and extends ANYRUNNER's `repo.grouped`. FORGE-TESTPLACE-1's
FULLRUN part also edits fasttest.py, prcheck.py, docs/guide.md and forge.yml; whichever merges
later brings main in first. Module sizes: review.py is near 1,200 lines after CISEL, so
ANYRUNNER adds at most three lines there and PYGROUPS at most four; PYGROUPS removes more lines from prcheck.py and
doctor.py than it adds.

New moving parts: none

## Notes

- Owner decisions (24 Oct 2026, settled): forge.toml `groups` splits the pull request's test job
  into that many parallel jobs for any runner, with `{group}` and `{groups}` filled into the test
  command; each group runs only its share of the change's related tests, and the repos with six
  groups move to related tests split into groups; a group never reuses another group's pass;
  always-run tests pass in their owning group and do not fail the others; a pytest repo with no
  `groups` keeps six; a new repo gets one.
- Planner choices the owner did not make: (1) the CI job passes the group as the
  `FORGE_GROUP` and `FORGE_GROUPS` variables, and every other run is group 1 of 1; (2) no refusal
  for `groups` above 1 without `{group}` in the command: the groups repeat the same tests, which
  is slow but correct; (3) init writes `groups = 1` for new and adopted repos, and upgrade writes
  nothing; (4) a grouped run skips the always_test "ran no test" check, since pytest still stops on
  a missing file or node; (5) Forge, not the workflow's shell, passes an empty pytest group; (6)
  lint and type checks in the test command run in every group.
