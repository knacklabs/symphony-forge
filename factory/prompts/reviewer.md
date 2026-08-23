# Review Prompt — one autoreview run, three lenses

Review runs ONCE per task, after `verify.py` passes and the automated testing
artifact is recorded. The orchestrator runs the autoreview skill **DIRECTLY**
(its engine is Codex): invoke the skill's helper yourself from the coordinating
session — NEVER hand the review to a Codex subagent (that re-triggers the same
skill one indirection deeper and the companion write-guard refuses it), and
never hand-write findings inline. One autoreview run, three lenses.

Loop discipline (carried over from the retired subagent panel): scope-freeze —
review the diff that exists, do not expand scope; verify findings against the
actual code before reporting; stop after two fix-verify cycles.

Review depth: run the helper at **`--max-priority P2`**, not the P0-only
default. P0-only ships correct-but-unmaintainable code — it hides structure,
validation-depth, and clarity findings that are exactly what keeps a growing
codebase healthy. P0/P1 findings are blocking; P2 findings are recorded as
`non_blocking_findings` and MUST be resolved or explicitly deferred (with a
reason) before the task ships, not silently dropped.

Procedure:

1. Run the autoreview skill over the diff. For a committed task diff use
   `--mode commit --commit HEAD`; for an uncommitted local pass use
   `--mode local` (branch mode `--base origin/<default>` pulls in unrelated
   binary/vendor churn and refuses). When the current task declares
   `plan_contracts`, first compose `.factory/review-briefs/<task-id>.md` with
   `./forge review-brief <task-id>` and pass that repo-relative path as
   `--prompt-file`. Example: `"$AUTOREVIEW" --mode commit --commit HEAD
   --max-priority P2 --prompt-file .factory/review-briefs/<task-id>.md`. The
   quality artifact must include `contract_verdicts` for every declared
   contract.
2. Review through THREE lenses and emit one JSON per lens matching
   `factory/schemas/review.json`, each with `"generated_by": "autoreview"`:
   - **quality** — correctness, regressions, gaps in the implementer's tests,
     API/contract drift, and **maintainability** — not only where it affects
     defect risk. Flag single-responsibility violations and poor file
     organisation: a service that mixes types + validation + data access +
     mapping + orchestration in one file, thin/partial validation of required
     inputs, uncontrolled string literals where an enum/constant belongs, and
     generic `Error` where a domain error type belongs. **Structure-for-growth
     is NOT over-engineering:** organising distinct, concrete responsibilities
     in foundational/shared infrastructure that is known to grow (a seam many
     future tasks route through) is correct design — do not wave it through as
     "over-engineering". Reserve the over-engineering finding for *speculative*
     abstraction: flexibility/configurability nothing uses, indirection for
     futures nobody has asked for, one-file-per-interface, abstract classes with
     a single trivial implementation, constants for values used once, or code
     duplicating stdlib/platform features. Constitution-mandated structure
     (modules, DTOs, the response envelope, provider pattern) is never a finding.
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
4. Record each artifact:

```bash
python3 factory/scripts/record_review_from_json.py --aspect <quality|performance|security> --input <json>
```

Afterwards — ONLY if the recorded decomposition has `user_facing: true` — run
the `functional-checker` subagent (`factory/prompts/tester-functional.md`) and
record its result with `record_test_from_json.py --kind functional`.
