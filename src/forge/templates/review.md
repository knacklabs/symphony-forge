<!-- The review instructions `forge close` hands to Autoreview. review.py joins the blocks that
apply (task or fix, then the functional check or promote block, then the rules) and fills each
dollar-sign name. The standards block rides as a separate prompt file on every review.
review.run also adds the review-rules block to every review, sign-off included, when the repo's
AGENTS.md has them. -->

<!-- task -->
Review this branch. It is one part of a story, "$name", and it is meant to deliver:
$delivers

Recorded allowance: $allowance

## Scope
This part may change only these paths:
$scope

Files the branch changes outside that scope:
$outside

A file outside Scope that the work needs, such as a caller, a type or an existing test the change
broke, is allowed. Report only the files outside Scope that the work doesn't need.

## Done when
This part covers the items below. Report every one the branch does not meet as a P1 finding
titled `Not done: <the item>`, citing the line that shows the gap.
$covered

The story's other Done-when items are context only; never report them as `Not done`:
$context

## What changes for you
The owner approved these items with the plan. Each ends with its source or the sourced item
that needs it:
$changes

## Builder guidance
These details guide implementation. They are not owner-approved acceptance criteria and never
produce a blocking `Not done` finding:
$guidance

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

Forge records the "Prototype before sign-off" allowance. It covers any size and interface
changes. Do not check this allowance against the diff.

For other agent-recorded allowances to correct one kind of problem everywhere without changing
an interface, check the reason against the whole diff. Report as P1 an allowance whose reason
doesn't match the diff: more than one kind of problem, or an interface change.

<!-- design-context -->
$design_context

<!-- design-screens -->
Report as P1 a built screen that lacks a component or field its section of
`${design_folder}SCREENS.md` lists, when that screen is a screen marked Build now at sign-off,
or, until sign-off can mark screens Build now, a screen that this story's Done-when items name.
Do not report a field missing from any other screen. Check only screens listed in this item's own
approved design folder. Other design folders are context only.

<!-- design-theme -->
Check that the worker follows this instruction:
Apply DESIGN.md's theme tokens, type and colours to the app's theme file$theme_file.
Report as P1 a starter app that still has the starter's neutral tokens when DESIGN.md sets others.

<!-- functional-check -->
## Functional check
This part is user-facing. The worker walks each Done-when item it covers the way the client's
user would, and ends a commit message with a `Functional check:` paragraph: what it exercised,
and what it saw. Forge found this one in the branch's commit messages:

$functional_check

Report a missing or hollow one (nothing was really exercised, or it skips a covered item) as a
P1 finding titled `Gate: functional check`. On the path it walks, missing keyboard access,
labels or readable contrast is its own P1; a screen, field or step the job didn't need is an
advisory `Simpler:`; and the one likely failure it triggers must show a message that says in
plain words what to do next.

For production stories, also check the following on the paths this part covers. Apply the app's
scope and constitution, and accept explicit exceptions that explain why an item does not apply:

- An offline state, including a clear message for an online-only app.
- Tablet widths for the shell, a table and a form.
- The keyboard path: tab order, Cmd+K, Cmd+B and Esc to close dialogs, where those controls exist.
- Each row-level object has an extended detail screen, with tabs for related data, activity and files.

Report a missing applicable item as P1. These checks belong to the production story, not canvas sign-off.

<!-- promote -->
## Promote
This repo lists no interface paths. Report any change to an interface (an API route, a database
schema or migration, a command table or a config schema) as a P1 finding titled
`Promote: <the interface>`: a change like that needs a story, not a fix.

<!-- proof-list -->
## Proof list
Forge builds this list from the worker's mapping of Done-when items to tests. A pytest name
the branch has shows it is in the branch; the repo's chosen test place gives its
result in the pull request. Any other name is marked `not run` or `not checked` and may not
exist: `not run` means close ran no such test, and `not checked` means close could not match the
line to its run, so judge it by reading it:

