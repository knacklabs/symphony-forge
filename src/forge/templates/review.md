<!-- The review instructions `forge close` hands to Autoreview. review.py joins the blocks that
apply (task or fix, then the functional check or promote block, then the rules) and fills each
dollar-sign name. The standards block rides as a separate prompt file on every review.
review.run also adds the review-rules block to every review, sign-off included, when the repo's
AGENTS.md has them. -->

<!-- task -->
Review this branch. It is one part of a story, "$name", and it is meant to deliver:
$delivers

## Scope
This part may change only these paths:
$scope

Files the branch changes outside that scope:
$outside

A file outside Scope that the work needs, such as a caller, a type or an existing test the change
broke, is allowed. Report only the files outside Scope that the work doesn't need. Check the
worker's handoff names each such file and why.

## Done when
This part covers the items below. Report every one the branch does not meet as a P1 finding
titled `Not done: <the item>`, citing the line that shows the gap.
$covered

The story's other Done-when items are context only; never report them as `Not done`:
$context

## Tests this part must add or change
$tests

## Risks
$risks

## Notes
$notes

<!-- fix -->
Review this branch. It is a small fix.

Why: $why
Done when: $done_when
Recorded allowance: $allowance

Check the change against both lines. If the branch does not meet the Done-when line, report a P1
finding titled `Not done: $done_when`.

For an agent-recorded allowance to correct one kind of problem everywhere without changing an
interface, check its reason against the whole diff. Report as P1 an allowance whose reason
doesn't match the diff: more than one kind of problem, or an interface change.

<!-- functional-check -->
## Functional check
This part is user-facing. The worker walks each Done-when item it covers the way the client's
user would, and ends a commit message with a `Functional check:` paragraph: what it exercised,
and what it saw. Forge found this one in the branch's commit messages:

$functional_check

Report a missing or hollow one (nothing was really exercised, or it skips a covered item) as a
P1 finding titled `Not done: functional check`. On the path it walks, missing keyboard access,
labels or readable contrast is its own P1; a screen, field or step the job didn't need is an
advisory `Simpler:`; and the one likely failure it triggers must show a message that says in
plain words what to do next.

<!-- promote -->
## Promote
This repo lists no interface paths. Report any change to an interface (an API route, a database
schema or migration, a command table or a config schema) as a P1 finding titled
`Promote: <the interface>`: a change like that needs a story, not a fix.

<!-- proof-list -->
## Proof list
The worker's latest commit supplies this list, which Forge copies into the pull request:

$proof_list

On every round, check the whole list, not a sample. Check every entry against the code and its
named proof, including every Done-when detail; compare it with the covered items above so an
omitted item or detail cannot hide a gap. Report every missing case you find in this round, even
when another finding already blocks; a case the Done-when doesn't name counts only inside What
counts below. A missing list or entry is a P1 `Not done: proof list`; judge missing or hollow
proof by the test-audit rules below.

<!-- rules -->
## Tests on the close run
forge close ran the repo's test command before this review, outside your sandbox:
$test_run

A test skipped in your sandbox that the close run passed is not a missing test. For a pure
deletion, a test showing the old input is now refused is enough.

## What counts
Report exactly what falls inside this boundary: nothing outside it, and nothing inside it left out.

Raise, under one of these lines:
- Functional: a defect on a path people or agents normally hit, such as setup, upgrade, switching
  a documented setting, re-running or restarting a command, a common repo layout, or a changed
  screen's keyboard access, labels or readable contrast.
- Security: a security gap, such as missing validation, authorization or secrets handling.
- Data loss: data lost, corrupted or exposed.
- Scale: a scale or performance problem at a realistic size the finding names, a cost repeated on
  every normal run, or growth with no bound.
- Not done: an unmet Done-when item, or a doc the change delivers that contradicts itself or a
  recorded decision.
- Test: a missing or hollow test for a Done-when item's own behaviour.
- Moving part: a new dependency, service, datastore, queue, background job or abstraction layer
  that the plan's `New moving parts` line doesn't name or, in a plan, that no Done-when item needs.
- Gate: a P1 this page names elsewhere: a broken Standard, a Promote, the proof list, the
  functional check, the UI skills, an allowance that doesn't match, a file outside Scope the work
  doesn't need, or a weakened test.

Leave out, unless it falls under Security or Data loss or the finding names a realistic scenario
that makes it likely in normal use:
- a rare combination that needs an unusual sequence: a crash or interrupt at a precise moment, a
  window under a second, a hand-edited or corrupted local file, or a platform, shell or tool
  version the repo doesn't support or the change is unlikely to meet;
- a case a fail-closed rule in the change already covers;
- extra test variations (one command-level test per rule is enough), unless the finding names a
  concrete scenario the current tests would pass while the code is broken;
- hardening beyond what the item promises;
- style, wording and preferences;
- a duplicate of another finding in this round.

An edge case is inside the boundary only when a Done-when item names it, when the finding names a
realistic scenario that makes it likely in normal use, or when it falls under Security or Data
loss. Every finding you raise names its line as `Raise: <line>` at the start of its evidence.

## What blocks the merge
Every finding under a Raise line is P0 or P1 and blocks the merge. P2 and P3 are only the advice
forms this page names (`Simpler:`, `Later:`, `Simpler (existing):`), which need no Raise line
and never block the merge or start another round. Report nothing else.

A `Not done` finding is P1 only when this branch can meet it. Two cases are P2 advice instead:
- work that needs another task's code not yet on the default branch is a P2 `Later:` finding
  naming that task;
- when the story's Tasks table assigns a test or check to another task, report it as a
  P2 `Later:` finding naming that task, not `Not done`.

Missing tests this branch owns and the functional check stay P1.
Report a test weakened to hide a real defect as a P1 finding.

