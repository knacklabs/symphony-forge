---
issue: GATES-1
title: Gates stale only on what they read
status: approved
saved: 2026-09-14T06:56:42+00:00
story: GATES-1
decisions_reviewed:
  - 0001-determinism-contract
  - 0005-recurring-findings-escalation
  - 0006-lessons-ledger
  - 0007-stage-commit-loop
  - 0008-loop-health-audit
  - 0009-frozen-gate-integrity
  - 0010-client-signoff
  - 0011-orchestrator-runs-autoreview
  - 0012-project-level-memory
  - 0013-always-armed-planning-lock
  - 0014-specs-before-signoff
  - 0015-plan-contradiction-gate
  - 0016-machinery-dir-rename
  - 0017-repo-as-system-of-record
  - 0018-delegation-gates
  - 0021-derived-ordering
  - 0022-conflict-free-ledgers
  - 0023-stage-delta-by-ref
  - 0025-evidence-lifetime-contract
  - 0026-bundled-example-validated-by-production-validators
  - 0027-responsive-proof-without-a-browser
  - 0028-path-boundary-invariant
  - 0029-plan-approval-in-plan-mode
  - 0030-harness-source-is-product-in-its-own-repo
  - 0031-workflow-modes-lite
  - 0032-jit-task-planning
  - 0033-gate-a-declares-all-work-records
  - 0034-vendored-docs-are-client-safe
  - 0035-commit-belt-keeps-ledger-fresh
  - 0036-client-gates-arm-on-roadmap
  - 0037-strict-role-split
  - 0038-portable-fail-closed-hooks
  - 0040-windows-user-scope-first-elevation-deferred
  - 0041-sandboxed-workers-default
  - 0042-psutil-cross-platform-process-model
  - 0044-accountable-engineering-loop
  - 0045-conflict-free-story-state
  - 0046-scoped-layout-activation-ordering
  - 0047-task-level-worktree-and-pr
  - 0048-plan-mode-and-grill-provenance
  - 0050-plan-authoring-is-mode-agnostic
  - 0052-approval-to-pr-is-the-agents
  - 0053-interchangeable-coordinator-shared-forge-contract
  - 0054-native-questions-and-task-proof
  - 0055-enforced-static-quality-baseline
  - 0056-staged-quality-baseline-rollout
  - 0057-coordinator-operation-simplification
  - 0058-bounded-native-bootstrap-support
  - 0059-task-owned-jit-workspaces
  - 0060-child-signal-mask-restoration
  - 0061-host-native-human-interaction
  - 0062-luna-max-exploration-and-implementation
  - 0063-first-native-task-workspace-bootstrap
  - 0064-lean-delivery-and-durable-history
  - 0065-ci-platform-evidence
  - 0066-closeout-binds-to-the-diff
  - 0067-rounds-rebind-to-their-gate
  - 0068-worker-commands-may-reach-the-network
---

# GATES-1 — Gates stale only on what they read

## Problem

Shipping one 17-file client task took eight re-runs of gates that had already
passed. None was caused by the work changing.

A clean three-lens review stamped the stage; fixing a verify command in the
contract then invalidated the stamp, and an unchanged tree was reviewed again to
re-earn it. Decision 0066 already says a stamp binds `delta_id` alone and that a
contract re-record never affects it, so that is the implementation failing an
accepted promise. Reverting two files to make the diff smaller killed the stamp
again. Amending a decision after a spec read re-staled that read. Cutting a task
worktree from trunk re-staled the task grill.

Two smaller costs compound it. Every recorded pass demands a fresh question
round, so a pass with a closed frontier cannot be recorded without inventing a
question to ask the owner. And a cold read that died on an upstream tool fault
still consumed a grill allowance, while recording an escalation printed that
grilling continues when the next read was still refused.

Spec: `docs/specs/gates-stale-only-on-what-they-read.md` (confirmed).

## Scope / Non-goals

In: the requirements gate joining the shared not-product definition, one freshness predicate for
every consumer, honouring 0066 for review stamps, same-gate round reuse, and
ledger terminal states that decide what spends a grill allowance.

Out: changing what any gate judges; `forge task close`, which exists and was a
vendoring lag in the client repo; scope widening, which `stage amend-scope`
already handles without a cascade.

## Owner rulings