$proof_list

On the first round, check the whole list, not a sample. Check every entry against the code and its
named proof, including every Done-when detail; compare it with the covered items above so an
omitted item or detail cannot hide a gap. Report every missing case you find in this round, even
when another finding already blocks; a case the Done-when doesn't name is a P2 `Follow-up:`
(What blocks the merge, below). A missing list or entry is a P1 `Gate: proof list`; judge missing or hollow
proof by the test-audit rules below.

<!-- approach -->
## Approach before code
$before_coding

Compare the diff with these three lines within this review's scope. Check git history: the
worker records them in an empty commit before code changes. Check that the need justifies
the code, the simplest option holds, and existing code is reused. Read later commit
explanations when evidence changes the approach. Report missing lines or unjustified
complexity under the normal Simpler rule.

<!-- rules -->
## Tests on the close run
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
- Not done: an unmet owner-approved Done-when item, quoted as written in the finding's title.
- Test: a missing or hollow test for a Done-when item's own behaviour.
- Moving part: a new dependency, service, datastore, queue, background job or abstraction layer
  that the plan's `New moving parts` line doesn't name or, in a plan, that no Done-when item needs.
- Not needed: a large addition that no source asks for and that no sourced item needs: a new
  table, background job, workflow or settings flag, or about 150 lines or more. A source is a
  client note in
  `docs/product/DISCOVERY.md`, an answer in `docs/product/BRIEF.md`, a decision in
  `docs/decisions/`, a screen marked Build now at sign-off, a fixed rule in
  `docs/product/CONSTITUTION.md`, or the human's own request: a dated source on a plan item, or a
  fix's Why and Done-when line. An item that has a source needs what it cannot work without. The
  canvas is not a source.
- Gate: a P1 this page names elsewhere: a broken Standard, a Promote, the proof list, the
  functional check, the UI skills, an allowance that doesn't match, a file outside Scope the work
  doesn't need, or a weakened test.
- Plan gap: something that would make the build wrong or stall it: a contradiction, a question a
  builder must ask, a shared name no earlier task pins, a likely case or refusal no rule or test
  covers, a one-way step missing from Risks, a task that is too big, a shape bigger than the Done
  when needs, work no Done-when item needs, or a known trap the change is likely to meet.

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

Four principles govern every change.
1. Is it needed at all? Deleting beats fixing.
2. Add work only when F x H >= 2 x C: how often the problem happens (F) times how bad it is (H)
   is at least two times the cost (C). Score each from 1 to 3. F, for the first 1,000 users:
   1 rare, 2 weekly, 3 daily. H: 1 cosmetic or the person's own data, 2 wrong information or a
   broken step, 3 a P0. C: 1 for 20 lines or fewer with no model call or user step, 2 for up to
   about 150 lines or one model call or user step, 3 for more, or a new table, job, workflow or
   flag.
3. Choose the simplest option.
4. Rules are stated, not policed: add no check, gate or refusal only to enforce a rule.

Mark each finding that asks for added work beyond the Done-when items (another check, retry, guard
or flag) with a body line `Adds work: <what>; F <f> x H <h> = <p>; 2 x C = <c>`. When p is less
than 2 x C, score its Gain 2 or less: it is a known limit and does not hold the work. A review
keeps it in Known issues; a cold read keeps it with its disposition in the read notes. A finding
under Security or Data loss, or one that names a migration, keeps its Harm floor and still holds
the work. A check that a Done-when item promises is not added work: report it missing as
`Not done: <the item>`, which holds the work at any score. Never title an added-work finding
`Not done`.