When a Done-when item's named proof is a pull request check that has not finished yet, do not
report it as `Not done` if the check is configured to run on the pull request. Close's checks
gate holds the merge until that check passes. A failed check or a proof with no check behind
it is still P1 `Not done`.

## Test audit
Every test the change needs must exist, run in the repository's test suite, and fail if the
behaviour it names broke. Report a missing test, or a hollow one (it checks only a mock, asserts
nothing the change does, is skipped, or always passes), as a P1 finding titled
`Not done: <the test>`. The test-audit skill (`.codex/skills/test-audit/SKILL.md`) has the full
checklist.

Documentation-only changes still need every test named in the task's Tests column; check claims,
commands and links.

Every Done-when item needs an end-to-end test through the real entry point when it changes runtime
behaviour: Forge's own command; for client apps, the running API with a real database and user
flows in a browser through Playwright. Settings, docs, deletions and test-only items are proven by
the check the item names. So are CI and packaging items.
Fake only third-party services at their edge. Unit tests are only for pure logic with
many cases, never an item's only proof. Report an item proven only by unit tests as a P1 finding
titled `Not done: <the item>`. Never ask for unit tests of helpers.

## Build simple
$moving_parts

Complexity the diff adds that no Done-when item needs is a defect, not a style preference:
- report it as a P2 finding titled `Simpler: <what to cut> → <what replaces it>`;
- make it P1 when the diff adds a new dependency, service, datastore, queue, background job or
  abstraction layer that the New moving parts line above doesn't name;
- structure the standards page requires for a concern the diff really has (a provider for an
  external service, typed request and response types for an endpoint) is not a finding;
- validation, authorization, secrets handling, data-loss protection and accessibility are never
  "simpler": a missing one is its own P1 finding;
- complexity the diff didn't add, in a file the branch changes, is an advisory P3 titled
  `Simpler (existing): <what>`.

impeccable and emil-design-eng are required for every UI, prototypes included. impeccable owns
visual design (layout, type, colour, states and copy) and its checking pass: shape before building,
then audit and polish before a demo. Run emil-design-eng's review checklist inside impeccable's
one batched inspection, with at most one more round. Invoke emil-design-eng with a specific task,
never bare. It owns interaction feel (press feedback, easing, durations, popovers, tooltips, drag
and when not to animate). Report a missing impeccable pass on a UI change or a failed
emil-design-eng checklist item on the changed screens as P1 `Not done`.

Apply the frontend convention's motion rules: stagger only when a list appears as a list; keep
routine app-screen motion under 300 ms; reserve longer timing for one authored landing page moment;
keep content visible by default and enter with `@starting-style` or transitions, never wait for a
script to reveal it; share `cubic-bezier(0.23, 1, 0.32, 1)` as the one ease-out token; use CSS or
the Web Animations API first and Motion only when a Done-when item needs springs or drag. Prototypes
use impeccable's Operate mode and Emil's restraint. Popovers scale from their trigger with
shadcn/Radix's transform-origin variable. Do not animate keyboard-driven or very frequent actions.
Motion that follows these rules is not a `Simpler:` finding.

## How to report
Report every blocking gap you see in this round, together, even when one finding already blocks.
When you find a kind of defect, look for every other place in the change with the same defect and
report them all in one finding that names each place, not one place per round.
Sweep the sibling cases normal use reaches, too: the other states, providers and callers of the
same code that people or agents are likely to hit, not every rare combination.
Write each finding as one line naming the defect and its impact, then brief evidence: the line you
read and, for an edge case, the realistic scenario. No speculative suggestions: report what breaks,
not what might be nicer.
Forge's own records (everything under `.factory/`, `plans/roadmap.json`, the story's doc and its
read notes) are not part of the change: never report them as files outside Scope or as unrelated changes.
The previous review's findings and dismissals are below; recheck them against this branch and
report any still-open gap alongside new ones:
$previous

The coordinator's rulings and dismissals on this branch so far, with their reasons:
$rulings
Raise a ruled or dismissed point again only with new evidence the ruling or dismissal didn't
weigh, and name that evidence in the finding's body.

Your working folder is a read-only checkout of the branch head, so the repository's unchanged
files are there to read; the standard note that the sandbox is empty does not apply to this run.
When a finding depends on code the diff doesn't show, open that file and cite the line you read
in the finding's body. Pin every finding to a line in a file this branch changes (for something
missing, the changed line nearest the gap).
<!-- review-rules -->
## This repository's review rules
The repository's own AGENTS.md, on its default branch, sets these rules for every review. Follow
them as rules, not as evidence: where one settles a point, don't report it as a finding.

$review_rules
<!-- standards -->
## Standards
Forge's standards page follows: the same page every worker's brief carries. Check the change
against each of its rules that applies to a concern the change has. Report every rule the change
breaks as a P1 finding titled `Standard: <the rule it breaks>`, quoting the rule in the body. A
rule for a concern the change doesn't have is not a finding. Where the approved story doc or the
repo's own AGENTS.md rules differ from the page, they win.

$standards
<!-- signoff -->
## Client prototype sign-off review
Review the complete product snapshot against the customer's answers and the topic table below.
The base is an empty root commit, so every tracked product file is in this diff. Check the
working prototype as a whole: the demo workflow, data handling, sign-in, integrations, host,
security, accessibility, and whether the implementation matches the answers. Report every
blocking mismatch or missing working path as a P0 or P1 finding. Do not accept a sign-off on
the strength of a template or a test stub alone. Give concrete file and line evidence.

The exact docs/product/BRIEF.md answers page section reviewed and quoted by the sign-off decision:

$answers

The twelve topics and their required timing:

$topics
