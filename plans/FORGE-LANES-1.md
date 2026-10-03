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
- `forge stop <item>` ends a running agent or test run, or takes a waiting one out of line, and
  frees its place. The Claude Code mod's stop key uses it after you confirm.

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
5. **`forge stop` ends a named running or waiting run in either lane and frees its place.**

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
   AGENTS, is the only place the count is worked out: `max(1, (getattr(os, "process_cpu_count", os.cpu_count)()
   or 2) // 2)` (process_cpu_count exists only from Python 3.13; Forge supports 3.11); the agent lane, the test lane and doctor all call it. Same queue for
   forge work, forge read and close reviews, all repos. Test (one, command-level): the test shim
   that starts Forge reports 6 cores; a work round in repo A, a plan read in repo B and a close
   review in repo A take the 3 places, a fourth, fifth and sixth run wait and say they are 1st, 2nd
   and 3rd; when a running one ends the 1st starts (not a later one); then the 2nd is stopped with
   `forge stop` and the 3rd says 1st and starts when the next place frees. Shared entry contract, pinned by AGENTS and used by TESTS, the machine
   view and `forge stop`: `machine.join(kind, repo, item, model, effort) -> entry`,
   `machine.started(entry, pid)`, `machine.leave(entry)`, `machine.entries() -> list`; each entry
   holds a unique `id`, kind, repo root, repo name, item, model, effort, joined and started times,
   the run's process identity (pid plus start time, through the existing `codex.identity` and
   `codex._alive`, so a reused pid never counts), output path and progress (both null until TESTS
   sets them). One rule for both lanes: a place is held while the recorded process is alive; for a
   test run that process is the test command itself, so it holds the lane even if Forge is killed;
   the command's own children are not tracked (ceiling: a grandchild left running after the
   command ends no longer holds the lane). One AGENTS test crosses
   join, started, entries and leave.
2. The test lane is the fair test queue close already uses (review.test_run). Workers reach it
   through a new `forge test` command: it runs forge.toml's fast_test (or test when none is set)
   with `{base}` filled in, inside the same queue, and prints the same report close keeps. It never
   skips: no docs-only skip and no already-passed cache, so a worker's uncommitted change always
   runs. It runs the command the same way close does (review.test_run's shell call), so quoting and
   Windows behave as close does today. Forge sets `PYTEST_XDIST_AUTO_NUM_WORKERS` and
   `FORGE_TEST_CPUS` to `machine.half_cores()` in every test run's environment; that is the whole
   promise: `pytest -n auto` honours the first, other commands may read the second. The test
   entry records the test command's own process (detail 1's rule), so the lane stays taken until
   that command ends even if Forge itself is killed. The worker's commit nudge
   (worker.py COMMIT_NUDGE) tells workers to run `forge test`, not the raw test command. Test (one,
   command-level): a worker's `forge test` in repo A runs while a close in repo B waits for the
   lane, both see the two variables set to half the shim's cores, a failing run reports its exit
   status and frees the lane. The worker's committed history holds only a doc change while a code
   change that fails is uncommitted, and `forge test` runs and fails. Killing the Forge process of a
   running `forge test` leaves the lane taken until the test command itself ends. `{base}` is the
   merge base with `origin/<default branch>`, as close uses; when that reference is missing,
   `forge test` refuses with one line saying to fetch it; with no test command it says forge.toml
   names none and exits 0, as close does. Upgrade test (TESTS, tests/test_lanes_upgrade.py): a repo
   pinned to the previous release, moved to this one, shows doctor's split line, runs through both
   lanes, and keeps every other forge.toml setting.
3. The worker brief tells workers to run tests only through `forge test`; close runs fast_test when
   set (already true), else test. Container tests in Forge's own suite skip unless
   `FORGE_CONTAINERS=1`, which the Ubuntu job of the CI workflow sets (it has Docker); the
   real-model tests already skip unless `FORGE_LIVE_CODEX=1`, and the codex-smoke workflow runs both
   `tests/test_codex_smoke.py` and `tests/test_fix_codex_test_home.py` with it set. Test: the
   container test skips without the variable; CI's Ubuntu run shows it passed, not skipped.
4. `forge doctor` prints one line: `This machine: N cores, so M agents at once and test runs on M
   cores.` The guide (docs/guide.md and the skill) explains the two lanes in a short section.
   Test: with the shim reporting 6 cores, doctor says 3 and 3; with no count found it says 1 and 1.

   Machine view (for the Claude Code mod, FORGE-MOD-1): `forge lanes --json` prints both lanes
   for the whole machine: for each lane its size and, in queue order, every entry with kind (work,
   read, review, test), repo root and name, item, model and effort, started time (null while
   waiting), output file path, and for a running test the runner's progress as `done`/`total`
   when the runner prints it (pytest's `[ NN%]` and xdist counts), else null. Machine load and
   memory come from the OS. AGENTS delivers the view with agent entries and its schema; TESTS adds
   the test entry's progress and output fields. `forge stop --id <entry id>` ends exactly that lane
   entry (the mod uses this); `forge stop [--repo <root>] <item>` ends every entry of that item in
   that repo, in both lanes (a worker and its own `forge test`). A running entry's process is
   terminated with its whole tree, the way Forge already ends Codex runs (taskkill /T on Windows,
   the process group elsewhere, as in codex.py and codex_turn.py), so the test runner a shell
   started ends too, and only after the recorded identity checks out; when it can't be verified, stop refuses with one
   line and terminates nothing. A waiting entry leaves the line and never starts later. No entry
   found says there is nothing to stop and exits 0. Only a person runs it (the mod
   asks first; the brief tells workers never to). Tests (one
   each, command-level): AGENTS: one agent running and one waiting from another repo show all agent
   fields; `forge stop` frees the place; a process whose pid was reused is not terminated. TESTS: a running
   test shows its progress and output path; stopping a running test ends the test runner the shell started, not only the shell,
   before the next run is let in; a stopped waiting test never starts; `forge stop <item>` ends both a worker and its
   test run.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| AGENTS | Agent lane by cores | `machine.half_cores()`, the agent queue sized by it, doctor's split line, the guide's lanes section, `forge lanes --json` with agent entries, `forge stop <item>` | 1, 4, 5 | src/forge/machine.py, src/forge/doctor.py, src/forge/cli.py, src/forge/templates/skill.md, docs/guide.md, tests/conftest.py | tests/test_lanes_agents.py, tests/test_lanes_view.py | | no |
| TESTS | One test lane for workers and close | `forge test`, the core-limit variables in every test run, the test entry's process record, test progress and output path in the lane entry, the brief's line and commit nudge, the test-audit skill's run step, the upgrade test | 2, 3, 5 | src/forge/review.py, src/forge/worker.py, .claude/skills/test-audit/SKILL.md, .codex/skills/test-audit/SKILL.md, src/forge/templates/brief.md, src/forge/templates/skill.md | tests/test_lanes_tests.py, tests/test_lanes_upgrade.py | AGENTS | no |
| CI | Slow tests in CI only | Container tests gated on `FORGE_CONTAINERS=1`, set by the CI workflow | 3 | tests/test_proto_deploy.py, .github/workflows/forge-next.yml, .github/workflows/codex-smoke.yml | tests/test_lanes_ci.py | | no |

New moving parts: none

## Notes

- Owner decisions (2026-10-03): two lanes; split measured cores in half, nothing hard-coded;
  machines have at least 6 cores, Windows included; one command-level test per rule.
- Depends on the worker cap fix (machine-wide agent queue) having merged.