Title an addition that no source asks for and that no sourced item needs
`Not needed: <what was added>`. Write its evidence in plain words for the developer and the client:
what the change adds, with its file and line or plan item; which sources and sourced items you
checked and found silent; and the two ways forward: name its source or the sourced item that needs
it, or remove it and add one line for it to `plans/ideas.md`. Check plans and code against the screens marked Build
now at sign-off, never against the canvas, which can show later screens. Until sign-off can mark
screens Build now, the Build now screens are the ones that the story's Done-when items name. What
the app's fixed rules or the starter already give is not an addition. A large addition goes under
the Raise line above: say that it is large and why, score it Gain 4, and Work 1 or 2, because
either way forward is small, so it holds the work, and include `Case: normal use - <the addition>`.
A smaller addition is advice: in a cold read start it with `Advisory:`, in a review report it as
P2, and score it Gain 1 or 2. When a source asks for an addition that the work does not need, ask
whether it can be cut: Is it needed at all? Deleting beats fixing. Report it as advice,
`Cut or defer: <what>` in a cold read or `Simpler: <what> → cut` in a review, scored Gain 1 or 2.

## What blocks the merge
A finding blocks only when it names a case that happens in normal use. Include
`Case: normal use - <the scenario>` or `Case: rare - <the scenario>` in each finding that
would block. A rare case never blocks. A security hole or data loss that any user can reach
is normal use. Do not raise a finding that this repo's Review rules or a recorded owner decision
(a decision in `docs/decisions/`, a `Decided:` line or a `Ruling:` line) already settles.

Your scores decide, whatever the priority: Harm 4 or 5, or Gain 5 blocks the merge. Otherwise,
Gain 4, or Gain 3 with Harm 3, blocks the merge only with Work 1 or 2. Every other Gain 3 or 4
finding is a follow-up fix, even a Gain 3 finding with Harm 1 or 2 and Work 1 or 2.
Gain 1 or 2 is lived with. Findings below the bar let the merge go on.
Every finding under a Raise line is P0 or P1. P2 and P3 are only the advice
forms this page names (`Simpler:`, `Later:`, `Follow-up:`,
`Simpler (existing):`, a small `Not needed:`), which need no Raise line
and, scored Gain 1 or 2, never block the merge or start another round. Report nothing else.

A `Not done` finding is P1 only when this branch can meet it. Two cases are P2 advice instead:
- work that needs another task's code not yet on the default branch is a P2 `Later:` finding
  naming that task;
- when the story's Tasks table assigns a test or check to another task, report it as a
  P2 `Later:` finding naming that task, not `Not done`.

