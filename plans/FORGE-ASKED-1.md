# Build only what was asked

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- Every app that Forge builds, and Forge itself, follows four principles:
  1. Is it needed at all? Deleting beats fixing.
  2. Add work only when how often a problem happens, times how bad it is, is at least twice the
     cost: F x H >= 2 x C. Each is scored from 1 to 3. F: rare 1, weekly 2, daily 3, for the
     first 1,000 users. H: cosmetic or the person's own data 1, wrong information or a broken
     step 2, a P0 3. C: 20 lines or fewer with no model call or user step 1; up to about 150
     lines, or one model call or user step 2; more, or a new table, job, workflow or settings
     flag 3.
  3. Choose the simplest option.
  4. Rules are stated, not policed.
  (Source: your request, 27 Oct 2026)
- A new app's constitution lists the four principles as fixed principles. Forge's own repo lists
  them in its review rules. (Source: your request, 27 Oct 2026)
- Before a worker writes code, it answers the principles in its three planning lines: what needs
  the change and why deleting does not solve it, the simplest option with F x H and 2 x C for
  each check, retry, guard or flag it adds, and the code it reuses. The cold read and the review
  apply the same principles. (Source: your request, 27 Oct 2026)
- A cold-read or review note that asks for added work beyond the Done-when items, such as another
  check, retry, guard or flag, shows its F x H and 2 x C. When F x H is less than 2 x C, the note
  does not stop the work. A review keeps it in Known issues as a known limit, and a cold read
  keeps it with its disposition in the read notes, as today. Security, data loss and migration
  notes still stop the work. A check that a Done-when item promises is not added work: when it
  is missing, the work stops, as today. (Source: your request, 27 Oct 2026)
- Each item in a story plan's "What changes for you" ends with its source: a client note, a brief
  answer, a decision, a screen marked Build now at sign-off, a fixed rule of the app, or your own
  request with its date. (Source: your request, 27 Oct 2026)
- An addition with no source gets a "Not asked for" note. For a small addition, the note is
  advice and does not stop the work. For a large addition (a new table, background job, workflow
  or settings flag, or about 150 lines or more), the note stops the work until the addition names
  a source or moves to the idea list. (Source: your request, 27 Oct 2026)
- Each "Not asked for" note says in plain words what was added, which sources Forge checked and
  found silent, and the two ways forward: name the source, or move the addition to the idea list.
  For a large addition, it also says that the addition is large and why. Nobody is stopped
  without a reason that they can act on. (Source: your request, 27 Oct 2026)
- Forge checks plans and code against the screens marked Build now at sign-off, never against the
  canvas. Until sign-off can mark screens Build now, the Build now screens are the ones that the
  story's Done-when items name. Workers build, and reviews check, only the fields of those
  screens. The canvas can still show the whole product, with its later screens.
  (Source: your request, 27 Oct 2026)
- When a worker or planner thinks of something useful that nobody asked for, it adds one line to
  the repo's idea list (`plans/ideas.md`) and builds nothing for it. The starter's fixed defaults
  stay the base of each app, and nothing more is built just in case.
  (Source: your request, 27 Oct 2026)
- A new repo gets all of this from the start. An existing repo gets it when it upgrades Forge and
  runs `forge sync`. An existing app's approved constitution does not change; its workers, cold
  reads and reviews still get the principles. (Source: your request, 27 Oct 2026)

Design: none (no screens; it changes plan, constitution, cold-read, review and worker text)

## Why

Forge and the apps it builds collect checks, guards and flags for rare cases, and features that
nobody asked for. Each extra adds code, tests, checks and review time, and it slows every later
change. Today a review holds added work by a fixed score bar that does not weigh the cost. The
cold read and the review flag only work that no Done-when item needs, so an extra that a
Done-when line can be stretched to cover gets through. Nobody records where a request came from,
so a reader cannot tell an asked-for field from a guess.

## Done when

