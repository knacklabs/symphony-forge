Review this unsigned working prototype.

Why: $why
Done when: $done_when
Recorded allowance: $allowance

Forge records the "Prototype before sign-off" allowance. It covers any size and interface
changes. Do not check this allowance against the diff.

Check only these three things:
1. Demo breakage: the demo workflow cannot finish in normal use.
2. Security: input, permissions or secrets allow unauthorized access or disclosure.
3. Data loss: a demo operation loses or corrupts data.

Only demo-step and boundary tests are due in these rounds. The full proof is due at sign-off.
Do not audit production completeness, style, architecture or coverage beyond those three checks.
Use the screen list to assess demo breakage, not to start a separate design audit.

## Demo proof and close's test run
$proof_list

$test_run

$design_context

## Findings
Give concrete file and line evidence and the normal-use scenario for each finding.
Score each finding's first body line as `Gain <g>, Work <w>, Harm <h>`, each from 1 to 5.
A broken main demo path scores Gain 5. Security and data loss score Harm 4 or more;
label their evidence `Raise: Security` or `Raise: Data loss`. These defects block the demo.
Report all such gaps together. A rare case is a follow-up.

## Earlier rounds and settled findings
$previous

## Rulings
$rulings

## Known and accepted
$accepted

Settled findings stay settled. Do not repeat a fixed or dismissed title and file. A new finding
needs distinct evidence of harm. The repository's reference material applies only within the
three checks above.