A `Not done` finding blocks only when it names a Done-when item the change misses as
written. A case the Done-when does not name, such as another language, platform, shell,
tool or folder layout, is a P2 `Follow-up: <the case>` finding that Forge records and the merge
doesn't wait for, even when realistic (score it Gain 1 or 2); a functional, security or data-loss defect
on the changed code still blocks under its own Raise line.
Only the numbered owner-approved Done-when sentences above (or the fix's Done-when line)
can block as `Not done`. Builder details, Notes and implementation guidance cannot. Forge keeps
a `Not done` finding that names none of those items as a follow-up, with its original scores.
A `Not done` that names one of this item's own Done-when lines blocks regardless of its scores,
rare-case label or light review. Only the owner's recorded choice can accept that unmet work.

Missing tests this branch owns and the functional check stay P1.
Report a test weakened to hide a real defect as a P1 finding.

Report a fix that hides a symptom and leaves the root cause in place. Check the first place the
code goes wrong, the shared function, and sibling callers with the same fault.
A guard is a fix only when it handles a valid state.
Report code that only makes tests pass: hard-coded expected values, a branch that detects a test,
or a silent default that hides a broken rule.

When a Done-when item's named proof is a pull request check that has not finished yet, do not
report it as `Not done` if the check is configured to run on the pull request. Close's checks
gate holds the merge until that check passes. A failed check or a proof with no check behind
it is still P1 `Not done`.

## Test audit
Every test the change needs must exist, run in the repository's test suite, and fail if the
behaviour it names broke. Report a missing test, or a hollow one (it checks only a mock, asserts
nothing the change does, is skipped, or always passes), as a P1 finding titled
`Gate: <the test>`. The test-audit skill (`.codex/skills/test-audit/SKILL.md`) has the full
checklist.

Tests check behaviour at the boundary the user touches, never internal record formats or private
calls. If a behaviour-preserving refactor breaks a test, report it under this test audit and ask
for a check at the owning boundary.

Documentation-only changes still need every test named in the task's Tests column; check claims,
commands and links.

Every Done-when item needs an end-to-end test through the real entry point when it changes runtime
behaviour: Forge's own command; for client apps, the running API with a real database and user
flows in a browser through Playwright. Settings, docs, deletions and test-only items are proven by
the check the item names. So are CI and packaging items.
Fake only third-party services at their edge. Unit tests are only for pure logic with
many cases, never an item's only proof. Report an item proven only by unit tests as a P1 finding
titled `Not done: <the item>`, quoting the owner-approved item. Never ask for unit tests of helpers.

## Build simple
$moving_parts

An added abstraction layer belongs only at the edge to an outside service. Keep business logic
in domain services and pure computation in helpers. Required module boundaries, controllers
and data access keep their roles, without extra wrappers.

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

Report reader load under this Simpler rule: a wrapper or adapter with one caller, a layer that
repeats the next layer's methods and arguments, or module or global state where a local variable
or return value works. Can a new reader answer "where does X come from?" and "what can change X?"
in about 30 seconds? Score the finding with the normal Gain/Work/Harm bar; reader load alone does
not make it P1. Keep structure that the standards require for a real concern.

impeccable and emil-design-eng are required for every UI, prototypes included. impeccable owns
visual design (layout, type, colour, states and copy) and its checking pass: shape before building,
then audit and polish before a demo. Run emil-design-eng's review checklist inside impeccable's
one batched inspection, with at most one more round. Invoke emil-design-eng with a specific task,
never bare. It owns interaction feel (press feedback, easing, durations, popovers, tooltips, drag
and when not to animate). Report a missing impeccable pass on a UI change or a failed
emil-design-eng checklist item on the changed screens as P1 `Gate: UI check`.

In an app with shadcn/ui set up (a `components.json`), report a new UI component that hand-builds what a shadcn/ui component or block already does as a P1 finding titled `shadcn: <the component>`, unless a `Not shadcn: <why>` comment at the component says why shadcn/ui cannot do it. A composite built from shadcn/ui components is not a finding, and neither is a library or component the default branch already has.

On client app screens, report an emoji that this change adds as an icon or decoration as a
finding titled `Icons: <the screen>`. Report an icon from outside the starter's `lucide-react`
library the same way; shadcn/ui is set to `lucide`. Keyboard key labels such as the Command key
symbol (⌘) are not emojis. Apply this rule to new and existing client repos; do not report
unchanged screen code.

In an app with a database, report a query that this change adds in one module on a table another
module owns as a P1 finding titled `Module tables: <the query>`. A module owns the tables in its
own schema file; in an app without one schema file per module, it owns the tables that only its
code writes. Other modules reach those tables only through its public service. A query the
default branch already has is not a finding, and neither is app code outside the modules, such
as the demo-data loader.

In an app with a database, report a foreign key that this change adds between two
business-module Postgres schemas as a P1 finding titled `Module foreign key: <the link>`.
A link between business modules stores an indexed id without a foreign key and is checked
through the other module's public service. Links within a module and links to core keep their
foreign key. A foreign key the default branch already has is not a finding; existing apps
keep their tables and schemas.

In an app with a database, report a table that this change adds, or a column, constraint, index
or trigger on such a table, that breaks the database skill (.codex/skills/database/SKILL.md) as
a P1 finding titled `Database: <the table or column>`. Report a Postgres extension that this
change turns on and that is not on the skill's allowed list the same way, unless the app's
constitution has a line "Postgres extension <name>:" with the owner's OK. A change to a table
that the default branch already has is not a finding.

Report agent, chat or assistant code that this change adds or changes, and that breaks a Must
rule of the agents skill (.codex/skills/agents/SKILL.md), as a P1 finding titled
`Agents: <the rule's heading>`. Report a broken Should rule as a P2 finding titled
`Agents advice: <the rule's heading>` scored Gain 1 or 2, so it stays advice. Agent code,
including its system prompts, tool descriptions and prompt versions, is agent code, so a change
that only edits a prompt is checked. Agent code that the default branch already has is not a finding.

In a TypeScript app with `zod` in a `package.json`, report a request body or query that this
change adds and that no zod schema checks as a P1 finding titled `Zod: <the endpoint>`. Request
input has one zod schema in the module's contracts package, which the web form and the API both
use, and the API documentation comes from that schema. A class-validator rule or an `@ApiProperty`
on request input that this change adds is a finding. Input the default branch already has is
not a finding, and neither is a path parameter that a Nest parse pipe checks.
An app made before this layout keeps its own folders and schema; follow the folders it has.

Apply the frontend convention's motion rules: stagger only when a list appears as a list; keep
routine app-screen motion under 300 ms; reserve longer timing for one authored landing page moment;
keep content visible by default and enter with `@starting-style` or transitions, never wait for a
script to reveal it; share `cubic-bezier(0.23, 1, 0.32, 1)` as the one ease-out token; use CSS or
the Web Animations API first and Motion only when a Done-when item needs springs or drag. Prototypes
use impeccable's Operate mode and Emil's restraint. Popovers scale from their trigger with
shadcn/Radix's transform-origin variable. Do not animate keyboard-driven or very frequent actions.
Motion that follows these rules is not a `Simpler:` finding.

In a React app with React Compiler turned on (`babel-plugin-react-compiler` in a `package.json`),
report a `useMemo`, `useCallback` or `React.memo` that this change adds as a P1 finding titled
`Memo: <the component>`. The compiler memoizes. Code under `components/ui/` (the shadcn/ui copies)
is not a finding, and neither is code the default branch already has.

In a React app, report a component or prop that this change adds and that breaks the frontend
convention's composition rule as a P1 finding titled `Composition: <the component>`: layout
passes content as `children`; parts that share state are a compound component that shares it
through context; logic with no markup is a custom hook; and no boolean prop switches a component
between modes. Code under `components/ui/` is not a finding, and neither is code the default
branch already has.

## How to report
Name the scenario with `Case: normal use - <the scenario>` or `Case: rare - <the scenario>`
in each finding that would block. A rare case is a follow-up, whatever its scores.
Report every blocking gap you see in this round, together, even when one finding already blocks.
When you find a kind of defect, look for every other place in the change with the same defect and
report them all in one finding that names each place, not one place per round.
Sweep the sibling cases normal use reaches, too: the other states, providers and callers of the
same code that people or agents are likely to hit, not every rare combination.
Write each finding as one line naming the defect and its impact, then brief evidence: the line you
read and, for an edge case, the realistic scenario. No speculative suggestions: report what breaks,
not what might be nicer.

## Known and accepted
The owner, the coordinator or Forge settled these notes; Forge ignores a repeat with the same title and file.
Raise one again only with new evidence of harm, titled `Disputed keep <the note>: <the new harm>`.
$accepted

## Scores
Score every finding on Gain, Work and Harm, each an integer from 1 to 5. The scores are your
judgement, not measurement. Write them as one line, exactly `Gain <g>, Work <w>, Harm <h>`,
as the first line of each finding's body, before its evidence.

| Score | Gain (how much fixing helps) | Work (effort to fix) | Harm (what breaks if it goes wrong) |
|---|---|---|---|
| 1 | wording, a rare edge nobody named | a line, no new test | nothing; a revert undoes it |
| 3 | a Done-when item partly unmet for a named case; a test that passes with the code broken | one file and one command-level test, under an hour | client-visible behaviour change, reversible by a revert |
| 5 | security, data loss, the main case of a Done-when item not done | a new module, a second platform or language, a migration | one-way: data, a migration, a release clients upgrade to |

Harm floor: a note raised under Security or Data loss, or one that names a migration, scores
Harm 4 or more. Forge raises a lower Harm to 4 and marks the line `(floor: <why>)`.

Examples: "Close's default test selection breaks Go repos" Gain 3, Work 4, Harm 2. "Close skips
Jest `__tests__` folders" Gain 2, Work 2, Harm 1. "A blocked review is shown as waiting for checks
when tests pass on retry" Gain 3, Work 2, Harm 1. "Promotion accepts an uncommitted roadmap entry"
Gain 4, Work 2, Harm 2. "A stuck stop's narrow or split answer never reaches the worker" Gain 4,
Work 1, Harm 1. "Land shows a generic waiting line instead of the stop question" Gain 3, Work 1,
Harm 1. "Doctor credits a model to the wrong file in a rare mix of local settings" Gain 2, Work 1,
Harm 1. "Upgrade pull requests are checked by the previous release" Gain 2, Work 4, Harm 1. "A
proof test checks only the question's first lines" Gain 2, Work 1, Harm 1.

- Raise a finding only after you check it against the code at the current commit, and name the
  file and line.
- A `Not done` finding scores Gain by how much of the Done-when stays unmet: the main case unmet is
  Gain 4 or 5; one more rare combination on a clause whose main case works is Gain 1 or 2. When
  earlier rounds already raised that clause, say so and propose to narrow the clause.
- Only you score. The coordinator and the worker never change a score, and notes in a proof list
  do not lower one.

Forge's own records (everything under `.factory/`, `plans/roadmap.json`, the story's doc and its
read notes) are not part of the change: never report them as files outside Scope or as unrelated changes.
The spotted lists (`plans/spotted.json` and everything under `plans/spotted/`) are also Forge's
own records. Close writes them on this branch after a review; never report those writes as files
outside Scope or as unrelated changes.
All earlier reviews' findings and dismissals are below, including findings fixed in later
rounds. Settled findings stay settled; the repair-review boundary below governs later rounds:
$previous