1. **A new app's constitution, the worker's planning lines, the cold read, the review and Forge's own review rules state the four principles, with the scales for F, H and C.**
2. **A cold-read or review note that asks for added work beyond the Done-when items shows its F x H and 2 x C. When F x H is less than 2 x C, the note does not hold the work: a review keeps it in Known issues as a known limit, and a cold read keeps it with its disposition in the read notes. Security, data loss and migration notes still hold the work, and so does a missing check that a Done-when item promises.**
3. **Every story plan names a source for each screen, field, endpoint, tool and setting that it adds.**
4. **The cold read and the review report an addition with no source as "Not asked for". A small one is advice. A large one (a new table, background job, workflow or settings flag, or about 150 lines or more) holds the work until it names a source or moves to the idea list. The note says what was added, which sources were checked, the two ways forward, and for a large one why it is large. Plans and code are checked against the screens marked Build now at sign-off, or until sign-off can mark them, the screens that the story's Done-when items name, never against the canvas.**
5. **A worker or planner who thinks of something useful that nobody asked for adds one line to the idea list and builds nothing for it, and nothing is built beyond the starter's fixed defaults just in case.**
6. **A new repo gets these rules from the start, and an existing repo gets them on upgrade with forge sync, with its approved constitution unchanged.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request.

Trade-off: the reader and the reviewer judge F, H and C, and whether an addition is large. No
code counts lines or checks the numbers.

Trade-off: a small addition with no source can ship. The rule is stated, and the note is advice.

Trade-off: in a review, a worker can clear a "Not asked for" note with a `Source:` line in its
commit that names a real client note, brief answer, decision or Build now screen. The plan's
approved items do not change, so no new approval is needed. The reviewer opens the named source.

Trade-off: until sign-off can mark screens Build now (the sign-off story adds that mark), the
Build now screens are the ones that the story's Done-when items name. A field that the canvas
shows on such a screen, and that no source asks for, is not built.

Trade-off: two branches that each add an idea line can conflict on `plans/ideas.md` at merge.
`forge start` already carries idea lines into branches, so this is not new. Keep both lines.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-ASKED-1"`. Tests run the forge command and never
import forge.

### How added work maps to the existing bar (FORGE-BAR-1)

- The rule reuses FORGE-BAR-1's `Adds work:` body line. Today the reviewer is asked for it only
  when the repo sets `added_work_min_gain` (the `<!-- added-work -->` block, added by
  `src/forge/review.py` `instructions` at line 380). Text P2 asks for it on every cold read and
  review, as `Adds work: <what>; F <f> x H <h> = <p>; 2 x C = <c>`. `score.ADDS_WORK`
  (`^[ \t]*Adds work:[ \t]*\S`) still matches that line.
- When p is less than 2 x C, the reviewer scores Gain 2 or less. `score.bar` then gives
  "live with", and `src/forge/known_issues.py` keeps the finding as lived with: the known limit.
  A finding under Security or Data loss, or one that names a migration, keeps its Harm-4 floor,
  and `score.bar` still gives "block".
- A `Not done` finding that names an approved Done-when item is marked `required_done_when`
  (`src/forge/review.py` line 1067) and blocks at any score (`blocking`, line 229). Text P2 keeps
  the two apart in words: work that a Done-when item promises is `Not done`, and it keeps
  blocking; work beyond the Done-when is added work under F x H against 2 x C, and its title is
  never `Not done`. No close code changes.
- In a cold read, a note below the bar keeps its disposition in the read notes (`src/forge/story.py`
  line 389), as today. No cold-read code changes, and nothing new goes to Known issues.
- `added_work_min_gain`, `always_block` and the `added-work` block do not change, and they still
  apply on top when a repo sets them. No score, close or review code changes for this rule.

### How "Not asked for" maps to the existing bar

- A large addition is cost 3 on the C scale. It goes under a new Raise line (text B). The reader
  scores it Gain 4 with Work 1 or 2, which holds a plan (`cold-read.md`: "Otherwise, Gain 4, or
  Gain 3 with Harm 3, holds the plan only with Work 1 or 2") and blocks a merge (`review.md`
  line 186).
- A smaller addition is advice: `Advisory:` in a cold read, a P2 advice form in a review, scored
  Gain 1 or 2, so it is lived with. Rules are stated, not policed.

### Why the source goes on the "What changes for you" items

- The owner approves that section, so the sources are part of the approval. A Tasks-table column
  would sit below `## For the builders`, where edits need no approval.
