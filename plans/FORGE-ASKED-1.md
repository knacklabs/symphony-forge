# Build only what was asked

1 part · Risks: none one-way · New moving parts: none

## What changes for you

- Each item in a story plan's "What changes for you" ends with its source: a client note, a brief
  answer, a decision, a screen marked Build now at sign-off, a fixed rule of the app, or your own
  request with its date. Every screen, field, endpoint, tool and setting that a plan adds is in one
  of these items. (Source: your request, 27 Oct 2026)
- The cold read and the review report an addition that has no source as "Not asked for". That
  note stops the work until the source is named or the addition is removed.
  (Source: your request, 27 Oct 2026)
- Each "Not asked for" note tells the developer or client, in plain words, what was added, which
  sources Forge checked and found silent, and the two ways forward: name the source, or move the
  addition to the idea list. Nobody is stopped without a reason that they can act on.
  (Source: your request, 27 Oct 2026)
- Forge checks plans and code against the screens marked Build now at sign-off, never against the
  canvas. The canvas can still show the whole product, with its later screens.
  (Source: your request, 27 Oct 2026)
- When a worker or planner thinks of something useful that nobody asked for, it adds one line to
  the repo's idea list (`plans/ideas.md`) and builds nothing for it.
  (Source: your request, 27 Oct 2026)
- The starter's fixed defaults stay the base of each app. Forge builds nothing more just in case:
  modules, contracts, a schema per module and the services list already leave room to grow.
  (Source: your request, 27 Oct 2026)
- A new repo gets these rules from the start. An existing repo gets them when it upgrades Forge
  and runs `forge sync`. (Source: your request, 27 Oct 2026)

Design: none (no screens; it changes plan, cold-read, review and worker text)

## Why

Plans and builds add screens, fields, endpoints, tools and settings that nobody asked for. Each
extra adds code, tests, checks and review time, and it slows every later change. Today the cold
read and the review flag only work that no Done-when item needs. An extra that a Done-when line
can be stretched to cover gets through. Nobody records where a request came from, so a reader
cannot tell an asked-for field from a guess.

## Done when

1. **Every story plan names a source for each screen, field, endpoint, tool and setting that it adds.**
2. **The cold read and the review report an addition with no source as "Not asked for", and that note holds the work. The note says what was added, which sources Forge checked, and the two ways forward: name the source, or move the addition to the idea list. Plans and code are checked against the screens marked Build now at sign-off, never against the canvas.**
3. **A worker or planner who thinks of something useful that nobody asked for adds one line to the idea list and builds nothing for it, and nothing is built beyond the starter's fixed defaults just in case. A new repo gets these rules from the start, and an existing repo gets them on upgrade with forge sync.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. The part reverts with its pull request.

Trade-off: the reviewer judges what counts as an added screen, field, endpoint, tool or setting.
No code counts them. A miss shows in a later review or at the check-back.

Trade-off: in a review, a worker can clear a "Not asked for" note with a `Source:` line in its
commit that names a real client note, brief answer, decision or Build now screen. The plan's
approved items do not change, so no new approval is needed. The reviewer opens the named source.

Trade-off: until sign-off marks screens Build now (the sign-off story adds that mark), every
signed screen counts as Build now.

Trade-off: two branches that each add an idea line can conflict on `plans/ideas.md` at merge.
`forge start` already carries idea lines into branches, so this is not new. Keep both lines.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

The new test file starts with `STORY = "FORGE-ASKED-1"`. Tests run the forge command and never
import forge.

### Why the source goes on the "What changes for you" items

- The owner approves that section, so the sources are part of the approval. A Tasks-table column
  would sit below `## For the builders`, where edits need no approval.
- The worker brief already shows that section (`src/forge/worker.py`,
  `what=doc.get("What changes for you", "")`). The task review does not: `src/forge/review.py`
  `instructions` passes the row's `what it delivers`, the covered Done-when items, their details,
  Risks and Notes, but not this section. One added value in that `values.update(...)` call gives
  the reviewer the same text. A table column would need the same line plus a cell per part.
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

**A. The source list.** These words are the one list of sources. Texts B to H use them.

