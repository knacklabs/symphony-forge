# Review brief — GATES-1-T1 — quality lens

You are one lens of a three-lens code review. You see ONLY the diff bundle for
this task (no repository access), so judge what the diff shows and say so when
something cannot be verified from it. Report every finding with its
file_path and line. Use ONLY these categories: bug, security, regression,
test_gap, maintainability. Priorities: P0/P1 block the task; P2/P3 must be
resolved or explicitly deferred with a reason before it ships.

LENS: QUALITY. Correctness, regressions, gaps in the implementer's tests,
API/contract drift, and maintainability. Check approved-deliverable presence and
reachability FIRST: every deliverable a plan contract, acceptance criterion, or
the reviewer focus names must be genuinely implemented AND reachable (registered,
invoked — not merely defined in a file nothing imports); an absent or unreachable
deliverable is a blocking finding even when the rest is clean. Flag
single-responsibility violations and incoherent file/folder organisation against
the reviewer focus (never a mandated layout). Structure-for-growth in shared
infrastructure is NOT over-engineering; reserve that finding for speculative
abstraction. Enforce the minimal-diff discipline (a new dependency where the
stdlib suffices, reimplementing an existing helper, sprawl where a surgical
change would do) — but a diff that drops validation, error handling, security, or
accessibility to look smaller is the OPPOSITE finding. The constitution's coding
standards are law: flag deviations you can see in the diff. Assess cyclomatic
complexity of every changed function; genuinely knotted control flow (roughly
>10 independent paths) is blocking and must name its decomposition.

LEFTOVERS (blocking): the diff must carry no code kept only for compatibility — no wrapper or shim over its replacement, no re-export or alias kept 'for callers', no renamed-but-retained symbol, no dead branch behind a removed feature, no 'legacy'/'deprecated'/'backward' naming or comment. Report each as a BLOCKING finding with file:line and verdict the contract it belongs to as partial; a clean diff says so in one line.
CONTRACT VERDICTS (mandatory, machine-parsed). In overall_explanation, emit ONE
line per plan contract listed under "Plan contracts" below, exactly in this form:

VERDICT <contract-id>: implemented|partial|missing — <file:line evidence>

Every listed contract must get a line. Do not rename contract ids.

For each contract, emit a verdict — implemented | partial | missing — with file:line evidence, recorded as contract_verdicts in the quality artifact. Then review the diff normally; the contract check does not replace the quality/performance/security lenses.

## Task GATES-1-T1

### Plan contracts

- **GATES-1-T1-C1**
  - Source: plans/active/GATES-1-gates-stale-only-on-what-they-read.md § Acceptance Criteria
  - Statement: Re-recording the same gate for the same story and task consumes its own existing round and requires no new question, including when the submitted round set differs from the one already stored
- **GATES-1-T1-C2**
  - Source: plans/active/GATES-1-gates-stale-only-on-what-they-read.md § Acceptance Criteria
  - Statement: A round already consumed by a pass at a different gate is refused
- **GATES-1-T1-C3**
  - Source: plans/active/GATES-1-gates-stale-only-on-what-they-read.md § Acceptance Criteria
  - Statement: A round already consumed by a pass for a different story is refused
- **GATES-1-T1-C4**
  - Source: plans/active/GATES-1-gates-stale-only-on-what-they-read.md § Acceptance Criteria
  - Statement: A round already consumed by a pass for a different task id is refused
- **GATES-1-T1-C5**
  - Source: plans/active/GATES-1-gates-stale-only-on-what-they-read.md § Acceptance Criteria
  - Statement: A gate that is not story-scoped is unchanged: it still reads the active story's rounds as well as the global ones
- **GATES-1-T1-C6**
  - Source: plans/active/GATES-1-gates-stale-only-on-what-they-read.md § Acceptance Criteria
  - Statement: A story-scoped gate still consumes rounds asked before any story existed
- **GATES-1-T1-C7**
  - Source: plans/active/GATES-1-gates-stale-only-on-what-they-read.md § Acceptance Criteria
  - Statement: The floor of at least one real round per gate still holds, asserted both ways
- **GATES-1-T1-C8**
  - Source: plans/active/GATES-1-gates-stale-only-on-what-they-read.md § Acceptance Criteria
  - Statement: No round record, schema or hook changes, asserted by the existing ledger round shape test still passing untouched

### Reviewer focus

- That the context outlives the cold reader and is cleared only when the gate pass records, since the human question comes after the reader exits
- That writer and reader resolve the same directory under a ceremony target, which silently misrouted rounds before
- That a task grill's rounds carry its declared task id, and empty means only a gate with no task
- That legacy and scoped rounds of identical text cannot consume one another in any scan order
- That the baseline comparator fails on a NEW failure rather than merely counting

### Settled — do not relitigate