- The worker brief already shows that section (`src/forge/worker.py`,
  `what=doc.get("What changes for you", "")`). The task review does not: `src/forge/review.py`
  `instructions` passes the row's `what it delivers`, the covered Done-when items, their details,
  Risks and Notes, but not this section. One added value in that `values.update(...)` call gives
  the reviewer the same text.
- Plans that `forge start` drafts replace the template's placeholder with the intake's Change
  lines (`src/forge/intake.py` `act`), so the template comment reaches only `forge story new`
  plans. The planning paragraph in the agent's guide reaches every plan.

### Why the idea list needs no new code

- Workers and planners append one line to `plans/ideas.md` in their own branch, in the format that
  `forge start`'s later lane writes (`- <YYYY-MM-DD>: <idea>`, `src/forge/intake.py` `act`). They
  do not run `forge start`: its intake is a model call, and `start.md` keeps the later lane for the
  owner's "later".
- The review never lists the line as outside Scope: `src/forge/review.py` drops every path under
  `BOOKKEEPING = (".factory/", "plans/")` from the changed files it reports (line 328). A branch
  that changes only `plans/` closes with no model call (`src/forge/close.py`, `records_only`).
- `plans/ideas.md` reaches the default branch with the branch's merge, and `forge start` already
  carries waiting entries into the next item.

### The pinned texts

Each block below goes in exactly. Workers keep the line breaks of the file they edit.

**P1. The four principles.** These words are the one statement of the principles. Texts P2, P3,
P4 and P5 use them:

```
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
```

**P2. The cold read and the review (PRINCIPLES).** In `src/forge/templates/cold-read.md` and
`src/forge/templates/review.md`, a new paragraph right after the paragraph that ends
``names its line as `Raise: <line>` at the start of its evidence.``, the same text in both: P1,
then:

```
Mark each finding that asks for added work beyond the Done-when items (another check, retry, guard
or flag) with a body line `Adds work: <what>; F <f> x H <h> = <p>; 2 x C = <c>`. When p is less
than 2 x C, score its Gain 2 or less: it is a known limit and does not hold the work. A review
keeps it in Known issues; a cold read keeps it with its disposition in the read notes. A finding
under Security or Data loss, or one that names a migration, keeps its Harm floor and still holds
the work. A check that a Done-when item promises is not added work: report it missing as
`Not done: <the item>`, which holds the work at any score. Never title an added-work finding
`Not done`.
```

It sits outside the `## What counts` boundary, so
`tests/test_fix_lean_review_prompts.py::test_1`, which compares the two boundaries, keeps passing.

**P3. The worker's planning lines (PRINCIPLES).** In `src/forge/templates/brief.md`
`## Build simple`, replace the three placeholder lines under `Before coding:` with:

```
Need: <the job or problem that needs this change, and why deleting code or a step does not solve it>
Simplest option: <the first rung of the ladder that works, and why; for each check, retry, guard or flag you add, its F x H and 2 x C>
Existing code reused: <the existing code you will use, or none and why>
```

Keep the labels: `src/forge/review.py` `before_coding` parses `Need:`, `Simplest option:` and
`Existing code reused:`, each on one line. After the line that ends
`Forge copies them into the pull request summary and gives them to the reviewer.`, add
"Answer these principles in the three lines:" and then P1.

**P4. The constitution outline (PRINCIPLES).** In `src/forge/templates/skill.md`
`## App constitution`, in the outline's code block, a new section after
`The product facts are in docs/product/BRIEF.md.` and before `## Defaults`:

```
## Principles
- Is it needed at all? Deleting beats fixing.
- Add work only when F x H >= 2 x C. F, for the first 1,000 users: 1 rare, 2 weekly, 3 daily. H: 1 cosmetic or the person's own data, 2 wrong information or a broken step, 3 a P0. C: 1 for 20 lines or fewer with no model call or user step, 2 for up to about 150 lines or one model call or user step, 3 for more, or a new table, job, workflow or flag.
- Choose the simplest option.
- Rules are stated, not policed.
```

After the code block, before `Make each architecture choice yourself`, add: "Copy `## Principles`
into every app's constitution word for word, and ask nothing about it. Do not add it to an
approved constitution: the principles reach that app through its briefs, cold reads and reviews."