> a client note in `docs/product/DISCOVERY.md`, an answer in `docs/product/BRIEF.md`, a decision
> in `docs/decisions/`, a screen marked Build now at sign-off, a fixed rule in
> `docs/product/CONSTITUTION.md`, or the human's own request: a dated source on a plan item, or a
> fix's Why and Done-when line

**B. The Raise line.** In `src/forge/templates/cold-read.md` and `src/forge/templates/review.md`,
under `## What counts`, a new line after the two-line `- Moving part:` entry, the same bytes in
both files:

```
- Not asked for: a screen, field, endpoint, tool or setting that the change adds and that no
  source asks for. A source is a client note in `docs/product/DISCOVERY.md`, an answer in
  `docs/product/BRIEF.md`, a decision in `docs/decisions/`, a screen marked Build now at sign-off,
  a fixed rule in `docs/product/CONSTITUTION.md`, or the human's own request: a dated source on a
  plan item, or a fix's Why and Done-when line. The canvas is not a source.
```

`tests/test_fix_lean_review_prompts.py::test_1` asserts that the two `What counts` boundaries are
equal apart from the `Not done` line, so the two copies must match.

**C. The note and its score.** In both files, a new paragraph right after the paragraph that ends
``names its line as `Raise: <line>` at the start of its evidence.``, the same text in both:

```
Title an addition with no source `Not asked for: <what was added>`. Write its evidence in plain
words for the developer and the client: what the change adds, with its file and line or plan item;
which sources you checked and found silent; and the two ways forward: name its source, or remove it
and add one line for it to `plans/ideas.md`. Check plans and code against the screens marked Build
now at sign-off, never against the canvas, which can show later screens. A repo signed off before
sign-off marked Build now treats every signed screen as Build now. A screen, field, endpoint, tool
or setting that the app's fixed rules or the starter already give is not an addition. Score the
note Gain 4, and Work 1 or 2, because either way forward is small, so it holds the work. Include
`Case: normal use - <the addition>`.
```