- A decision record is NOT product for the requirements gate. This REVERSES an
  earlier ruling on this plan, which said the manifest should hash every accepted
  decision because authors do not reliably know what they relied on, and that a
  newly accepted decision should therefore stale a pass. The owner overruled that
  on 2026-09-13 for this gate, on the evidence that every other closeout check
  already treats decision records as not-product, and that the rule fired
  circularly here: recording decision 0067 invalidated the gate that had already
  read the spec 0067 came from. The other gates keep the old behaviour.
- The story is FIVE tasks, not four. An earlier round settled "four tasks means
  four pull requests"; T5 was split out of T2 on 2026-09-13 when T2's cold read
  showed the escalation grant rested on scoping the repo does not have. The
  per-task PR standard is unchanged — there is simply one more task.
- No freshness evidence is ever backfilled: inferring what a reader read
  fabricates evidence. (Carried forward from the deferred manifest design, which
  it also governs.)
- Round reuse is narrowed to the same gate and the same story, never across
  gates, stories or tasks.
- Decision 0066 stands; stamp deaths are a bug against it, not a reason to
  change it.

## Acceptance Criteria

Carried verbatim from the confirmed spec; see that file. In summary: the
requirements gate stops staling on inputs every other gate already treats as
not-product, chiefly decision records; review stamps surviving contract
re-records that leave the delta unchanged; same-gate round reuse with the
per-gate floor intact; and a launch whose latest row is failed spending no
allowance and blocking no further read.

The full input manifest and the bounded command-grammar check are deferred as
D-0035 with a revisit trigger — see the T3 entry for why the measured cost turned
out to have a much smaller cause.

## Technical Approach

**The requirements gate joins the one definition of product.**
`requirements_digest` (`factory_lib.py`) binds the confirmed spec body to
`product_tree_digest(root)` — called with NO `exclude` argument, so it uses the
bare default of `.factory/` and `plans/`. Every other closeout check calls
`product_excluded_prefixes`, which its own docstring calls "The ONE definition of
'not product'" and says exists because four lists disagreed and a decision record
"was not a scope stray but did stale the review stamp". That list also excludes
`docs/decisions/` and `docs/context/ledger.json`.

So the requirements gate is the one list that never joined. Accepting a decision
stales it and nothing else, and it fired on nearly every step of T1 and T2 —
including commits whose only product change was a decision record this story
itself wrote. The fix is to pass the shared definition, which is what the
docstring already claims is universal.

**The full manifest is deferred as D-0035.** A path-plus-digest list on every
pass, recorder validation, one predicate shared by all six gates, the
accepted-decision set comparison, the optional schema field, and the bounded
command-grammar check. It remains a coherent design for the four prefix-based
gates — spec, signoff, epics and plan all stale on whole directory prefixes — but
no measured cost forces it yet, and the cost that was measured had a one-argument
cause. The deferral carries a revisit trigger.

**Post-stage task freshness is selective already.**
The owner ruling above keeps 0066, and 0066 binds a post-stage task pass to its
objective, criteria, plan contracts, user-facing flag and plan — nothing else. So
the universal "a newly accepted decision stales a pass" rule does NOT reach the
post-stage task gate, which would otherwise contradict 0066 by staling every task
pass the moment any decision is accepted. T4 builds that selective snapshot and
this gate binds selectively by design. The alternative, superseding 0066, was
rejected: 0066 is the promise this story is restoring, not revising.

**The pre-stage task guard is untouched, by owner ruling.** Task grounding
(`factory_lib.py:2304`) deliberately hashes the whole product tree BEFORE stage
start, which is how work drifting from its contract is caught before
implementation begins. That guard stays exactly as it is. The task gate moves to
selective grounding only after stage start, which is where every case measured on
the client task occurred. So "all six gates" means all six after stage start; the
pre-stage task grill keeps whole-tree grounding and a test pins that it still
stales on an unrelated product file.

**Stamps stop reading the contract.** The stamp path binds `delta_id` only, as
0066 states. The contract digest leaves that comparison.

