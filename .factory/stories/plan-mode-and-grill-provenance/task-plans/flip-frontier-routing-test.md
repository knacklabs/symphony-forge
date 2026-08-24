# Task plan — flip-frontier-routing-test (follow-up, story plan-mode-and-grill-provenance)

## Objective
Fix the one suite failure the full verify surfaced: the frontier-routing
test still expects the pre-0048 order at the state after decomposition
recording.

## Finding
`factory/tests/test_gates.py::test_forge_next_routes_the_jit_frontier_states`
(assert at :15674) expects `factory/prompts/griller.md --gate task` as the
first frontier action after the decomposition is recorded. Under 0048 the
frontier routes `author-task-plan` first, so `forge next` now prints
"Before grilling, enter plan mode and author T1, then save it: ./forge task
plan save T1 --from <path>". Task 3 flipped the assertions at ~15112 but
missed this one; all other 656 tests pass.

## Steps (Codex, via delegate — one file)
In `test_forge_next_routes_the_jit_frontier_states`, at the
post-decomposition state: assert the author-task-plan action first
(`"task plan save"` and `"enter plan mode"` present; `"stage start"`,
`"forge delegate"` absent), then advance through `task plan save` +
`task approve` in the fixture before asserting the grill action
(`factory/prompts/griller.md --gate task`), matching the enforced order the
same way the flipped tests at ~15112 do. No production code changes.

## Write scope
`factory/tests/test_gates.py`.

## Proof (required_tests)
`uvx --with pytest --with psutil python3 -m pytest {path}::{id} -q -o
junit_family=legacy --junitxml={report}` for
`test_forge_next_routes_the_jit_frontier_states`.

## Verify commands
`python3 factory/scripts/check_dual_runtime.py`.

## Reviewer focus
The test asserts the new order end to end (plan → grill → approve → start)
rather than deleting assertions; fixture uses the real `task plan save` /
`task approve` commands and the real hook for the marker.

## Task grill (1 round; frontier empty)
Delivered via AskUserQuestion and hook-recorded; question asks whether the
fix belongs in a follow-up task (frozen graph) rather than reopening task 3.
