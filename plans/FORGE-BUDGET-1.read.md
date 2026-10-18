---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-18T10:19:44.779922+00:00
seconds: 207.136
read_hash: 48731db5ee323532eb316df7e080749493994774
round: 1
passed: no
doc_seen: 48731db5ee323532eb316df7e080749493994774
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a14e83-1d5e-7fe3-a9ad-1c6390be10e9
session:
blocked_rounds: 1
loop_choice:
loop_reason:
---
# Cold read notes

Written by `forge read`. Under every blocking finding, write one disposition line, amend the
doc, then run `forge read <doc>` again until a round has no blocking notes. Notes marked
`Advisory:` are recorded without requiring a disposition or another round:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

A finding inside What counts is cut or deferred. Keep one only when it falls outside that boundary
or is factually wrong, and give as the reason the Leave out line, the missing Raise line, the
cited fact that disproves it, or the human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: The mixed-release promise has no compatible accounting rule or test.
   Raise: Plan gap. `plans/FORGE-BUDGET-1.md:39-41` promises shared lanes during upgrades, but `src/forge/machine.py:163-176` counts runs, while the proposed lane counts processes. An older release can admit its four-process run alongside a new release's allocation without respecting the combined limit. Upgrading the adopted fixture before testing does not exercise that overlap.
   Gain 4, Work 2, Harm 3
   Disposition: cut

2. Blocking: SHARE excludes an existing test that requires the behavior it removes.
   Raise: Plan gap. `tests/test_machine_test_lane_capacity.py:17-20` and `:80-82` require two concurrent runs with four workers each on eight cores. That contradicts the proposed four-process total. Its doctor and guide assertions also require the old policy (`:101-105`). Neither task's Tests cell includes this necessary update (`plans/FORGE-BUDGET-1.md:79-80`).
   Gain 4, Work 1, Harm 2
   Disposition: cut

3. Blocking: MEMORY's budget reporting depends on an allocation contract that neither task pins.
   Raise: Plan gap. MEMORY must report test processes in use before SHARE implements process allocation (`plans/FORGE-BUDGET-1.md:79-80`). Existing entries record no allocated process count (`src/forge/machine.py:157-162`); `test_cpus()` supplies a per-command value instead (`:40-42`). The first task does not define the shared allocation data that doctor and SHARE must both use.
   Gain 4, Work 2, Harm 2
   Disposition: cut

4. Blocking: The required `ps` batching contradicts the supported Windows identity path.
   Raise: Plan gap. `plans/FORGE-BUDGET-1.md:69-71` requires one `ps` call per pass without a Windows rule. Windows currently uses native process handles and creation times (`src/forge/codex.py:853-884`); POSIX uses `ps` (`:885-897`). Ordinary native Windows installations cannot follow the specified implementation, and the planned identity-call test does not define its Windows behavior.
   Gain 3, Work 2, Harm 3
   Disposition: cut

5. Blocking: Unproven: item 3: an already-waiting command starts when a runner becomes idle.
   Raise: Test. Admission currently calculates capacity once, before polling (`src/forge/machine.py:163-170`). Tests that compare separate busy-runner and idle-runner starts, as described at `plans/FORGE-BUDGET-1.md:64-66`, can pass while a waiter retains its original reduced capacity indefinitely. Item 3 explicitly promises that the runner frees the budget when idle.
   Gain 3, Work 2, Harm 3
   Disposition: cut