**P5. Forge's own review rules (PRINCIPLES).** In this repo's `AGENTS.md`, under `## Review rules`,
a new subsection before `### Forge's 13 principles`: the heading `### Four simplicity principles`,
the line "These govern every change to Forge, as they govern every app that Forge builds.", then
P1's four numbered lines.

**A. The source list (SOURCES).** These words are the one list of sources. Texts B to H use them.

> a client note in `docs/product/DISCOVERY.md`, an answer in `docs/product/BRIEF.md`, a decision
> in `docs/decisions/`, a screen marked Build now at sign-off, a fixed rule in
> `docs/product/CONSTITUTION.md`, or the human's own request: a dated source on a plan item, or a
> fix's Why and Done-when line

**B. The Raise line (SOURCES).** In `cold-read.md` and `review.md`, under `## What counts`, a new
line after the two-line `- Moving part:` entry, the same bytes in both files:

```
- Not asked for: a large addition that no source asks for: a new table, background job, workflow
  or settings flag, or about 150 lines or more. A source is a client note in
  `docs/product/DISCOVERY.md`, an answer in `docs/product/BRIEF.md`, a decision in
  `docs/decisions/`, a screen marked Build now at sign-off, a fixed rule in
  `docs/product/CONSTITUTION.md`, or the human's own request: a dated source on a plan item, or a
  fix's Why and Done-when line. The canvas is not a source.
```

`tests/test_fix_lean_review_prompts.py::test_1` asserts that the two `What counts` boundaries are
equal apart from the `Not done` line, so the two copies must match.

**C. The note (SOURCES).** In both files, a new paragraph right after text P2, the same text in
both:

```
Title an addition with no source `Not asked for: <what was added>`. Write its evidence in plain
words for the developer and the client: what the change adds, with its file and line or plan item;
which sources you checked and found silent; and the two ways forward: name its source, or remove it
and add one line for it to `plans/ideas.md`. Check plans and code against the screens marked Build
now at sign-off, never against the canvas, which can show later screens. Until sign-off can mark
screens Build now, the Build now screens are the ones that the story's Done-when items name. What
the app's fixed rules or the starter already give is not an addition. A large addition goes under
the Raise line above: say
that it is large and why, score it Gain 4, and Work 1 or 2, because either way forward is small,
so it holds the work, and include `Case: normal use - <the addition>`. A smaller addition is
advice: in a cold read start it with `Advisory:`, in a review report it as P2, and score it Gain 1
or 2.
```

In `review.md` `## What blocks the merge`, extend the advice-form list
``(`Simpler:`, `Later:`, `Follow-up:`, `Simpler (existing):`)`` with `` a small `Not asked for:` ``.

**D. The task review gets the approved items (SOURCES).** In `review.md`, in the `<!-- task -->`
block, a new section between `## Done when` (after its `$context` line) and `## Builder guidance`:

```
## What changes for you
The owner approved these items with the plan. Each ends with its source:
$changes
```

In `src/forge/review.py` `instructions`, in the task branch's `values.update(...)`, add
`changes=doc.get("What changes for you", "none"),` after the `delivers=...` argument. The fix block
does not change: it already has the fix's Why and Done-when line.

**E. The plan template (SOURCES).** In `src/forge/templates/story.md`, replace the placeholder line
under `## What changes for you`,
`<What the people who use this will notice, in plain English. No IDs, codes or jargon.>`, with:

```
<What the people who use this will notice, in plain English. No IDs, codes or jargon. End each
item with its source in plain words, such as (Source: the client's note on late orders, 12 Oct).
A source is a client note, a brief answer, a decision, a screen marked Build now at sign-off, a
fixed rule of the app, or the owner's own request with its date. Name each screen, field,
endpoint, tool and setting that the plan adds in one of these items.>
```

**F. The agent's guide (SOURCES).** In `src/forge/templates/skill.md`:

- In `## Save decisions and ideas`, replace the line that starts
  ``- `forge start` keeps `plans/ideas.md` `` with:
  "- `forge start` keeps `plans/ideas.md`, a short dated list, when the owner says later, and
  carries waiting entries into the next fix or story. When you, a planner or a worker think of
  something useful that nobody asked for, add one line `- <YYYY-MM-DD>: <the idea>` to
  `plans/ideas.md` in the branch in hand and build nothing for it."
  Keep the next line (`Remove an entry when the owner says to do it now, ...`).
