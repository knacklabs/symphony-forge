# Review Prompt — three lenses, one selected generation

Review runs inside the task-close owner after focused implementation checks and
its integrated verify/test proof. The owner releases it through
**`./forge task close <task-id>`** (0011, 0054, 0069). A small
diff uses one Codex helper call over the whole task diff. A diff that the helper
would chunk is split into the fewest file groups that fit its prompt limit;
each group judges all three lenses in ONE pass. Forge releases parallel groups
together; each sees the whole task tip tree, and a refused group retries alone
with its cause in the brief (0076, 0078).
Lock and generated files stay in scope and the stamp but their bytes are not
sent. The results merge into one immutable selected generation, with the worst
genuine contract verdict winning (0077). Never hand the review to a nested
companion job or hand-write findings.

Formal review uses `gpt-6-sol` at `high` reasoning. Route fixes back to the
active `gpt-6-luna`/max implementer and reuse that agent across review loops.
Apply `factory/skills/test-audit/SKILL.md`: flag tests that assert implementation
rather than behavior, lack a credible regression, duplicate coverage, or require
test-only production seams as findings.

A previously selected clean generation may be reused only when the stage's
stamp-token delta and current reviewed-meaning identity both match. Reviewed
meaning includes the approved semantic task brief, effective acceptance,
security and migration semantics, substantive automated evidence, review
instructions/helper/configuration, generated semantic inputs, and product
delta. Only explicitly canonicalized recorder bookkeeping and timestamps are
ignored; unknown, partial, or substantive change forces a fresh helper call and
preserves the original raw provenance.
The selected generation's `input` separately preserves the exact combined
prompt SHA256 and byte count sent to the helper. Never substitute the canonical
reviewed-meaning digest for that immutable input provenance.

Loop discipline: review the scoped diff that exists and verify findings against
the actual code before reporting. The host triages each blocker before a fix
round with `./forge review <id> --triage` by opening its cited line and callee
and naming all instances (0075). Repeated identical refusals follow
`docs/QUALITY.md` "Bounded recovery".

Review depth: the helper runs at **`--max-priority P3`**, the complete
three-lens depth `forge review` enforces. P0/P1 findings block the task; P2/P3
findings are recorded as `non_blocking_findings` and MUST be resolved or
explicitly deferred (with a reason) before the task ships, except
`simplification-debt`, which never blocks the current change. Other
non-blocking findings are never silently dropped or by themselves the reason
for another review.

Procedure:

1. `./forge task close <task-id>` does the final run: it mints the branch review run
   (`review-brief --all`, which the recorded generation is bound to), composes
   `.factory/review-briefs/<task-id>.combined.md` from the task's plan
   contracts, reviewer focus and the three lens definitions below, and runs
   the skill in **branch mode from the task's recorded base** — the whole task
   diff (`--mode commit --commit HEAD` would review only the LAST commit of a
   multi-commit task) — at `--max-priority P3`, with Codex as the engine. The
   run is pinned in a clean detached worktree because the skill refuses to
   finish if the reviewed tree changes mid-run and the main tree is where the
   harness keeps writing. Harness bookkeeping and lock/generated files are put
   back to the task base in the review tip; bookkeeping findings are dropped.
   Quality `contract_verdicts` come from `[quality] VERDICT <contract-id>:
   implemented|partial|missing` finding records (0077). Missing, partial, or
   unverdicted contracts block rather than passing silently. Verdicts
   are required for the reviewed task's contracts and those of tasks already
   done; tasks that have not started are not verdicted under the accepted
   per-task proof model in 0054, as preserved by 0069.
