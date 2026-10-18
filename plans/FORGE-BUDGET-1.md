# One machine budget for workers, reviews, tests and CI runners, counting memory

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- Forge stops starting new work, reads, reviews and test runs when the machine is short of memory,
  not only when it is busy, and starts them again as memory frees. The laptop no longer runs out
  of memory when many items run at once.
- The test runs of all items share one budget of test processes, so two test runs at once no
  longer double the load.
- Self-hosted CI runners on the same machine are counted: while they run jobs, Forge leaves them
  room.
- Items waiting in line cost almost nothing while they wait, and the wait message still says each
  one's place.
- `forge doctor` shows the budget: cores, memory, test processes, and what the runners use.

## Why

On 16 October 2026 the laptop (8 cores, 16 GB) ran out of memory, and on 18 October it had under
1 GB free with about 5 GB compressed while Forge items and two GitHub Actions runners ran. An
analysis that day found that the half-the-cores rule does not bound the total: eight cores allow
two test runs at once, each with four test processes; small test selections, reads and reviews
skip the capacity limits; five test runs once overlapped; and admission checks load but never
memory. Each waiting item also polls every half second and checks every queue entry's process
with a separate command.

## Done when

1. **New work, reads, reviews and test runs wait while free memory is below a safe floor, and start again when it recovers.**
2. **All concurrent test runs on the machine share one budget of test processes.**
3. **A self-hosted CI runner busy on the machine reduces the budget Forge uses, and frees it when idle.**
4. **Items waiting in line poll at most once a second each and check all queue processes in one pass.**
5. **`forge doctor` shows the budget and what is using it, on new and adopted repos.**

## New and existing repos

- **New repos** (init or adoption): the budget from their first command; `forge doctor` shows it.
- **Existing repos** (on upgrade to this release): the same, with no setting to change; the
  machine-wide lanes keep working across repos on the old and new release while they upgrade.
  Tested on the adopted earlier-release fixture moved to this release.

## Risks

Risks: none one-way. The budget only delays starts; it never stops a running item. Each part
reverts with its pull request.

## For the builders

### Done-when details

1. Read free memory cheaply (macOS: `vm_stat` free plus inactive pages, or `sysctl
   vm.page_free_count`; Linux: MemAvailable in /proc/meminfo; Windows: GlobalMemoryStatusEx).
   Floor: about 1.5 GB or 10 percent of RAM, whichever is larger; a single constant like
   LOAD_LIMIT in src/forge/machine.py, not a setting. Waiting says why ("waiting for memory: 0.8 GB
   free, starts above 1.6 GB") in the same place line the load wait uses. Unknown memory (an
   unreadable source) never blocks. Tests: a fake low-memory reading holds a work round, a read, a
   review and a test run, and a recovered reading starts them.
2. Today each test run uses `-n` workers on its own and small selections bypass the test lane.
   Make the test lane's capacity a count of test processes (cores minus the agent share), give each
   run a share of it through the `-n` value it passes to pytest, and count small selections too.
   Tests: two concurrent test runs on a 8-core budget together never exceed the budget's process
   count.
3. A GitHub Actions runner on the machine (Runner.Worker processes, as doctor already detects
   Runner.Listener) counts as busy cores while a job runs. Tests: a fake busy runner reduces the
   agent and test budgets; idle runners do not.
4. src/forge/machine.py around 169 and 463: waiters poll every 0.5 s and run one process-identity
   command per queue entry, rewriting the queue each pass. Poll at 1 s (back off to 2 s after a
   minute), read all entries' process identities in one `ps` call per pass, and rewrite the queue
   only when it changes. Keep PID-reuse safety. Tests: a queue of many waiters makes one identity
   call per pass.
5. Doctor's machine section lists cores, free memory and floor, test processes in use, and busy
   runners. Tests: doctor output on new and adopted repos.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| MEMORY | Memory floor and runners | the memory floor for every lane, runner-aware budgets, doctor's budget lines | 1, 3, 5 | src/forge/machine.py, src/forge/doctor.py, src/forge/templates/skill.md, .claude/skills/forge/SKILL.md, .codex/skills/forge/SKILL.md | tests/test_machine_memory_budget.py | | | |
| SHARE | Shared test budget and cheap waiting | one test-process budget shared by all test runs, cheaper polling and identity checks | 2, 4 | src/forge/machine.py, src/forge/fasttest.py, src/forge/quicktest.py | tests/test_machine_shared_test_budget.py | MEMORY | | |

New moving parts: none

## Notes

- Measured inputs: Astra analysis of 18 October 2026, saved outside the repo.
