---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-03T13:40:34+00:00
read_hash: a8488fc6d7535a70d01d45460fe3cd7ea2fa4c3c
round: 3
passed: no
doc_seen: a8488fc6d7535a70d01d45460fe3cd7ea2fa4c3c
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 90e68f8f2ea9974ce0c0e2d8cc7eaf1739f4578b
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

## Round 2

15. The proposed CPU helper fails on supported Python 3.11 and 3.12.
    `os.process_cpu_count` is unavailable there; the fallback expression raises before reaching `os.cpu_count`. Forge supports Python 3.11 and CI runs it. Guard the optional API and prove that path without the test shim masking its absence.
    Disposition: cut getattr fallback to os.cpu_count for Python 3.11 and 3.12

16. Disputed keep 10: one command-level test can still prove FIFO admission and cancellation.
    The revised scenario has only one waiting agent, so it cannot distinguish FIFO from another admission order or prove cancellation updates positions. Extend that same scenario with multiple waiters and cancellation; no additional test is necessary.
    Disposition: cut the one scenario now has two waiters and a forge stop that moves the 2nd to 1st

17. Unproven: item 2: the test lane remains occupied after Forge is killed.
    Recording a process group specifies the repair, but the named test still covers only normal failure and release. Include controller termination and a surviving child in `tests/test_lanes_tests.py`.
    Pin Windows group-lifetime handling too: the existing `codex._alive` checks one PID, which cannot establish that all descendants have ended.
    Disposition: cut the TESTS scenario kills Forge mid-run and the lane stays taken; the lane follows the test command's own pid, with descendants as a stated ceiling (no Windows job objects)

18. Finding 7 remains open for the shared lane-entry contract.
    `machine.half_cores()` is pinned, but the shared registration/update/removal API and record fields consumed by machine view, stop and `review.test_run` are not. AGENTS must pin their names, process identity/group fields and schema, with a crossing test before TESTS consumes them.
    Disposition: cut join, started, leave, entries and the entry fields are pinned in AGENTS with one crossing test

19. AGENTS’ upgrade proof depends on the later TESTS task.
    It must demonstrate both completed lanes, while TESTS delivers `forge test`, test-run CPU settings and group lifetime handling. Move `tests/test_lanes_upgrade.py` to TESTS or a final integration task so AGENTS can finish independently.
    Disposition: cut the upgrade test moved to TESTS

20. Cut or defer: `forge stop <item>`.
    This new user action traces to none of the approved outcomes; choosing the machine view does not establish a need for cancellation. If retained, add its outcome above the builders boundary and pin targeting across duplicate item names, waiting entries without process groups, and already-finished entries, with command-level proof.
    Disposition: cut forge stop is now an owner-facing outcome (Done-when 5) with targeting, waiting and finished cases pinned and tested

21. Unproven: item 2: `forge test` resolves `{base}` and handles missing inputs.
    Reusing close’s shell invocation does not specify which default-branch reference the standalone command uses, what happens when that reference is unavailable, or the result when neither test command exists. Finding 12’s command-contract gaps remain; name these cases in TESTS.
    Disposition: cut {base} is the merge base with origin/<default>, a missing ref refuses with one line, no test command exits 0; in the TESTS scenario

22. Unproven: item 3: the failing run contains a worker’s uncommitted change.
    “Never skips” fixes the specified behavior, but the named scenario does not exercise the original failure: committed history containing only documentation while code changes remain uncommitted. Include that state in the existing TESTS scenario.
    Disposition: cut the TESTS scenario has a doc-only commit with a failing uncommitted code change

23. The test-audit skill still instructs workers to bypass the lane.
    Its Validation step says to run `forge.toml`’s `test` command directly, and the worker brief requires using that skill. Assign its source, `.codex/skills/test-audit/SKILL.md`, to TESTS and align the shipped instruction with `forge test`.
    Disposition: cut TESTS owns both test-audit skill copies and points their run step at forge test

## Round 3

24. The lifetime contract still contradicts itself.
    Detail 1 releases the lane when the recorded PID ends and explicitly excludes descendants; detail 2 still holds it until the entire process group ends. Pick one rule and align the implementation, public promise and tests.
    Disposition: cut one rule: the place is held while the recorded process is alive; for tests that is the test command itself; process-group wording removed

25. Unproven: item 5: stop preserves process-identity protection.
    The new entry contract records a PID but does not pin protection against PID reuse or unreadable identity. Preserve the existing `codex.identity`/`codex._alive` safeguards, specify the refusal when identity cannot be verified, and prove an unrelated process cannot be terminated.
    Disposition: cut entries record process identity through codex.identity and codex._alive; unverifiable identity refuses; a reused pid is tested

26. `forge stop` is still ambiguous when one item occupies both lanes.
    A worker remains an agent while its `forge test` runs, so the same repo and item can have two entries. Pin whether stop cancels both or selects a lane, and prove that the separate test process cannot remain running after its place is freed.
    Disposition: cut every entry has an id; stop --id ends one entry, stop <item> ends all of the item's entries in both lanes; tested

27. Unproven: item 5: stopping running and waiting test entries.
    AGENTS’ named scenarios cover agent entries; TESTS’ stop proof is absent and its Covers cell excludes item 5. Assign the real test-command cancellation cases to TESTS, including confirmation that a stopped waiter never starts later.
    Disposition: cut TESTS covers item 5 with running and waiting test stops

28. Unproven: item 1: FIFO admission between surviving waiters.
    Stopping the first of two waiters leaves only one eligible run, so the revised scenario still cannot distinguish FIFO from LIFO admission. Extend the same command-level test to release a slot while two waiters remain, then exercise cancellation.
    Disposition: cut the scenario now has three waiters, releases a place before stopping one, and checks the order