2. Review through THREE lenses in each run. The recorder projects the merged
   result into three `factory/schemas/review.json` lens records, each with
   `"generated_by": "autoreview"`:
   - **quality** — correctness, regressions, gaps in the implementer's tests,
     API/contract drift, and **maintainability** — not only where it affects
     defect risk. **Approved-deliverable presence and reachability — check this
     FIRST, before judging the code that IS present.** Cross-check the task's
     `acceptance_criteria` AND the approved task-plan's concrete deliverables
     against the ACTUAL diff. Every deliverable a criterion or the plan names — a
     guard/middleware, an endpoint or route, a migration, a config wiring, a CI
     job, a decorator, a port/adapter — must be genuinely IMPLEMENTED and
     REACHABLE (registered in the module/app, actually invoked — not merely
     defined in a file nothing imports). A promised deliverable that is ABSENT, or
     present but unreachable, is a BLOCKING finding under a stable
     `missing-deliverable` category — even when everything that IS present is
     clean and the build passes. This is the check that catches an implementation
     silently dropping an approved requirement that lived in plan prose or an
     acceptance criterion rather than a formal `plan_contract`/`contract_verdict`:
     a tidy PARTIAL implementation must never pass as complete. When the task
     declares `plan_contracts`, this presence audit is in addition to (not a
     substitute for) the per-contract `contract_verdicts`. Flag single-responsibility violations and poor file/folder
     organisation: a service that mixes types + validation + data access +
     mapping + orchestration in one file, thin/partial validation of required
     inputs, uncontrolled string literals where an enum/constant belongs,
     generic `Error` where a domain error type belongs, support/declaration
     files that cram unrelated concerns together (e.g. typed enums + primitive
     constants + DI tokens in one file), and a large module dumped flat with no
     coherent directory grouping by responsibility and concern. This
     organisation check is technology-AGNOSTIC — flag INCOHERENCE against the
     organisation the task's `reviewer_focus` calls for, never a specific
     mandated layout; cluster it under a stable `code-organization` category so
     `forge findings patterns` sees it recur. **Structure-for-growth
     is NOT over-engineering:** organising distinct, concrete responsibilities
     in foundational/shared infrastructure that is known to grow (a seam many
     future tasks route through) is correct design — do not wave it through as
     "over-engineering". Reserve the over-engineering finding for *speculative*
     abstraction: flexibility/configurability nothing uses, indirection for
     futures nobody has asked for, one-file-per-interface, abstract classes with
     a single trivial implementation, constants for values used once, or code
     duplicating stdlib/platform features. Constitution-mandated structure
     (modules, DTOs, the response envelope, provider pattern) is never a finding.
     **Ponytail conformance — the minimal-diff discipline is enforced at REVIEW,
     not only at write.** The implementer is bound to the ponytail ladder
     (necessity/YAGNI → reuse what exists → stdlib → native platform feature →
     an already-installed dependency → one line → minimum viable code); flag a
     diff that breaks it — a new dependency where the stdlib or an installed one
     suffices, a reimplementation of an existing helper, speculative flexibility
     — as an `over-engineering` finding. **Simpler alternative — check every
     mechanism the diff adds or extends:** ask whether one simpler, blunt rule
     covers the same cases (fail closed where safety is involved). Flag the stable
     `simplification` category, naming that rule, when cases are handled one by
     one though one rule covers the class, a follow-up fix adds machinery where a
     blunt rule works, or complexity exceeds the stated purpose (e.g. treating a
     guardrail as hostile-code containment). Dropping required validation, error
     handling, security, or accessibility is the opposite finding — a blocking
     gap, never simplification.
     **Existing simplification debt:** inspect existing code in files the diff
     touches and the functions it calls. Report avoidable complexity under the
     stable `simplification-debt` category in `non_blocking_findings`, naming
     the simpler shape; it never blocks the current change or triggers another
     fix/review round by itself. The coordinator follows `factory/skills/forge.md`
     to decide whether to refactor now or ledger it. Keep `simplification` for
     complexity the diff adds or extends.
     **Conversely, the constitution's coding standards are LAW, and code that
     VIOLATES them IS a finding** under a stable `constitution-conformance`
     category. Read `constitution/README.md` and the references its index maps to
     this diff, then flag deviations: an HTTP endpoint missing a typed request OR
     RESPONSE DTO (`pnp-api-standards`, `pnp-swagger-api-documentation-standards`),
     wrong file suffixes or a module layout that ignores
     `pnp-coding-standards-modular-monolith`/`03`, string literals where a typed
     enum/constant belongs, missing structured logging on security-relevant events
     (`05`/`06`), generic `Error` where domain exception handling is required
     (`07`), an integration that bypasses the provider/port pattern (`08`,
     `pnp-provider-pattern-for-integration`), or schema work ignoring
     `pnp-database-standards`. Judge conformance to the constitution and the task's
     `reviewer_focus` citations — the constitution, not your taste, is the standard
     (do not impose an invented layout beyond it). This holds whichever engine runs
     the lens and in any environment: `constitution/` is on disk, always readable.
     **Cyclomatic complexity — assess EVERY review, no exceptions.** Measure the
     branching complexity of each function/method the diff adds or changes; any
     whose control flow is excessively tangled (roughly >10 independent paths —
     deep nesting, long if/elif/switch chains, compound boolean conditions) is a
     BLOCKING finding under a stable `cyclomatic-complexity` category, naming the
     decomposition it needs (guard clauses, extracted helpers, table/polymorphic
     dispatch). Flag genuinely knotted control flow, never mere file or line
     count — constitution-mandated structure is never the target, and a run of
     simple sequential statements is not complexity.
     When the decomposition has `user_facing: true`, loading the
     `review-animations` skill as input to this lens is MANDATORY
     (easing/duration/spring choices, reduced-motion) — attest it in each
     artifact's `skills_used` list or the recorder refuses the artifact. It
     informs your findings; the artifact stays `generated_by: autoreview`.
   - **performance** — hot paths, algorithmic complexity, query fanout, I/O
     amplification, memory churn, concurrency bottlenecks; distinguish
     measured evidence from inference.
   - **security** — OWASP-style trust boundaries, authn/authz, secrets,
     injection, data exposure, unsafe defaults, abuse paths.
3. Emit findings STRUCTURED, not as prose strings: each entry in
   `blocking_findings`/`non_blocking_findings` is
   `{"category": "<kebab-case defect class>", "area": "<module/dir>",
   "summary": "<one sentence>"}`. The category is what lets
   `forge findings patterns` detect the same class recurring across tasks —
   the trigger for consolidation instead of a fourth patch (WORKFLOW.md
   "Recurring Findings"). Reuse category slugs you have used before; a
   renamed class is an undetected class.
4. `forge review` records the generation itself
   (`record_review_from_json.py --set`), replaces the task's `selected.json`
   pointer last, and stamps the stage when nothing blocks. The per-aspect
   recorder (`--aspect <lens>`) serves only a diagnostic `--lens` run, which
   never selects proof.

Afterwards — ONLY if the recorded decomposition has `user_facing: true` — run
the Sol/high `functional-checker` subagent (`factory/prompts/tester-functional.md`) and
record its result with `record_test_from_json.py --kind functional`.