- In `## Planning a story`, a new paragraph after the one that ends
  `New repos get this guide at init; existing repos get it after upgrading Forge and running sync.`:
  "End each item of a plan's What changes for you with its source in plain words, such as
  `(Source: the client's note on late orders, 12 Oct)`. A source is a client note in
  `docs/product/DISCOVERY.md`, an answer in `docs/product/BRIEF.md`, a decision in
  `docs/decisions/`, a screen marked Build now at sign-off, a fixed rule in
  `docs/product/CONSTITUTION.md`, or the human's own request with its date. Name each screen,
  field, endpoint, tool and setting that the plan adds in one of these items. The canvas can show
  later screens; plan only the screens marked Build now. The starter's fixed rules are the base:
  plan nothing beyond them just in case."
- In `## Cold read findings`, a new bullet after the `Unproven:` / `Trap:` bullet:
  "- `Not asked for: <what>` on a large addition: name the item's source, or cut the addition and
  add one line for it to `plans/ideas.md`. On a small addition it is advice: act on it only when
  that is cheap."
- `forge sync` rewrites `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`.

**G. The worker brief (SOURCES).** In `src/forge/templates/brief.md`, a new paragraph after the
`Spotted:` paragraph, which ends `fix it and name it in your handoff.`:

```
Build only what your Done-when items and the story's What changes for you name. When you think of
something useful that nobody asked for, build nothing for it: add one line
`- <YYYY-MM-DD>: <the idea in one plain sentence>` at the end of `plans/ideas.md` and name it in
your handoff. When a review reports `Not asked for: <what>` on a large addition, remove the
addition and add its idea line, or, when a client note, brief answer, decision or Build now screen
asks for it, add `Source: <what>: <where it was asked>` to your commit body.
```

**H. The standards page (SOURCES).** In `src/forge/standards.md` (in every worker brief and review,
and synced to `.claude/skills/forge/standards.md` and `.codex/skills/forge/standards.md`):

- Replace principle 3 with:
  "3. **Only what was asked.** Every task, screen, field, endpoint, tool, setting, role and
  integration traces to a Done-when item and to a source: a client note, a brief answer, a
  decision, a screen marked Build now at sign-off, a fixed rule of the app, or the owner's own
  request. An idea that nobody asked for goes as one line to `plans/ideas.md`, and nothing is
  built for it. Anything else is cut, or goes under the spec's Out of scope."
- At the end of principle 4, add:
  "The starter's fixed rules are the base of each app. Build nothing beyond them just in case:
  modules, contracts, a schema per module and `services.toml` already leave room to grow."

**I. Screens in the Build now scope (SOURCES).** Three places tell workers and reviewers to build
every field of a screen's `SCREENS.md` section. Each one narrows to the Build now screens:

- `src/forge/templates/review.md`, the `<!-- design-screens -->` block: replace its first sentence
  with "Report as P1 a built screen that lacks a component or field its section of
  `${design_folder}SCREENS.md` lists, when that screen is a screen marked Build now at sign-off,
  or, until sign-off can mark screens Build now, a screen that this story's Done-when items name.
  Do not report a field missing from any other screen." Keep the next two sentences.
- `src/forge/templates/brief.md`, the `<!-- if screen-design -->` block: replace its sentence with
  "Build each screen you touch that is marked Build now at sign-off, or, until sign-off can mark
  screens Build now, that your Done-when items name, with the components and fields its section of
  `${design_folder}SCREENS.md` lists. Build nothing for any other screen or field."
- `src/forge/worker.py`, the continued brief (the `if owned_design:` string near line 598): the
  same sentence as the brief, with `{owned_design}` in place of `${design_folder}`. This is a text
  change in one string; the brief and its continued copy must stay the same.

The prototype's light review (`review-light.md`), the sign-off review and the design check keep
their own blocks and do not change: before sign-off the canvas is the scope.

### Done-when details