This maps to the existing bar: Gain 4 with Work 1 or 2 holds a plan (`cold-read.md`, "Otherwise,
Gain 4, or Gain 3 with Harm 3, holds the plan only with Work 1 or 2") and blocks a merge
(`review.md` line 186). No score or close code changes.

**D. The task review gets the approved items.** In `src/forge/templates/review.md`, in the
`<!-- task -->` block, a new section between `## Done when` (after its `$context` line) and
`## Builder guidance`:

```
## What changes for you
The owner approved these items with the plan. Each ends with its source:
$changes
```

In `src/forge/review.py` `instructions`, in the task branch's `values.update(...)`, add
`changes=doc.get("What changes for you", "none"),` after the `delivers=...` argument. The fix block
does not change: it already has the fix's Why and Done-when line.

**E. The plan template.** In `src/forge/templates/story.md`, replace the placeholder line under
`## What changes for you`,
`<What the people who use this will notice, in plain English. No IDs, codes or jargon.>`, with:

```
<What the people who use this will notice, in plain English. No IDs, codes or jargon. End each
item with its source in plain words, such as (Source: the client's note on late orders, 12 Oct).
A source is a client note, a brief answer, a decision, a screen marked Build now at sign-off, a
fixed rule of the app, or the owner's own request with its date. Name each screen, field,
endpoint, tool and setting that the plan adds in one of these items.>
```

**F. The agent's guide.** In `src/forge/templates/skill.md`:

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
  "- `Not asked for: <what>`: name the item's source, or cut the addition and add one line for it
  to `plans/ideas.md`."
- `forge sync` rewrites `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`.

**G. The worker brief.** In `src/forge/templates/brief.md`, a new paragraph after the `Spotted:`
paragraph, which ends `fix it and name it in your handoff.`:

```
Build only what your Done-when items and the story's What changes for you name. When you think of
something useful that nobody asked for, build nothing for it: add one line
`- <YYYY-MM-DD>: <the idea in one plain sentence>` at the end of `plans/ideas.md` and name it in
your handoff. When a review reports `Not asked for: <what>`, remove the addition and add its idea
line, or, when a client note, brief answer, decision or Build now screen asks for it, add
`Source: <what>: <where it was asked>` to your commit body.
```

**H. The standards page.** In `src/forge/standards.md` (in every worker brief and review, and
synced to `.claude/skills/forge/standards.md` and `.codex/skills/forge/standards.md`):

- Replace principle 3 with:
  "3. **Only what was asked.** Every task, screen, field, endpoint, tool, setting, role and
  integration traces to a Done-when item and to a source: a client note, a brief answer, a
  decision, a screen marked Build now at sign-off, a fixed rule of the app, or the owner's own
  request. An idea that nobody asked for goes as one line to `plans/ideas.md`, and nothing is
  built for it. Anything else is cut, or goes under the spec's Out of scope."
- At the end of principle 4, add:
  "The starter's fixed rules are the base of each app. Build nothing beyond them just in case:
  modules, contracts, a schema per module and `services.toml` already leave room to grow."

The prototype's light review (`review-light.md`), the sign-off review and the design check keep
their own blocks and do not change: before sign-off the canvas is the scope.

### Done-when details

1. Plans name their sources (ASKED).
   - Texts E and F (the planning paragraph). The cold read's Raise line (text B) reports a plan
     item with no source.
   - Test: `tests/test_build_only_what_was_asked.py::test_1_plans_ask_for_a_source_on_each_item`,
     parametrised `new-client` and `adopted-v1.2.2` (the fixture copy and version move of
     `tests/test_fix_lean_review_prompts.py::test_1`, then `forge sync`). Each case: run
     `forge story new SHOP "Shoppers can save a basket"` as `tests/test_app_constitution.py` does,
     and read `plans/SHOP.md` in the story checkout: its `## What changes for you` has
     `End each item with its source in plain words`. The synced `.claude/skills/forge/SKILL.md`
     and `.codex/skills/forge/SKILL.md` have `Name each screen, field, endpoint, tool and setting
     that the plan adds in one of these items` and `plan only the screens marked Build now`.
2. Unsourced additions are "Not asked for" (ASKED).
   - Texts B, C and D.
   - Test: `tests/test_build_only_what_was_asked.py::test_2_unsourced_additions_are_not_asked_for`,
     parametrised `new-client` and `adopted-v1.2.2`, with the setup of
     `tests/test_fix_lean_review_prompts.py::test_1` (`env`, the `READER` reader, `forge read` for
     the cold-read prompt, `env.close` and `env.prompt()` for the fix review prompt). Both cases:
     each prompt's `## What counts` has text B's line, and each prompt has text C's phrases
     `Title an addition with no source`, `which sources you checked and found silent`,
     ``name its source, or remove it and add one line for it to `plans/ideas.md` ``,
     `never against the canvas` and `Score the note Gain 4, and Work 1 or 2`. New-client case,
     also: approve a SHOP doc whose first What-changes item ends
     `(Source: the owner's request, 27 Oct)` with `env.start_approved_task(doc)`, close it, and
     check that `env.prompt()` has `## What changes for you` and that item. The adopted case skips
     this step: the task review takes the same path in both repos.
   - `tests/test_fix_lean_review_prompts.py::test_1` keeps passing unchanged: it proves text B is
     the same in both prompts.
3. Extras go to the idea list; the starter is the base (ASKED).
   - Texts F (the idea-list line and the cold-read bullet), G and H.
   - Test: `tests/test_build_only_what_was_asked.py::test_3_useful_extras_go_to_the_idea_list`,
     parametrised `new init` and `previous release`, as
     `tests/test_deployment_requires_an_explicit_request.py::test_1` sets them up (`_fresh_client`;
     the `tests/fixtures/forge-v1.2.2` Forge's init, then the version move and `forge sync`). Each
     case: the worker brief from `forge work` (`install_claude`, `calls(log)[-1]["brief"]`) has
     `build nothing for it`, `plans/ideas.md`, `Source: <what>: <where it was asked>` and, from the
     standards page, `Only what was asked` and `Build nothing beyond them just in case`; the synced
     `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` have
     ``add one line `- <YYYY-MM-DD>: <the idea>` to `plans/ideas.md` ``; the synced
     `.claude/skills/forge/standards.md` and `.codex/skills/forge/standards.md` have
     `Only what was asked`.

### New and existing repos

- **New repos** (`forge init`, either starter, and adoption of a repo with history): the cold
  read, review and plan template text come from the installed Forge, and init writes the agent's
  guide and the standards copies, so every plan, read, review and worker brief has the rules from
  the first item. Tested by the `new-client` and `new init` cases.
- **Existing repos** (on upgrade to this release): the cold read, review, plan template, worker
  brief and the standards page in briefs and reviews come from the installed Forge, so they change
  with the upgrade. `forge sync` rewrites the agent's guide and the standards copies. No repo file
  needs a migration. A plan approved before the upgrade keeps its approval, because an approval
  binds the text of its own "What changes for you". A review of that plan's parts can find items
  with no source; the worker then names the source with a `Source:` line or cuts the addition, as
  for any plan. Tested by the `adopted-v1.2.2` and `previous release` cases.

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
| ASKED | Build only what was asked | The source on each plan item, the "Not asked for" rule in the cold read and the review, the approved items in the task review, the idea-list rule and the starter base in the brief, the guide and the standards page, on new and existing repos | 1, 2, 3 | `src/forge/templates/story.md`, `src/forge/templates/cold-read.md`, `src/forge/templates/review.md`, `src/forge/review.py` (one value in `instructions`), `src/forge/templates/brief.md`, `src/forge/templates/skill.md`, `src/forge/standards.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md`, `.claude/skills/forge/standards.md` and `.codex/skills/forge/standards.md` (rewritten by `forge sync`), `tests/test_build_only_what_was_asked.py` (new) | `tests/test_build_only_what_was_asked.py` (`test_1`, `test_2`, `test_3`); `tests/test_fix_lean_review_prompts.py::test_1` unchanged | | no | |

One part: the change is text in seven files, one line of code and one test file, well under 400
lines. Two parts would share `skill.md`, because this repo's review rules need the guide to change
in the same change as the cold read and the brief.

New moving parts: none

## Notes

- Owner decisions (27 Oct 2026, settled): build only what is asked, in every client repo and in
  Forge itself; every screen, field, endpoint, tool or setting that a plan adds names its source
  (a client note, a brief answer, a decision record, a screen marked Build now at sign-off; in
  Forge's own repo, the owner's request or a decision); the cold read and the review report an
  addition with no source as "Not asked for", and it blocks; the canvas may show the whole
  product, and code is checked against the signed Build now scope; a useful extra becomes one
  line in the existing idea list and nothing is built for it; the starter's fixed defaults stay
  the base, and nothing beyond them is built just in case; new repos get it at init, existing
  repos with `forge sync`; one or two parts, one test per rule, a new-repo case and one
  earlier-adopted case each.
- Owner addition (27 Oct 2026): FDEs and clients must not feel blocked for no reason. Each "Not
  asked for" note says what was added, why Forge sees no source (which sources it checked), and
  the two ways forward: name the source, or move it to the idea list.
- Planner choices the owner did not make: (1) the source goes at the end of each "What changes
  for you" item, not in a Tasks-table column; (2) the source list also counts the app's fixed
  rules and the human's own dated request in every repo, so a feature's built-in CSV export or
  history is not "Not asked for", and one rule serves client repos and Forge's own; (3) the note
  maps to the bar as Gain 4 with Work 1 or 2, so no score or close code changes; (4) in a review,
  a `Source:` commit line that names a real source clears the note with no new plan approval;
  (5) workers and planners write the idea line in their own branch, with no `forge start` call;
  (6) until sign-off marks Build now, every signed screen counts as Build now; (7) the prototype's
  light review and the sign-off review do not change.
- Depends on nothing: the sign-off story adds the Build now mark. This story only reads it, and
  the rule for repos without the mark (text C) covers the time before it lands.
- `src/forge/review.py` is 1,213 lines today, over the 1,200-line principle; this part adds one
  line. Spotted for a later trim, not widened here.
