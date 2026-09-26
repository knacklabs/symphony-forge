<!-- The review instructions `forge close` hands to Autoreview. review.py joins the blocks that
apply (task or fix, then the functional check or promote block, then the rules) and fills each
dollar-sign name. -->

<!-- task -->
Review this branch. It is one part of a story, "$name", and it is meant to deliver:
$delivers

## Scope
This part may change only these paths:
$scope

Files the branch changes outside that scope (report any that the work doesn't need):
$outside

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

Check the change against both lines. If the branch does not meet the Done-when line, report a P1
finding titled `Not done: $done_when`.

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

<!-- rules -->
## What blocks the merge
A `Not done` finding is P1 only when this branch can meet it. Two cases are P2 advice instead:
- work that needs another task's code not yet on the default branch is a P2 `Later:` finding
  naming that task;
- an edge case the Done-when doesn't ask for, where the item's purpose is already met, is a P2.

Missing tests and the functional check are unchanged: they stay P1.

## Test audit
Every test the change needs must exist, run in the repository's test suite, and fail if the
behaviour it names broke. Report a missing test, or a hollow one (it checks only a mock, asserts
nothing the change does, is skipped, or always passes), as a P1 finding titled
`Not done: <the test>`. The test-audit skill (`.codex/skills/test-audit/SKILL.md`) has the full
checklist.

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

impeccable is the one UI skill. A motion skill, or motion in the UI, belongs only when a
Done-when item needs motion; anything else is a P2 `Simpler:` finding.

## How to report
Your working folder is a read-only checkout of the branch head, so the repository's unchanged
files are there to read; the standard note that the sandbox is empty does not apply to this run.
When a finding depends on code the diff doesn't show, open that file and cite the line you read
in the finding's body. Pin every finding to a line in a file this branch changes (for something
missing, the changed line nearest the gap). P0 and P1 block the merge; P2 and P3 are advice.