1. The four principles are stated (PRINCIPLES).
   - Texts P1 to P5.
   - Test: `tests/test_four_principles.py::test_1_the_principles_reach_the_guide_and_the_worker`,
     parametrised `new init` and `previous release`, set up as
     `tests/test_deployment_requires_an_explicit_request.py::test_1` does (`_fresh_client`; the
     `tests/fixtures/forge-v1.2.2` Forge's init, then the version move and `forge sync`). Each
     case: the synced `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` have
     `## Principles`, `Add work only when F x H >= 2 x C. F, for the first 1,000 users` and
     ``Copy `## Principles` into every app's constitution word for word``; the worker brief from
     `forge work` (`install_claude`, `calls(log)[-1]["brief"]`) has
     `why deleting code or a step does not solve it`, `its F x H and 2 x C`,
     `Rules are stated, not policed` and `3 a P0`.
   - The cold-read and review side of P1 is in test 2. P5 is this repo's own review-rule text:
     the review reads it through the existing review-rules block, and the review of this part
     checks the text.
2. Added work by F x H against 2 x C (PRINCIPLES).
   - Text P2. The mapping is in "How added work maps to the existing bar" above.
   - Test: `tests/test_four_principles.py::test_2_added_work_is_weighed_against_its_cost`,
     parametrised `new-client` and `adopted-v1.2.2`, with the setup of
     `tests/test_fix_lean_review_prompts.py::test_1` (`env`, the `READER` reader, `forge read` for
     the cold-read prompt, `env.close` and `env.prompt()` for the review prompt). Each prompt has
     `Four principles govern every change.`, `Adds work: <what>; F <f> x H <h> = <p>; 2 x C = <c>`
     `When p is less than 2 x C, score its Gain 2 or less`,
     `a cold read keeps it with its disposition in the read notes` and
     `A check that a Done-when item promises is not added work`. Then, with the scored-review stub
     that `tests/test_score_notes.py` uses (`_scored`), a review that returns one finding with
     `Adds work: a retry; F 1 x H 1 = 1; 2 x C = 4` and `Gain 2, Work 2, Harm 1` lets close pass
     and lists it under Known issues; a finding raised under Security with
     `Gain 2, Work 2, Harm 4` and the same `Adds work:` line still blocks.
3. Plans name their sources (SOURCES).
   - Texts E and F (the planning paragraph).
   - Test: `tests/test_build_only_what_was_asked.py::test_1_plans_ask_for_a_source_on_each_item`,
     parametrised `new-client` and `adopted-v1.2.2` (the fixture copy and version move of
     `tests/test_fix_lean_review_prompts.py::test_1`, then `forge sync`). Each case: run
     `forge story new SHOP "Shoppers can save a basket"` as `tests/test_app_constitution.py` does,
     and read `plans/SHOP.md` in the story checkout: its `## What changes for you` has
     `End each item with its source in plain words`. The synced `.claude/skills/forge/SKILL.md`
     and `.codex/skills/forge/SKILL.md` have `Name each screen, field, endpoint, tool and setting
     that the plan adds in one of these items` and `plan only the screens marked Build now`.
4. Unsourced additions are "Not asked for" (SOURCES).
   - Texts B, C and D.
   - Test: `tests/test_build_only_what_was_asked.py::test_2_unsourced_additions_are_not_asked_for`,
     parametrised `new-client` and `adopted-v1.2.2`, with the setup of test 2 in
     `tests/test_four_principles.py`. Both cases: each prompt's `## What counts` has text B's line,
     and each prompt has text C's phrases `Title an addition with no source`,
     `which sources you checked and found silent`,
     ``name its source, or remove it and add one line for it to `plans/ideas.md` ``,
     `say that it is large and why`, `A smaller addition is advice` and
     `never against the canvas`. New-client case, also: approve a SHOP doc whose first
     What-changes item ends `(Source: the owner's request, 27 Oct)` with
     `env.start_approved_task(doc)`, close it, and check that `env.prompt()` has
     `## What changes for you` and that item. The adopted case skips this step: the task review
     takes the same path in both repos.
   - `tests/test_fix_lean_review_prompts.py::test_1` keeps passing unchanged: it proves text B is
     the same in both prompts.
   - Text I. Test: change `tests/test_design_context.py::test_1`, which already runs the first
     and the continued `forge work` brief and the review for a story with its own design folder,
     on new and adopted repos and both worker families: in the cases with a design folder, the
     brief has `that your Done-when items name` and `Build nothing for any other screen or field`,
     and the review prompt has `Do not report a field missing from any other screen`. Its current
     assertions (`Report as P1 a built screen`, `component or field`) stay true.
5. Extras go to the idea list; the starter is the base (SOURCES).
   - Texts F (the idea-list line and the cold-read bullet), G and H.
   - Test: `tests/test_build_only_what_was_asked.py::test_3_useful_extras_go_to_the_idea_list`,
     parametrised `new init` and `previous release`, set up as in test 1 of
     `tests/test_four_principles.py`. Each case: the worker brief has `build nothing for it`,
     `plans/ideas.md`, `Source: <what>: <where it was asked>` and, from the standards page,
     `Only what was asked` and `Build nothing beyond them just in case`; the synced
     `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` have
     ``add one line `- <YYYY-MM-DD>: <the idea>` to `plans/ideas.md` ``; the synced
     `.claude/skills/forge/standards.md` and `.codex/skills/forge/standards.md` have
     `Only what was asked`.
6. New and existing repos (PRINCIPLES): the `previous release` and `adopted-v1.2.2` cases of tests
   1 and 2, and in test 1's `previous release` case, after `forge sync`, the repo has no
   `docs/product/CONSTITUTION.md` (sync writes and changes no constitution).

### New and existing repos

- **New repos** (`forge init`, either starter, and adoption of a repo with history): the cold
  read, review and plan template text come from the installed Forge, and init writes the agent's
  guide and the standards copies, so every plan, read, review and worker brief has the rules from
  the first item. The agent writes `## Principles` into the app's constitution when it first
  writes the constitution. Tested by the `new-client` and `new init` cases.
- **Existing repos** (on upgrade to this release): the cold read, review, plan template, worker
  brief and the standards page in briefs and reviews come from the installed Forge, so they change
  with the upgrade. `forge sync` rewrites the agent's guide and the standards copies. No repo file
  needs a migration. The approved constitution does not change, because the owner approved it
  (`docs/decisions/NNNN-app-constitution.md`); the principles reach that app through its briefs,
  cold reads and reviews. A plan approved before the upgrade keeps its approval, because an
  approval binds the text of its own "What changes for you". A review of that plan's parts can
  find a large addition with no source; the worker then names the source with a `Source:` line or
  cuts the addition. Tested by the `adopted-v1.2.2` and `previous release` cases.

## Tasks

<!-- One row per task. Covers: the Done-when numbers it delivers, at most three. Scope: the paths
it may change. Tests: the tests it adds or changes. After: the tasks it waits for. When two tasks
share a function, field, file format or command, the first task pins it: it commits the shared
names and stubs plus one test that crosses both sides, and the tasks that use it list it under
After. Split tasks so each owns its files; shared lines (command table, guide list, registry) go
to one task or a small last wiring task; After only when a task needs another task's code. The
Developer column is optional: the lead fills or changes a GitHub username here, below For the
builders, without another approval. Leave it blank for an unassigned part. Forge next uses
the caller's GitHub login; another developer may start it with a warning. Existing tables
without Developer still work. The moving-parts line stays last: "none", or each new dependency, service, datastore,
queue, background job or abstraction layer, with the Done-when item that needs it. -->

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| PRINCIPLES | The four principles | The principles in the constitution outline, the worker's planning lines, the cold read, the review and Forge's own review rules, and the F x H against 2 x C rule for added work, on new and existing repos | 1, 2, 6 | `src/forge/templates/cold-read.md`, `src/forge/templates/review.md`, `src/forge/templates/brief.md` (`## Build simple`), `src/forge/templates/skill.md` (`## App constitution`), `AGENTS.md` (`## Review rules`), `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_four_principles.py` (new) | `tests/test_four_principles.py` (`test_1`, `test_2`); `tests/test_fix_lean_review_prompts.py::test_1` unchanged | | no | |
| SOURCES | Sources and the idea list | The source on each plan item, the "Not asked for" note (advice when small, holding the work when large), the approved items in the task review, the Build now scope for screens in the brief and the review, the idea-list rule and the starter base in the brief, the guide and the standards page, on new and existing repos | 3, 4, 5 | `src/forge/templates/story.md`, `src/forge/templates/cold-read.md`, `src/forge/templates/review.md`, `src/forge/review.py` (one value in `instructions`), `src/forge/worker.py` (one string in the continued brief), `src/forge/templates/brief.md`, `src/forge/templates/skill.md` (`## Save decisions and ideas`, `## Planning a story`, `## Cold read findings`), `src/forge/standards.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md`, `.claude/skills/forge/standards.md` and `.codex/skills/forge/standards.md` (rewritten by `forge sync`), `tests/test_build_only_what_was_asked.py` (new), `tests/test_design_context.py` (`test_1`) | `tests/test_build_only_what_was_asked.py` (`test_1`, `test_2`, `test_3`); the changed `tests/test_design_context.py::test_1` | PRINCIPLES | no | |

SOURCES waits for PRINCIPLES. Both change `cold-read.md`, `review.md`, `brief.md` and `skill.md`,
in different paragraphs, so Forge refuses to start SOURCES while PRINCIPLES is open. SOURCES' text
C sits after PRINCIPLES' text P2, and its large-addition rule uses P1's C scale. Each part updates
the guide and the brief for its own behaviour, as this repo's review rules require.

New moving parts: none

## Notes

- Owner decisions (27 Oct 2026, settled): build only what is asked, in every client repo and in
  Forge itself; every screen, field, endpoint, tool or setting that a plan adds names its source
  (a client note, a brief answer, a decision record, a screen marked Build now at sign-off; in
  Forge's own repo, the owner's request or a decision); the canvas may show the whole product,
  and code is checked against the signed Build now scope; a useful extra becomes one line in the
  existing idea list and nothing is built for it; the starter's fixed defaults stay the base, and
  nothing beyond them is built just in case; new repos get it at init, existing repos with
  `forge sync`; one or two parts, one test per rule, a new-repo case and one earlier-adopted case
  each.
- Owner addition (27 Oct 2026): FDEs and clients must not feel blocked for no reason. Each "Not
  asked for" note says what was added, why Forge sees no source (which sources it checked), and
  the two ways forward: name the source, or move it to the idea list.
- Owner changes (27 Oct 2026): four core principles for every app and for Forge (needed at all,
  F x H >= 2 x C with the stated 1-3 scales, simplest option, rules stated not policed), in the
  constitution template, this repo's AGENTS.md, the worker's before-coding lines and the cold-read
  and review prompts; the source rule is stated, not enforced, so a missing source is advice
  explained with F x H against 2 x C; the review weighs added work by F x H >= 2 x C, and below it
  the finding becomes a known limit, reusing FORGE-BAR-1's bar where that is simplest.
- Owner refinement (27 Oct 2026): a missing source is advice for a small addition and holds the
  work for a large one. Large uses C = 3: a new table, background job, workflow or settings flag,
  or about 150 lines or more. The note says it is large and why.
- Planner choices the owner did not make: (1) the source goes at the end of each "What changes
  for you" item, not in a Tasks-table column; (2) the source list also counts the app's fixed
  rules and the human's own dated request in every repo, so a feature's built-in CSV export or
  history is not "Not asked for"; (3) added work below F x H >= 2 x C maps to Gain 2 or less, so
  Forge keeps it as lived with, and FORGE-BAR-1's `Adds work:` line is now asked for on every read
  and review, with no code change; (4) in a review, a `Source:` commit line that names a real
  source clears a large-addition note with no new plan approval; (5) workers and planners write
  the idea line in their own branch, with no `forge start` call; (6) until sign-off can mark Build
  now, the Build now screens are the ones that the story's Done-when items name, and workers and
  reviews build and check only their fields (coordinator, round 1); (7) the prototype's light review and the sign-off
  review do not change; (8) sync does not add `## Principles` to an approved constitution; (9) the
  title stays "Build only what was asked", because the story's state and roadmap entry hold that
  title.
- Depends on nothing: the sign-off story adds the Build now mark. This story only reads it, and
  the rule for repos without the mark (text C) covers the time before it lands.
- `src/forge/review.py` is 1,213 lines today, over the 1,200-line principle; SOURCES adds one
  line. Spotted for a later trim, not widened here.