The following are accepted: the story plan's decisions and rulings, and the contracts of tasks already sealed in this story. A finding that contradicts one is a proposal to change a decision, which belongs in a decision record, not in this review; do not raise it as a defect. Rejected findings from earlier rounds are ledgered as lessons below.

#### Story plan — Owner rulings

- The manifest hashes EVERY accepted decision, not only cited ones, because
  authors do not reliably know what they relied on.
- A pass recorded without a manifest keeps today's tree-based freshness. No
  manifest is ever backfilled: inferring what a reader read fabricates evidence.
- Round reuse is narrowed to the same gate and the same story, never across
  gates, stories or tasks.
- Decision 0066 stands; stamp deaths are a bug against it, not a reason to
  change it.

#### Story plan — Decisions

Governing: 0066 (a stamp binds the diff — restored, not changed), 0067 (a round
belongs to its gate and story and may be reused there — accepted with this work,
superseding 0051), 0055 (enforced static quality baseline). No further new
decision.

### Lessons in force

Recorded lessons that apply to this task's paths. A finding that contradicts one is not a defect unless it shows the lesson itself is wrong; say so explicitly instead of re-raising it.

- [medium] verify-merge-resolution-before-staging: Never git add a conflicted file until the resolution is machine-verified (anchored ^marker regex + ast.parse for Python) — content can legitimately contain marker-like strings, and add-after-failed-resolver commits the markers. Separate verification from commit; never chain a may-fail step to a commit via newline.
- [high] evidence-vs-tooling: Machine-generated evidence keeps colliding with tooling that assumes human-authored files, three times in one session: autoreview's secret detector reads delegations.jsonl's 32-hex launch_id as a credential and refuses the whole bundle; the union-merge driver reorders append-only JSONL ledgers on merge, which four review rounds then filed as a state bug; and verify.py silently substitutes a Node toolchain when FACTORY_*_CMD is unset, reporting red against a stack the repo does not have. Before adding an evidence format, ask what a generic scanner, a merge driver and a default-valued env read will each do to it.
- [medium] ledger-directories: Decision 0022 in practice: a ledger that many worktrees append to is a merge conflict by construction, and every mechanism built to manage that — a per-clone driver, gitattributes rules, scaffold wiring, dedupe — exists only to paper over the shared file. One record per file removes the conflict rather than resolving it.
- [high] task-grill-validator-two-gaps: record_grill_from_json._validate_task_grill: (1) rounds options are capped at 2..3 but AskUserQuestion delivers up to 4 options - change to 2 <= len(options) <= 4 or operator rounds with 4 choices refuse; (2) escalation_packet on decision 'block' accepts any non-empty dict - contract ACC2-C2 requires exactly the keys issue, evidence, recommendation, alternatives, rollback (all non-empty strings); validate them. Update/extend the two required tests accordingly.
- [high] Promote consumer-regression tests to required_tests so the worker must run them: A delegated worker self-verifies only against the task's required_tests + verify_commands, not the full suite. A regression in an out-of-scope consumer (e.g. board/story_detail crashing on run_state_path) is invisible to it and survives repeated re-delegation. When measurement finds such a regression, add the exact failing test to the frontier task's required_tests and re-delegate: a failing required test is feedback the worker cannot skip. Four re-delegations failed to land a 3-line guard until the board test was promoted to required.
- [high] A move-where-evidence-lives change needs an exhaustive hand-joined-read audit, and the full suite is the backstop: When a change relocates where evidence is stored, every consumer that hand-joins the old path breaks. Grepping only the paths named in known signals (grills/plan, history) missed phase.py (reads decomposition/tests/verify/reviews) and a pr_ready scratchpad gap — both surfaced only by the full gate suite after activation (S-0007). Audit by grepping EVERY hand-joined .factory/<name> read across the tree, not just the signal-named ones; and always run the full suite before committing an activation, never a targeted subset (a targeted subset hid a .gitattributes test regression for two tasks).

### Recorded evidence

Recorded by the harness for this story (not in the diff). Use it to verdict verification contracts; do not mark them partial for lack of execution evidence in the bundle.

- verify.py: ok at b32834d61038
  - `python3 factory/scripts/check_dual_runtime.py` -> exit 0
  - `python3 factory/scripts/check_factory_scaffold.py` -> exit 0
  - `uv run --with pytest --with psutil python -m pytest factory/tests -q` -> exit 0
- automated tests: pass
  - Seven new tests in factory/tests/test_round_provenance.py cover the one condition this task changes: a pass no longer spends the rounds recorded at its own evidence path, so re-recording the same gate for the same story and task reuses them even when the submitted round set differs from the one stored, while a different gate, story or task still refuses. The floor of one real round per gate is asserted both ways, and global gates are asserted unchanged. Three existing gate tests that an earlier draft broke (intake, adhoc capture, and the next/board route) pass again after that draft's global-gate narrowing was reverted.
  - 3 command(s) recorded, e.g. `uv run --with pytest --with psutil python -m pytest factory/tests/test_round_provenance.py -q`