The coordinator's rulings and dismissals on this branch so far, with their reasons:
$rulings
Raise a ruled or dismissed point again only with new evidence the ruling or dismissal didn't
weigh, and name that evidence in the finding's body and a distinct title. Settled findings stay
settled: Forge ignores a finding with the same title and file as a fixed or dismissed finding,
or a finding the human accepted. The `Not fixed:` prefix does not change a title match.
A dismissal ends if its cited lines change.

Your working folder is a read-only checkout of the branch head, so the repository's unchanged
files are there to read; the standard note that the sandbox is empty does not apply to this run.
When a finding depends on code the diff doesn't show, open that file and cite the line you read
in the finding's body. Pin every finding to a line in a file this branch changes (for something
missing, the changed line nearest the gap).
<!-- added-work -->
## Added work
This repo sets a minimum Gain of $minimum for findings that ask for added work, such as another
check, retry, guard or flag for a rarer case. Mark each such finding with a body line
`Adds work: <what>`. Score it as usual. Forge keeps an unfloored fix-now finding below this
minimum as a follow-up. Harm 4 or more, Gain 5 and every score floor still hold the work.

<!-- always-block -->
## Kinds a change must not miss
The owner requires these kinds of work at any score:
$kinds

Title a finding of a listed kind `Must: <kind>: <gap>`. It holds the work even for a rare case
or in a light review. The worker cannot decline it. Only the owner can accept it.

