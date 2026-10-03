---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-03T13:17:22+00:00
read_hash: 027a0c1522b29a34fa780f5310b14cf76f8d27f5
round: 1
passed: no
doc_seen: 027a0c1522b29a34fa780f5310b14cf76f8d27f5
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc, then run
`forge read <doc>` again for the next round, until a round finds nothing:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Item 2 promises a CPU ceiling that the proposed environment variables do not enforce.
   `FORGE_TEST_CPUS` requires runner cooperation, and the xdist setting covers `-n auto`, not explicit worker counts or other runners. Pin supported runner behavior or narrow the promise; the test must observe actual concurrency, not merely environment values.
    Disposition: cut the promise is now that Forge tells the run to use half the cores (pytest -n auto via PYTEST_XDIST_AUTO_NUM_WORKERS, FORGE_TEST_CPUS for others); the test checks the variables

2. Item 3 contradicts the full-suite fallback for repositories without `fast_test`.
   New setup only proposes that setting, and this checkout itself has none. Reconcile “only tests related to the change” and “never the full suite” with the stated fallback before approval.
    Disposition: cut Done-when 3 and the summary now say: related tests when the repo has a fast test command, otherwise its full suite in the test lane

3. Updating the worker brief leaves another instruction that bypasses the test lane.
   `src/forge/worker.py` builds `COMMIT_NUDGE` with the raw `config["test"]` command when a worker leaves changes uncommitted. Assign this path to TESTS and prove the retry instructs workers to use `forge test`.
    Disposition: cut TESTS owns worker.py's commit nudge, which now names forge test

4. Unproven: item 3: testing a worker’s uncommitted changes.
   `review.test_run` checks only `{base}...HEAD` before its documentation-only skip. A worker’s first uncommitted code changes can therefore produce a successful skip. Pin explicit-command skip/cache behavior and prove a failing uncommitted change actually runs and fails.
    Disposition: cut forge test never skips: no docs-only skip and no cache

5. Unproven: item 2: a running test survives termination of its Forge parent.
   `codex.in_line` locks the controller’s ticket; killing that controller releases it while its test subprocess can remain alive. Specify how the lane stays occupied or the subprocess is stopped, and prove the next run cannot overlap it.
    Disposition: cut the test command runs in its own process group recorded in the lane entry; the lane stays taken until the group ends

6. Cut or defer: `forge lanes --json`, test-progress parsing, and machine load/memory reporting.
   Item 4 requires a doctor line and guide text; this telemetry serves the separate mod story. Removing it also removes AGENTS’ test dependency on progress/output fields delivered only by the later TESTS task.
    Disposition: keep owner chose 2026-10-03 to put the machine view in this story for the mod; AGENTS ships agent entries, TESTS adds test fields, so no forward dependency

7. Shared contracts and ownership are not pinned before TESTS consumes them.
   AGENTS must pin the shared CPU-budget accessor. If telemetry stays, also pin the changes to `machine.agent_slot`, `machine.started`, `review.test_run`, queue metadata and JSON schema, with a crossing test.
   Both tasks own `src/forge/templates/skill.md`; assign the shared lanes section to AGENTS and the test-command instructions to TESTS, or use a final wiring task. Keep `After` only for an actual code dependency.
    Disposition: cut machine.half_cores() is the one shared function, owned by AGENTS; the view schema is pinned in AGENTS; skill.md lanes section is AGENTS', TESTS adds its lines after AGENTS

8. Simpler: `FORGE_TEST_CPU_COUNT` → patch `os.cpu_count` in the existing test shim.
   The test-audit skill rejects production flags needed only by tests. `tests/conftest.py` already launches Forge through a configurable Python shim, which can supply the reported CPU count without a production override.
    Disposition: cut the production override is gone; the existing test shim reports the core count

9. Unproven: items 1 and 4: CPU discovery returns no count.
   `os.cpu_count()` can return `None`; the proposed division then crashes. “Machines have at least 6 cores” does not guarantee successful discovery. Pin the fallback and prove admission and doctor use the same result.
    Disposition: cut half_cores falls back to 2 cores when no count is found, and doctor uses the same function; tested

10. Unproven: item 1: multiple waiting agents preserve arrival order and recover after cancellation or failure.
    Showing the fourth agent waiting proves capacity, not FIFO admission or changing queue positions. Extend the command-level scenario across work, read and review in different repos, including release and cancellation.
    Disposition: keep owner rule: one command-level test per rule; that test now mixes work, read and review across two repos and covers waiting order and release

11. Unproven: item 2: workers and close contend for the same lane across repositories.
    Two `forge test` invocations cannot establish that close shares their queue or receives the CPU settings. Name that mixed-entry scenario in TESTS, including a failing run’s exit status, report and subsequent lane release.
    Disposition: cut the TESTS test mixes a worker's forge test in one repo with a close in another, and a failing run frees the lane

12. Trap: Windows line endings and shells: item 2.
    The new command has no named proof for quoted executable paths, spaces, backslashes or CRLF output under Windows cmd/PowerShell. Pin its `{base}` reference, missing-reference behavior and empty-command result, then include these cases in `tests/test_lanes_tests.py`.
    Disposition: cut forge test runs the command exactly as close's test run does today, so quoting and Windows behave the same; no new shell handling

13. Unproven: item 3: the opted-in slow tests actually execute in CI.
    The proposed container test proves only skipping without the flag. Require positive execution on a runner with Docker and its dependencies.
    The current real-model workflow runs only `tests/test_fix_codex_test_home.py`; `tests/test_codex_smoke.py` remains skipped in the full workflows. Assign the missing CI wiring and its proof to CI.
    Disposition: cut the Ubuntu CI job sets FORGE_CONTAINERS=1 and the container test must show as passed there; codex-smoke runs both real-model files

14. Unproven: items 1–4: upgrading a repository adopted on the previous release.
    The upgrade test promised above the builders section has no task owner or Tests-cell entry. Assign it and prove both lanes, refreshed worker instructions and doctor behavior after upgrading, while preserving settings other than the release pin.
    Disposition: cut AGENTS owns tests/test_lanes_upgrade.py: a repo pinned to the previous release, moved to this one
