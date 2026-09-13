---
issue: GATES-1
title: Gates stale only on what they read
status: approved
saved: 2026-09-13T06:23:47+00:00
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

In: the input manifest and its recorder validation, one freshness predicate for
every consumer, honouring 0066 for review stamps, same-gate round reuse, and
ledger terminal states that decide what spends a grill allowance.

Out: changing what any gate judges; `forge task close`, which exists and was a
vendoring lag in the client repo; scope widening, which `stage amend-scope`
already handles without a cascade.

## Owner rulings

- The manifest hashes EVERY accepted decision, not only cited ones, because
  authors do not reliably know what they relied on.
- A pass recorded without a manifest keeps today's tree-based freshness. No
  manifest is ever backfilled: inferring what a reader read fabricates evidence.
- Round reuse is narrowed to the same gate and the same story, never across
  gates, stories or tasks.
- Decision 0066 stands; stamp deaths are a bug against it, not a reason to
  change it.

## Acceptance Criteria

Carried verbatim from the confirmed spec; see that file. In summary: a manifest
of path plus digest on every new pass with recorder validation; edits outside it
leave a pass valid and edits inside it stale the pass, including a newly accepted
decision; one predicate used by all six gates, the board and the next-step text;
review stamps surviving contract re-records that leave the delta unchanged;
same-gate round reuse with the per-gate floor intact; ledger terminal states
where a launch whose latest row is failed spends no allowance and blocks no
further read; and a bounded command-grammar check.

## Technical Approach

**The manifest is data on the grill record.** `factory/schemas/grill.json` gains a
required `input_manifest` for new passes: an ordered list of `{path, sha256}`,
with a null digest for an absent input. `record_grill_from_json.py` validates it,
refusing a manifest that omits the gate's artifact or whose digests disagree with
the tree.

**One predicate replaces several checks.** A single function in `factory_lib.py`
answers freshness from a manifest, and every consumer calls it:
`forge_cli/plans.py` (which today hashes the confirmed spec plus the whole
product tree), the gate table in `grill_gates.py`, the board and the next-step
text. A record without a manifest falls through to today's behaviour, which is
what keeps legacy passes valid.

**Post-stage task freshness is an exception to the manifest, not a case of it.**
The owner ruling above keeps 0066, and 0066 binds a post-stage task pass to its
objective, criteria, plan contracts, user-facing flag and plan — nothing else. So
the universal "a newly accepted decision stales a pass" rule does NOT reach the
post-stage task gate, which would otherwise contradict 0066 by staling every task
pass the moment any decision is accepted. T4 builds that selective snapshot and
this is the one gate the manifest does not govern. The alternative, superseding
0066, was rejected: 0066 is the promise this story is restoring, not revising.

**The pre-stage task guard is untouched, by owner ruling.** Task grounding
(`factory_lib.py:2304`) deliberately hashes the whole product tree BEFORE stage
start, which is how work drifting from its contract is caught before
implementation begins. That guard stays exactly as it is. The task gate moves to
manifest freshness only after stage start, which is where every case measured on
the client task occurred. So "all six gates" means all six after stage start; the
pre-stage task grill keeps whole-tree grounding and a test pins that it still
stales on an unrelated product file.

**A newly accepted decision is detected by set comparison, not by path.** The
manifest lists accepted decision ids with digests at record time. Freshness
compares the CURRENT accepted id set against the recorded one: an id present now
and absent then stales the pass, as does a digest change on a recorded id. A
decision that becomes superseded likewise changes the set.

**The schema stays one schema.** `input_manifest` is OPTIONAL in
`grill.json`, so legacy records remain valid documents; the RECORDER requires it
for every new pass. That split is what lets one schema describe both without a
migration.

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

**The manifest is derived, never declared.** The recorder builds it from the
FINAL pass payload rather than trusting an author to list inputs: it resolves
every record the pass cites to a repo-relative path and refuses the pass when a
cited input cannot be resolved or does not exist. Without that, a pass could omit
a record it actually relied on, validate cleanly, and stay fresh after that
record changed — which is the same blindness this story exists to remove, only
quieter. The gate's own artifact and the accepted-decision set are always
included, cited or not.