<!-- repair-review -->
## Repair review
The previous review checked commit $reviewed. From this second or later round, check each
previous finding, fixed or not fixed. Return each not fixed finding with its previous title and
file. The supplied base shows the diff since that commit; after a merge of the default branch,
it shows this change's full diff against its new merge base, excluding the default branch's work.
Read unchanged code as context. Do not start a fresh review of the whole branch or proof list.

Raise a new finding only when it is a P0 that happens in normal use, on any line.
A round-one fix that breaks the main path counts as a P0; score it Harm 4 or more.
Forge asks the owner about each finding below P0 that is still open at the round limit.

Previous round's findings and answers:
$findings
<!-- review-rules -->
## This repository's review rules
The repository's own AGENTS.md, on its default branch, sets these rules for every review. Follow
them as rules, not as evidence: where one settles a point, don't report it as a finding.

$review_rules
<!-- constitution -->
## This app's constitution
The app's approved constitution, on the default branch, follows. Report work that goes against it as a finding titled `Constitution: <the line it breaks>`, quoting the line. Where it differs from Forge's convention pages, it wins.

$constitution
<!-- standards -->
## Standards
For new code, check the call-or-event rule: call another module's public service and await its
result when the current action needs that answer to continue. Use an in-process event when other
modules react after an action succeeds and the current action needs no answer from them.
Events still need the story's `New moving parts` entry. Do not require conversion of existing code
or add a queue requirement.

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