**Rounds are already scoped by where their evidence lives.** Nothing new is
stamped onto a round. The hook writes a round into the ACTIVE STORY's
`grill-rounds/` directory, and a recorded pass lands at a path already unique per
gate, story and task. So the rule follows from location: in
`record_grill_from_json.py`, a pass stops treating the rounds of its OWN evidence
path as spent, which is what makes re-recording free, while every other pass
still spends them, which is what refuses a round at a different gate, story or
task. That is the WHOLE change — one condition. This is decision 0067 (accepted),
which supersedes 0051. No round, round schema or hook changes, so there is no
legacy class and no migration.

0051 was thought to leave a hole where a globally recorded gate could consume a
round asked during another story. It does not: the recorder reads only the ACTIVE
story's rounds plus the global ones, so another story's rounds were never
reachable. Narrowing non-story-scoped gates to global rounds only, which an
earlier draft of this plan required, breaks the ordinary flow instead — spec,
signoff and epics are recorded while a story IS active, so their rounds live in
that story's directory. The gate tests caught it. Those gates are unchanged.

**Both grill guards read the ledger the same way.** Every launch appends
`starting`, then `running`, then a terminal row. Neither guard collapses them, so
filtering rows by status cannot exclude a failed launch: its `starting` and
`running` rows are not failed and still carry its id. The cap counts every launch
regardless, and the repeat-read guard's existing failed-filter does not actually
work. Both move to one view that collapses rows by `launch_id` to the latest, and
a launch whose latest row is `failed` spends nothing and blocks nothing.

A third state for a read that exits zero having produced nothing is deferred as
D-0032. The launcher runs the companion with `--json`, so the griller's verdict
marker never ends raw stdout, and detecting a silent read needs payload decoding
the fix above does not.

## Decisions

Governing: 0066 (a stamp binds the diff — restored, not changed), 0067 (a round
belongs to its gate and story and may be reused there — accepted with this work,
superseding 0051), 0055 (enforced static quality baseline). No further new
decision.

## Surface Impact

- **Runtime / harness scripts:** the whole change. The recorder, the freshness
  predicate, the gate table, the plans gate, the stamp path, the grill budget
  and the launch ledger.
- **Data:** the ledger gains
  a terminal state on launch rows. Round records are untouched. No migration,
  because old records stay valid documents and fall through to old behaviour.
- **API / MCP:** none. No tool, schema or protocol a client consumes changes.
- **CLI:** none. No command, flag or output contract changes; next-step text is
  validated, not altered.
- **UI:** none. The board reads the same records through the new predicate.
- **Docs:** decision 0067 lands with this work and 0051 is marked superseded.
- **Security:** neutral. The change loosens WHEN a pass is considered stale, never
  what a gate judges, and the criteria assert that a real product change still stales.
- **Tests:** none replaced. An earlier draft claimed
  `factory/tests/test_gates.py:8583` asserted the inverse of the new rule; reading
  it shows `test_plan_save_refuses_without_fresh_requirements_grill` asserts
  behaviour this story PRESERVES — editing the confirmed spec stales the pass, and
  so does adding a real product file. That claim was true only of the deferred
  manifest design, under which an unrelated product file would have stopped
  staling.

## Task Decomposition

FIVE tasks. The plan gate read this twice and each round asked the plan to
specify a mechanism at code level; four distinct mechanisms are involved, and
that depth belongs in a task contract rather than here. Splitting also lets the
two small mechanisms land independently of one another.

- **T1 Round reuse at its own gate (0067).** The recorder's consumption walk
  stops spending a pass's own recorded rounds, and a gate that is not
  story-scoped stops reading the active story's rounds. Provenance is read from
  where evidence already lives, so no hook, round or schema changes. Carries the
  test-baseline comparator the stage cannot close without, which is why it ships
  first: the other three cannot close a stage without it.
- **T2 The cap and the repeat-read guard agree.** A failed launch spends no
  allowance. The repeat-read guard already ignores a launch whose terminal row is
  `failed`; `_rounds_since_last_pass` counts every launch regardless, so a
  crashed launcher burns an allowance that exists to stop a reader circling. The
  cap adopts the filter the other guard already uses — existing data, no new
  field. Independent of the other tasks.

  A third state for a read that exits zero having produced nothing is deferred as
  D-0032, not dropped. The launcher runs the companion with `--json`, so stdout
  is a serialized object whose verdict text is in `rawOutput`, not raw text
  ending in the griller's marker; detecting it needs payload decoding, an
  end-anchored grammar, failure precedence for the host-side branches that write
  `failed` after a zero exit, and an outcome config on the starting row for
  read-launch recovery. The fault that motivated it is fixed in codex 0.154.0.
