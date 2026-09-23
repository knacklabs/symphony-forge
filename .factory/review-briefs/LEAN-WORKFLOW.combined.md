# Review brief — LEAN-WORKFLOW — combined review

You are the three-lens code review. The diff bundle is the subject.
Your working folder is the reviewed repository at the task tip, READ-ONLY; the
skill's note that the sandbox is empty does not apply to this run. Judge the
diff first. When a verdict or a finding depends on code the diff does not show
-- the callee of a changed line, a file a contract names, the other places a
contract covers -- open it (cat, sed -n, rg) and cite the line you read.
"Cannot verify from the diff" is not a verdict and not a finding: a partial or
missing verdict names the line that fails, and a finding about unchanged code
names the line that shows the defect. Read to resolve, not to roam: no finding
on code the diff neither touches nor calls. Report every finding with its
file_path and line. Use ONLY these categories: bug, security, regression,
test_gap, maintainability. Priorities: P0/P1 block the task; P2/P3 must be
resolved or explicitly deferred with a reason before it ships.

The target task's complete Plan contracts and Reviewer focus are supplied in `.factory/review-briefs/all.md`; use that dataset for task-specific review requirements. The rendered dataset is the authoritative review input for task lifecycle and evidence records intentionally omitted from the synthetic review checkout. Use those rendered records; do not call task proof, an event, or lifecycle evidence absent solely because its original `.factory` path is absent. Report any real contradiction between the product tree and the rendered evidence.

Assess quality, performance, and security in one provider pass. In every provider pass, overall_explanation must contain these exact full-line markers once, in this order, with a non-empty assessment between each pair:

BEGIN FORGE ASSESSMENT quality
<quality assessment>
END FORGE ASSESSMENT quality
BEGIN FORGE ASSESSMENT performance
<performance assessment>
END FORGE ASSESSMENT performance
BEGIN FORGE ASSESSMENT security
<security assessment>
END FORGE ASSESSMENT security

Keep each assessment short, a few sentences: overall_explanation is capped at 3000 characters in total and holds ONLY these three assessments. Never write VERDICT lines in it; a verdict is a finding record.

Prefix every finding title with exactly one matching token: [quality] , [performance] , or [security] .

FINDING FORM. Every finding, blocking or not, states in its body: the trigger
(the input or state that reaches the line), the behaviour the code shows there,
the contract, decision or rule it breaks, and the concrete risk. A finding
without a file:line that shows the behaviour is not a finding. Before demanding
a change, check the approved decisions, rulings and lessons in the dataset; a
finding that contradicts settled text is rejected on the record. Judge
reachability only where the evidence shows it: missing context is not proof of
absent implementation -- read the tree before calling a deliverable absent,
and name where you looked. A static security finding needs the trust boundary
and the line, not an executed exploit.


LENS: QUALITY. Correctness, regressions, gaps in the implementer's tests,
API/contract drift, and maintainability. Check approved-deliverable presence and
reachability FIRST: every deliverable a plan contract, acceptance criterion, or
the reviewer focus names must be genuinely implemented AND reachable (registered,
invoked — not merely defined in a file nothing imports); an absent or unreachable
deliverable is a blocking finding even when the rest is clean. Flag
single-responsibility violations and incoherent file/folder organisation against
the reviewer focus (never a mandated layout). Structure-for-growth in shared
infrastructure is NOT over-engineering; reserve that finding for speculative
abstraction or a concrete P0/P1 risk. Enforce the minimal-diff discipline (a new dependency where the
stdlib suffices, reimplementing an existing helper, sprawl where a surgical
change would do) — but a diff that drops validation, error handling, security, or
accessibility to look smaller is the OPPOSITE finding. The constitution's coding
standards are law: flag deviations you can see in the diff. Assess cyclomatic
complexity of every changed function; genuinely knotted control flow (roughly
>10 independent paths) is a P0/P1 finding only when it creates a concrete
correctness, security, or operational risk, and must name its decomposition.

CONTRACT VERDICTS (mandatory, machine-parsed). For EVERY plan contract
listed under the target task's "Plan contracts" in .factory/review-briefs/all.md, add one finding
RECORD, never a line in overall_explanation:

- title: exactly `[quality] VERDICT <contract-id>: implemented|partial|missing`
- body: the file:line you read and one sentence of evidence (the tree is
  readable; a verdict on code the diff does not show is read, not guessed)
- code_location: that file and line; priority: P3; category: maintainability

Every listed contract must get a record, in every pass. Do not rename contract
ids. A verdict record is not a defect: it is lifted out of the findings before
they are counted. Keep overall_explanation to the three short assessments.

In a chunked run, each quality pass emits a VERDICT record only for contracts it can judge from that pass's evidence. If a contract's evidence is absent from this chunk, omit its record; do not call it partial or missing solely because this chunk lacks its files. A genuine observed defect remains partial or missing. Across all passes every target contract must have an implemented verdict; an unverdicted contract fails closed. In a one-pass run, verdict every contract.


LENS: PERFORMANCE. Hot paths, algorithmic complexity, query fanout (N+1),
I/O amplification, memory churn, concurrency bottlenecks, missing pagination or
bounds, work repeated per request that could be done once. Distinguish measured
evidence from inference and say which each finding is. Use category `bug` for a
performance defect that will bite in production and `maintainability` for a cost
worth reducing.

LENS: SECURITY. OWASP-style trust boundaries, authentication and authorization
(every new route/handler: who may call it, with what scope), secrets and
credential handling, injection (SQL/command/template), data exposure and
over-broad responses, unsafe defaults, privilege escalation, and abuse paths.
Use category `security` for these findings.

LEFTOVERS: report compatibility, dead, or style-only code only when it creates a concrete P0/P1 correctness, security, data-loss, or contract risk, with file:line evidence. Otherwise record it as a P2/P3 follow-up or say that no blocking leftover exists; cleanup alone does not make the contract partial.

Reviewed meaning SHA-256: c2dc9e48ecb607e6d57df61439732a28c4288c8e63a4e8fcffb8e08b34c97501