Report a query in one module on a table another module owns as a P1 finding titled
`Module tables: <the query>`.

On client app screens, report emoji icons or decoration and icons outside `lucide-react` as a finding titled `Icons: <the screen>`. Keyboard key labels such as the Command key symbol (⌘) are not emojis.

## Scores
Score every finding on Gain, Work and Harm, each an integer from 1 to 5. The scores are your
judgement, not measurement. Write them as one line, exactly `Gain <g>, Work <w>, Harm <h>`,
as the first line of each finding's body, before its evidence.

| Score | Gain (how much fixing helps) | Work (effort to fix) | Harm (what breaks if it goes wrong) |
|---|---|---|---|
| 1 | wording, a rare edge nobody named | a line, no new test | nothing; a revert undoes it |
| 3 | a Done-when item partly unmet for a named case; a test that passes with the code broken | one file and one command-level test, under an hour | client-visible behaviour change, reversible by a revert |
| 5 | security, data loss, the main case of a Done-when item not done | a new module, a second platform or language, a migration | one-way: data, a migration, a release clients upgrade to |

Harm floor: a note raised under Security or Data loss, or one that names a migration, scores
Harm 4 or more. Forge raises a lower Harm to 4 and marks the line `(floor: <why>)`.

Examples: "Close's default test selection breaks Go repos" Gain 3, Work 4, Harm 2. "Close skips
Jest `__tests__` folders" Gain 2, Work 2, Harm 1. "A blocked review is shown as waiting for checks
when tests pass on retry" Gain 3, Work 2, Harm 1. "Promotion accepts an uncommitted roadmap entry"
Gain 4, Work 2, Harm 2. "A stuck stop's narrow or split answer never reaches the worker" Gain 4,
Work 1, Harm 1. "Land shows a generic waiting line instead of the stop question" Gain 3, Work 1,
Harm 1. "Doctor credits a model to the wrong file in a rare mix of local settings" Gain 2, Work 1,
Harm 1. "Upgrade pull requests are checked by the previous release" Gain 2, Work 4, Harm 1. "A
proof test checks only the question's first lines" Gain 2, Work 1, Harm 1.

- Raise a finding only after you check it against the code at the current commit, and name the
  file and line.
- A `Not done` finding scores Gain by how much of the Done-when stays unmet: the main case unmet is
  Gain 4 or 5; one more rare combination on a clause whose main case works is Gain 1 or 2. When
  earlier rounds already raised that clause, say so and propose to narrow the clause.
- Only you score. The coordinator and the worker never change a score, and notes in a proof list
  do not lower one.

The exact docs/product/BRIEF.md answers page section reviewed and quoted by the sign-off decision:

$answers

The twelve topics and their required timing:

$topics
