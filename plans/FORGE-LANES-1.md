# Forge splits the machine between agents and tests

3 parts · Risks: none · New moving parts: none

## What changes for you

- Forge counts your machine's cores and gives half to agents and half to tests. On a 6-core
  machine, 3 agents (building, plan reads, reviews) run at once across all your repos, and test
  runs use 3 cores. On 8 cores it is 4 and 4. Nothing is hard-coded.
- Agents beyond that wait in line, first come first served, and say their place.
- Only one test run happens on the machine at a time, whether a worker or close starts it, so
  test suites never pile up and time out.
- Workers and close run only the tests related to the change. The full suite, and the slow tests
  that start containers or call a real model, run in CI.
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
2. **Only one test run happens on the machine at a time, using at most half its cores, whether a worker or close starts it.**
3. **Workers and close run only the tests related to the change, and the full suite and the container and real-model tests run in CI.**
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
   its size changed from 2 to `max(1, os.cpu_count() // 2)`. Same queue for forge work, forge read
   and close reviews, all repos. Test: one command-level test with `os.cpu_count` reported as 6
   (through an environment override Forge reads only in tests, `FORGE_TEST_CPU_COUNT`) shows the
   fourth agent waits.
2. The test lane is the fair test queue close already uses (review.test_run). Workers reach it
   through a new `forge test` command: it runs forge.toml's fast_test (or test when none is set)
   with `{base}` filled in, inside the same queue, and prints the same report close keeps. Forge
   sets `PYTEST_XDIST_AUTO_NUM_WORKERS` and `FORGE_TEST_CPUS` to `max(1, cpu_count // 2)` in the
   test run's environment, so `pytest -n auto` and any command that reads `FORGE_TEST_CPUS` stay
   within half the cores. Test: one command-level test where two `forge test` runs start together
   and the second waits, and the run sees both variables set to half the reported cores.
3. The worker brief tells workers to run tests only through `forge test`, never the full suite;
   close runs fast_test when set (already true). Container and real-model tests in Forge's own
   suite skip unless `FORGE_LIVE_CODEX=1` (done) or `FORGE_CONTAINERS=1`, which the CI workflow
   sets. Test: the brief carries the line; the container test skips without the variable.
4. `forge doctor` prints one line: `This machine: N cores, so M agents at once and test runs on M
   cores.` The guide (docs/guide.md and the skill) explains the two lanes in a short section.
   Test: doctor's line with `FORGE_TEST_CPU_COUNT=6` says 3 and 3.
   Machine view (for the Claude Code mod, FORGE-MOD-1): `forge lanes --json` prints both lanes
   for the whole machine: for each lane its size and, in queue order, every entry with kind (work,
   read, review, test), repo root and name, item, model and effort, started time (null while
   waiting), output file path, and for a running test the runner's progress as `done`/`total`
   when the runner prints it (pytest's `[ NN%]` and xdist counts), else null. Machine load and
   memory come from the OS. Test: one command-level test with one agent running, one waiting and a
   running test shows all fields, including another repo's entry.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| AGENTS | Agent lane by cores | The agent queue sized at half the cores, the test-only core override, doctor's split line, the guide section, `forge lanes --json` | 1, 4 | src/forge/machine.py, src/forge/doctor.py, src/forge/cli.py, src/forge/templates/skill.md, docs/guide.md | tests/test_lanes_agents.py, tests/test_lanes_view.py | | no |
| TESTS | One test lane for workers and close | `forge test`, the core-limit variables in every test run, test progress and output path in the lane entry, the brief's line | 2, 3 | src/forge/review.py, src/forge/templates/brief.md, src/forge/templates/skill.md | tests/test_lanes_tests.py | AGENTS | no |
| CI | Slow tests in CI only | Container tests gated on `FORGE_CONTAINERS=1`, set by the CI workflow | 3 | tests/test_proto_deploy.py, tests/conftest.py, .github/workflows/forge-next.yml | tests/test_lanes_ci.py | | no |

New moving parts: none

## Notes

- Owner decisions (2026-10-03): two lanes; split measured cores in half, nothing hard-coded;
  machines have at least 6 cores, Windows included; one command-level test per rule.
- Depends on the worker cap fix (machine-wide agent queue) having merged.
