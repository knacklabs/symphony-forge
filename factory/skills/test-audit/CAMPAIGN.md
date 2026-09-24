# Test-pruning campaign

Campaign mode audits one subsystem's whole test surface: a plugin, package, or
core area. The value bar, retention bar, candidate evidence, and validation in
[SKILL.md](SKILL.md) apply to every lane. This file adds the order of work and
the lessons of a full campaign. Each step ends on its completion criterion;
do not start the next step early. Keep every edit inside approved task scope;
split a larger campaign into Forge tasks along production owner boundaries.
Each Forge leaf task owns its worktree and PR.

## 1. Baseline

Record the subsystem's test and support line counts and every in-scope test
file's pass/fail state at the task's base commit. Keep baseline failures in
their own list: an existing failure may be a real product bug, not a stale
test. For Forge's own harness, include relevant files under `factory/tests`;
client tasks use the paths declared in their task contracts.

Done when every in-scope test file has a recorded baseline result.

## 2. Lanes and inventory

Split the surface into **lanes** along production owner boundaries, not file
prefixes. Include every test file the subsystem owns, cases at shared core
boundaries, and its QA or live-proof harness tests.

Done when every in-scope test file and QA scenario belongs to exactly one
lane.

## 3. Read-only ledger per lane

Give each lane a read-only reviewer when the approved task graph permits it.
The reviewer reads every assigned test in full, including parameter tables.
They also read the production owners and their entry points, callers, history,
and CI routing. Each test declaration goes into a written **ledger** with one
mark. A parameterized test is one declaration unless its rows need different
marks; then mark each row.

- `R`: retain, naming the contract and the bug it catches; a retained test that
  only moves to a better-named file stays `R` with the move noted;
- `F`: retain the contract but repair the assertion, such as a vacuous negative
  that passes when only one of several items is missing;
- `C`: consolidate, naming the owner that absorbs the assertion first: a
  sibling table case, a stronger boundary suite, or the shared owner in
  another package;
- `D`: delete, naming the proof that remains, or why no contract exists.

Judge a test by its assertions, not its name. A test named for retiring a
progress window could assert that the window was not cleared.

Done when every declaration in the lane has a mark and an evidence line.

## 4. Layer plan per lane

Treat the per-test ledger as input, not as the edit list. A second read-only
pass, starting from the ledger, looks for the redundant **layer**. Name the
**keeper** suite for each contract. Prefer the real transport boundary with a
fake network over a mocked collaborator. Correct any ledger errors this pass
finds.

Done when each lane plan names its retired files, its keeper per contract, the
assertions to carry into keepers, and the test-only production seams unlocked.

## 5. Cutover

Edit lane by lane. Serialize changes to shared harnesses and support files
through one owner. With each lane, remove the test-only production seams it
unlocks: injection parameters, getters, reset exports, and indirection layers.
Register moved suites in CI routing and test inventories. Update shrink-only
line-cap baselines only when the approved task owns them. Put durable
test-ownership rules in the relevant `AGENTS.md`, drawn from mistakes this
campaign actually found.

Done when every lane plan is applied and each lane's keepers pass the tests
declared in the task's `required_tests`.

## 6. Preservation review

Before claiming completion, have independent reviewers compare deleted
coverage against the keepers, one reviewer per boundary group where the task
graph allows. They look for contracts that lost their only proof. They also
look for new assertions that cannot fail, such as a rejection row the
production code never reaches.

For each restored contract, make one deliberate **mutation** of the production
owner and confirm the keeper goes red. Then restore the source byte for byte.

Done when every reported gap is restored or rejected with source evidence, and
every restored contract has a caught mutation.

## 7. Product defects

A baseline failure that survives into a keeper is a bug report. Fix it in a
separate approved Forge task and PR, and prove it through the real user flow,
with a **control** run that reverts the fix and shows the old behavior. Record
unrelated product discrepancies as follow-ups instead of fixing them in the
campaign.

Done when each repaired defect has a failing control and a passing candidate
on the same harness.

## 8. Reconcile and hand off

Long campaigns can span many base commits. Refresh each task against the
current base through the approved Forge workflow. When the base changed a file
the campaign planned to delete, preserve the deletion only if the contract
still has a keeper; port any new contract into that keeper and confirm every
new regression still has a home. Rerun the complete subsystem test surface
through the task's `required_tests` and `verify_commands`, then use
`python3 factory/scripts/verify.py` and `forge task close <task-id>` as required
by the task contract.

Hand off with the [SKILL.md](SKILL.md) report, plus:

- baseline and final test/support line counts, with production counted
  separately;
- lanes, retired layers, and keepers;
- preservation gaps found and their mutations;
- product defects with control and candidate proof.