**The command check is bounded.** A test walks a named set of generated `./forge`
invocations from next-step text through the real parser, arguments included.
External programs and placeholders are out of scope.

## Decisions

Governing: 0066 (a stamp binds the diff — restored, not changed), 0067 (a round
belongs to its gate and story and may be reused there — accepted with this work,
superseding 0051), 0055 (enforced static quality baseline). No further new
decision.

## Surface Impact

- **Runtime / harness scripts:** the whole change. The recorder, the freshness
  predicate, the gate table, the plans gate, the stamp path, the grill budget
  and the launch ledger.
- **Data:** `grill.json` gains an OPTIONAL `input_manifest`, and the ledger gains
  a terminal state on launch rows. Round records are untouched. No migration,
  because old records stay valid documents and fall through to old behaviour.
- **API / MCP:** none. No tool, schema or protocol a client consumes changes.
- **CLI:** none. No command, flag or output contract changes; next-step text is
  validated, not altered.
- **UI:** none. The board reads the same records through the new predicate.
- **Docs:** decision 0067 lands with this work and 0051 is marked superseded.
- **Security:** neutral. The change loosens WHEN a pass is considered stale, never
  what a gate judges, and the criteria assert that manifest inputs still stale.
- **Tests:** one existing regression in `factory/tests/test_gates.py:8583` asserts
  the inverse of the new rule and is replaced by name.

## Task Decomposition

FIVE tasks. The plan gate read this twice and each round asked the plan to
specify a mechanism at code level; four distinct mechanisms are involved, and
that depth belongs in a task contract rather than here. Splitting also lets the
two small mechanisms land while the manifest work is still being designed.

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
- **T3 The manifest producer and freshness predicate.** ONE authoritative
  per-gate producer of manifest inputs, returning normalised repo-relative paths
  rather than the display text gate locators return today, and handling the
  composite signoff gate (BRIEF plus every spec plus the roadmap). The optional
  schema field, recorder validation, the single freshness predicate, and the
  accepted-decision set comparison. The pre-stage task guard is untouched per
  owner ruling. T3 also OWNS acceptance criterion 8, the generated-command
  grammar check, because it is the task that changes the next-step text and the
  board: it names the generated `./forge` invocations and walks them through the
  real parser, arguments included. Depends on T1 only for the comparator; T4
  depends on it.
- **T4 Post-stage task freshness under 0066.** The canonical selective task
  snapshot: a file-only manifest would stale on `write_scope`, `required_tests`
  or `verify_commands`, while omitting the decomposition would miss a changed
  objective or criteria. Preserves 0066's post-stage binding rather than
  replacing it, and restores the stamp path to `delta_id` only. Depends on T3.

Order: T1, then T2, then T3, then T4, with T5 after T2. The order is by
dependency: T4 needs T3's manifest, T5 needs T2's collapsed terminal-launch view
to decide when a granted read has been spent, and T1 and T2 are independent of
both. Nothing is sequenced by a shared verification helper, because
none is needed — see the note on the suite below.

T5 was split out of T2 when T2's contract was read cold. T2 was carrying two
mechanisms that share a sentence in the spec but no code: counting what a read
produced, and granting a further read. Only the first fits three files, and the
second turned out to rest on scoping the repo does not have.

## Risks

- Loosening staleness could blind a gate. The criteria assert both directions:
  edits inside the manifest must still stale a pass, including a newly accepted
  decision.
- The dual freshness path exists until legacy passes age out. It is deliberate
  and the alternative forces a re-grill on every in-flight task at vendor time.
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
green; the named new suites for manifest freshness, round reuse,
ledger terminal states and the command grammar; `./forge doctor`; and, per
decision 0055, Ruff format and lint plus Pyright over the changed Python. Those
three are not wired into verify today, so this task wires them for its own files
rather than claiming a baseline it does not run.