- **T5 The escalation grant.** An escalation grants exactly one further read for
  THAT gate and task. This is separate from T2 because the scoping does not
  exist: `open_escalation` returns the first unspent record globally, the record
  carries no gate, and the CLI exposes only `--task`, so one escalation silently
  unlocks a different gate. It needs `signal.py`, `forge.py`, the schema and the
  existing cap test — and an atomic claim, since two launches can both observe an
  unspent grant. The spend rule follows the confirmed spec: the grant is spent
  when the granted read COMPLETES, not only when it answers. Depends on T2.
- **T3 The requirements gate joins the one definition of product.**
  `requirements_digest` binds the confirmed spec body to
  `product_tree_digest(root)` with the BARE default exclusion — `.factory/` and
  `plans/` only. Every other closeout check calls `product_excluded_prefixes`,
  whose own docstring calls it "The ONE definition of 'not product'" and says it
  exists because four lists disagreed. That list also excludes `docs/decisions/`
  and `docs/context/ledger.json`. So accepting a decision stales the requirements
  gate and nothing else — the cascade that fired on nearly every step of T1 and
  T2. T3 is that one argument, plus the tests that pin it. The pre-stage task
  guard is untouched per owner ruling.

  The full manifest — a path-plus-digest list on every pass, recorder validation,
  and one predicate shared by all six gates — is deferred as D-0035 with a
  revisit trigger. It stays a coherent design for the four prefix-based gates,
  but no measured cost forces it yet. Acceptance criterion 8, the
  generated-command grammar check, goes with it; nothing in this story now
  changes the next-step text.
- **T4 Post-stage task freshness under 0066.** NOTE: `grounding_digest` already
  drops the product tree once `in_stage` is true, with a comment explaining that
  binding to it after work starts makes the gate self-defeating. Before writing
  T4's contract, read that and establish what is actually missing — it may be
  smaller than written here, or already done. The canonical selective task
  snapshot must still cover `write_scope`, `required_tests` and
  `verify_commands`, and must not omit the decomposition or a changed objective
  would slip through. Preserves 0066's post-stage binding rather than replacing
  it, and restores the stamp path to `delta_id` only. Independent of T3.

Order: T1, then T2, then T3, then T4, with T5 after T2. The order is by
dependency: T5 needs T2's collapsed terminal-launch view to decide when a granted
read has been spent. T4 no longer depends on T3, since the manifest it was to
consume is deferred. Nothing is sequenced by a shared verification helper, because
none is needed — see the note on the suite below.

T5 was split out of T2 when T2's contract was read cold. T2 was carrying two
mechanisms that share a sentence in the spec but no code: counting what a read
produced, and granting a further read. Only the first fits three files, and the
second turned out to rest on scoping the repo does not have.

## Risks

- Loosening staleness could blind a gate. The criteria assert both directions: a
  real product change must still stale the requirements gate, and only the paths
  every other check already treats as not-product stop counting.
- An earlier draft of this plan said the suite was 93 red and made T1 carry a
  baseline comparator so a stage could close against it. That was wrong twice
  over. `already_serving` answered "is ANY board up" rather than "is a board for
  THIS repo up", so the gate suite failed whenever the developer had a board
  running — and `task approve` starts one. Sharding the run under CPU contention
  inflated the count further. Measured sequentially and alone, `factory/tests` is
  942 passed, 0 failed. The comparator and its committed baseline are therefore
  CUT from T1: a plain full-suite verify closes a stage, and the net is strong,
  not weak. The probe itself is fixed separately.

## Verify Plan

`uv run --with pytest --with psutil python -m pytest factory/tests -q`, which is
green, plus the named new suites per task.

Decision 0055's static checks are NOT run by these tasks, and that is now
sanctioned rather than silent. 0055 was amended on 2026-09-14: the baseline binds
a task only once Ruff and Pyright are CONFIGURED and wired into verify and CI,
and until then a task must not contract those commands — an unrunnable verify
command fails at the seal, after implementation and review have already passed,
which is exactly how T1's seal failed. Configuring the baseline is ledgered as
D-0036 with an owner and a revisit trigger.
