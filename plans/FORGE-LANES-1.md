# Forge splits the machine between agents and tests

3 parts · Risks: none · New moving parts: none

## What changes for you

- Forge counts your machine's cores and gives half to agents and half to tests. On a 6-core
  machine, 3 agents (building, plan reads, reviews) run at once across all your repos, and test
  runs are told to use 3 cores. On 8 cores it is 4 and 4. Nothing is hard-coded.
- Agents beyond that wait in line, first come first served, and say their place.
- Only one test run happens on the machine at a time, whether a worker or close starts it, so
  test suites never pile up and time out.
- Workers and close run only the tests related to the change when the repo has a fast test
  command (setup proposes one); a repo without one runs its full suite, inside the test lane. The
  slow tests that start containers or call a real model run in CI.
- `forge doctor` shows the split for this machine, and the guide explains it.

## Why

On a 16 GB, 8-core Mac, Forge and a second repo started many agents and up to three full test
suites at once. The machine ran out of memory, a live service stopped answering, tests timed out
under the load, and every timeout cost another round and another review. Agents mostly wait on
the model, so several can run together cheaply; test suites take every core, so two at once slow
everything. Forge has no plan for this today: it caps agents at a fixed 2 and lets each test run
use every core.

## Done when

1. **Forge runs at most half the machine's cores' worth of agents at once across all repos, and the others wait in line showing their place.**
2. **Only one test run happens on the machine at a time, whether a worker or close starts it, and Forge tells it to use half the cores.**
3. **Workers and close run only the tests related to the change when the repo has a fast test command, otherwise its full suite in the test lane, and container and real-model tests run only in CI.**
4. **`forge doctor` shows this machine's split, and the guide explains both lanes.**

## New and existing repos

- **New repos** (init or adoption): both lanes work from the first run; the agent proposes a fast
  test command at setup, as today.
- **Existing repos**: nothing to edit beyond moving to the new release (one upgrade fix). A repo
  still pinned to an older Forge runs that version's code, which uses its own test lock and no
  agent lane, so `forge doctor` there says to upgrade. A repo without a fast test command still
  runs its full suite, now inside the test lane. Their `forge.toml` is never rewritten. Tested by
  an upgrade test on a repo adopted on the previous release.

## Risks

Risks: none

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

### Done-when details

1. The agent lane is the machine-wide queue the worker cap fix added (src/forge/machine.py), with
   its size changed from 2 to the half-cores budget. One function, `machine.half_cores()`, owned by
   AGENTS, is the only place the count is worked out: `max(1, (os.process_cpu_count() or
   os.cpu_count() or 2) // 2)`; the agent lane, the test lane and doctor all call it. Same queue for
   forge work, forge read and close reviews, all repos. Test (one, command-level): the test shim
   that starts Forge reports 6 cores; a work round in repo A, a plan read in repo B and a close
   review in repo A take the 3 places, a fourth run waits and says it is 1st, and starts when one
   ends.
2. The test lane is the fair test queue close already uses (review.test_run). Workers reach it
   through a new `forge test` command: it runs forge.toml's fast_test (or test when none is set)
   with `{base}` filled in, inside the same queue, and prints the same report close keeps. It never
   skips: no docs-only skip and no already-passed cache, so a worker's uncommitted change always
   runs. It runs the command the same way close does (review.test_run's shell call), so quoting and
   Windows behave as close does today. Forge sets `PYTEST_XDIST_AUTO_NUM_WORKERS` and
   `FORGE_TEST_CPUS` to `machine.half_cores()` in every test run's environment; that is the whole
   promise: `pytest -n auto` honours the first, other commands may read the second. The test
   command starts in its own process group and its lane entry records that group, so the lane stays
   taken until the group has ended even if Forge itself is killed. The worker's commit nudge
   (worker.py COMMIT_NUDGE) tells workers to run `forge test`, not the raw test command. Test (one,
   command-level): a worker's `forge test` in repo A runs while a close in repo B waits for the
   lane, both see the two variables set to half the shim's cores, a failing run reports its exit
   status and frees the lane.
3. The worker brief tells workers to run tests only through `forge test`; close runs fast_test when
   set (already true), else test. Container tests in Forge's own suite skip unless
   `FORGE_CONTAINERS=1`, which the Ubuntu job of the CI workflow sets (it has Docker); the
   real-model tests already skip unless `FORGE_LIVE_CODEX=1`, and the codex-smoke workflow runs both
   `tests/test_codex_smoke.py` and `tests/test_fix_codex_test_home.py` with it set. Test: the
   container test skips without the variable; CI's Ubuntu run shows it passed, not skipped.
4. `forge doctor` prints one line: `This machine: N cores, so M agents at once and test runs on M
   cores.` The guide (docs/guide.md and the skill) explains the two lanes in a short section.
   Test: with the shim reporting 6 cores, doctor says 3 and 3; with no count found it says 1 and 1.
   Upgrade test (AGENTS): a repo whose forge.toml pins the previous release, moved to this one,
   shows doctor's split line, runs through both lanes, and keeps every other forge.toml setting.
   Machine view (for the Claude Code mod, FORGE-MOD-1): `forge lanes --json` prints both lanes
   for the whole machine: for each lane its size and, in queue order, every entry with kind (work,
   read, review, test), repo root and name, item, model and effort, started time (null while
   waiting), output file path, and for a running test the runner's progress as `done`/`total`
   when the runner prints it (pytest's `[ NN%]` and xdist counts), else null. Machine load and
   memory come from the OS. AGENTS delivers the view with agent entries and its schema; TESTS adds
   the test entry's progress and output fields. `forge stop <item>` ends that item's lane entry
   (its process group) and frees its place; only a person runs it (the mod asks first). Tests (one
   each, command-level): AGENTS: one agent running and one waiting from another repo show all agent
   fields; `forge stop` frees the place. TESTS: a running test shows its progress and output path.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| AGENTS | Agent lane by cores | `machine.half_cores()`, the agent queue sized by it, doctor's split line, the guide's lanes section, `forge lanes --json` with agent entries, `forge stop <item>` | 1, 4 | src/forge/machine.py, src/forge/doctor.py, src/forge/cli.py, src/forge/templates/skill.md, docs/guide.md, tests/conftest.py | tests/test_lanes_agents.py, tests/test_lanes_view.py, tests/test_lanes_upgrade.py | | no |
| TESTS | One test lane for workers and close | `forge test`, the core-limit variables in every test run, the process-group lane hold, test progress and output path in the lane entry, the brief's line and commit nudge | 2, 3 | src/forge/review.py, src/forge/worker.py, src/forge/templates/brief.md, src/forge/templates/skill.md | tests/test_lanes_tests.py | AGENTS | no |
| CI | Slow tests in CI only | Container tests gated on `FORGE_CONTAINERS=1`, set by the CI workflow | 3 | tests/test_proto_deploy.py, .github/workflows/forge-next.yml, .github/workflows/codex-smoke.yml | tests/test_lanes_ci.py | | no |

New moving parts: none

## Notes

- Owner decisions (2026-10-03): two lanes; split measured cores in half, nothing hard-coded;
  machines have at least 6 cores, Windows included; one command-level test per rule.
- Depends on the worker cap fix (machine-wide agent queue) having merged.
