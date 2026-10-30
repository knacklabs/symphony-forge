# Prototypes start as a signed canvas, a working build comes only when needed, and signed-off work ships without redoing it

6 parts · Risks: none one-way · New moving parts: none

## What changes for you

- Every prototype, and every story that adds a screen or changes a flow, starts with a canvas
  design. A story that makes only a small change to existing screens says so in its plan and
  needs no canvas. Backend-only stories skip this.
- Each app gets its own design. The agent makes it from the app's brief: what the app is for,
  who uses it, what it keeps track of with the fields of each thing, and the options of each
  choice list. No two apps share a look. The agent runs the design skill's init, which writes
  PRODUCT.md, and writes the app's look in DESIGN.md. Then it designs the screens in a Claude
  design artifact with a shadcn design system, as was done for the Forge board, so every element
  is a named shadcn component. On a Codex-only host, the screens are HTML artboards in the repo.
- The approved screens, their images and a screen list are copied into the repo. The screen
  list gives each screen's shadcn components and its fields. The plan names the design folder,
  so your one plan approval covers the design too.
- Before the client signs off, the agent runs impeccable's critique and polish and the
  emil-design-eng checklist, and records each result in the design folder. Then Forge runs a
  completeness check on Opus. It compares the screens with the brief and a checklist. A missing
  screen, field or choice-list option sends the design back, and sign-off waits.
- A client can sign off on the finished canvas alone. Production stories then start from the
  signed canvas.
- A working prototype is built only when the FDE asks for one, because the canvas cannot prove
  something such as real data or speed, and you accept that request as a recorded decision.
  Until then, Forge refuses to merge app code into an unsigned prototype.
- A working prototype's rounds prove only what the demo needs: the demo's steps work, and
  nothing leaks or loses data. Its light review checks only demo breakage, security and data
  loss, with its own model setting. The full proof is due at sign-off.
- Workers and reviewers on both Codex and Claude get the design, its screen list and the parts
  of the skills they need. The build applies the app's own design to the starter app: its theme,
  type, colours and screens, each screen with the components and fields on the screen list. A
  review holds a screen that misses one.
- Each fix goes to the right kind of worker for what it changes: screens, backend or a
  mechanical change. A repeat round keeps the same kind on both tools.
- Sign-off of a working prototype reviews the whole product once. Each sign-off runs the
  completeness check once. Forge uses both results again while nothing they checked changes.
- After sign-off, each new story carries what the canvas and any prototype already proved. Its
  plan and cold read cover only what is new or risky for production.
- Design: a story that adds a screen or changes a flow ends this section with its line
  `Design: docs/design/<KEY>/ (<content id>)`, so approving the plan approves that exact design.
  A story with only small changes to existing screens ends it with `Design: none (<why>)`, so
  you approve that choice too.

## Why

The owner wants prototypes to move fast before sign-off and features to ship fast after it. An
audit of Forge on 15 October 2026 found that prototypes still carry most of the production
contract (full proof lists, a "light" review that runs the full review and only blocks less), that
sign-off runs its whole-product review twice and keeps neither, that new stories after sign-off
re-plan and re-check work the prototype already proved, that every prototype fix is routed to the
design worker even when it changes only backend code, and that reviewers never receive the design
references. On 16 October 2026 the owner set the order: a prototype is a canvas made with the
design skills first, the client can sign off on that canvas, and a working prototype is built only
when it is needed.

From 21 to 23 October 2026 the owner set how each app's design is made. Every app gets its own
design from its own interview answers in the brief; the starter app has no look of its own. The
canvas is a Claude design artifact with a shadcn design system, and its screen list lets the
build map each screen one to one. A design can miss a field, a choice-list option or a whole
screen, and the client then signs off on an incomplete app. So sign-off waits for the design
skills' results and for a completeness check on Opus. A canvas is needed only for work that adds a
screen or changes a flow.

## Done when

1. **Every prototype, and every story that adds a screen or changes a flow, starts with the design skill's init and an approved canvas whose screens and images live in the repo, and a story names that design in the part the owner approves, so one approval covers both; a story with only small changes to existing screens names that choice in the same part instead.**
2. **Client sign-off, on the canvas alone or on a working build, waits until the design folder lists each screen's shadcn components and fields, records the results of the design skills' init, critique, polish and checklist, and passes a completeness check on Opus that finds no screen, field or choice-list option missing against the app's brief; a sign-off on the canvas alone needs no working build, and production stories start from the signed canvas.**
3. **A working prototype starts only after the owner accepts the FDE's recorded request, and its rounds prove the demo's steps and its security and data boundaries under a light review with its own model setting.**
4. **Workers and reviewers on both tools receive the named design, its screen list and the skill guidance their work needs, the build applies the app's own theme, type, colours and screens to the starter app, a review holds a built screen that lacks a listed component or field, and each fix goes to the worker kind named when it starts (screens, backend or mechanical), keeping that kind on every round.**
5. **Sign-off of a working prototype reviews the whole product once, every sign-off runs the completeness check once, and Forge reuses each result while what it checked stays unchanged.**
6. **Every story planned after sign-off carries what the canvas and any prototype proved, and its plan and cold read cover only what is new or risky for production.**

## New and existing repos

- **New repos** (init or adoption): canvas-first for work that adds a screen or changes a flow,
  the `Design: none` choice, the screen list, the design skills' records and the completeness
  check before sign-off, the app's own design applied to the starter, canvas sign-off, the
  working-build decision, the prototype contract, the light review setting, sign-off reuse and
  the hand-off from their first prototype or story. Tested on a repo made by `forge init`, and by
  `forge init --starter` for the starter case.
- **Existing repos** (on upgrade to this release): the same rules from their next prototype
  round, story or sign-off. An unsigned prototype that already has merged app code counts as
  having an accepted working-build decision, so its work goes on; its current proof stays until
  its next round. An unsigned prototype whose design folder has no screen list or design-skill
  records is refused at its next sign-off, and the refusal names each missing file. A repo that
  already has its sign-off needs no new records and no check; its next story follows the new
  rules. A sign-off already reviewed is reviewed once more, then reused. An app without the
  starter gets its design applied to its own theme file. Existing model settings stay; the new
  light-review setting starts at Forge's default. A story approved before this release keeps
  working without a `Design:` line. Tested on the adopted earlier-release fixture moved to this
  release.

## Risks

Risks: none one-way. Every part reverts with its pull request. The strict sign-off review still
runs before any sign-off of a working prototype, so the lighter prototype rounds never reach
production unchecked. A canvas sign-off ships no code: production stories build and review it.

Trade-off: each design that goes to sign-off costs one completeness check on Opus. On a machine
without Claude, the check runs on Codex with gpt-6.1-sol at high, and Forge says so.

## For the builders

### Done-when details

1. Design-first, in this order. Story: run impeccable's `init` (PRODUCT.md) when the repo has
   none; design the screens in a Claude artifact (Design type); copy the artboards into
   `docs/design/<KEY>/` on the story branch with a renderer (as `docs/board-design/support.js`
   does) and a 1440 by 900 image per screen; write `Design: docs/design/<KEY>/ (<tree id>)` as the
   last line of the plan's `## What changes for you` section, which the approval hash covers,
   where `<tree id>` is the git tree id of that folder; then cold read, then the owner's approval.
   Because the line is in the approved text, approval covers that exact design; changing the
   folder changes the tree id and voids the approval like any other edit. `forge read` and
   approval refuse a plan with a user-facing part (User-facing = yes or true, read as
   `src/forge/repo.py` reads it) whose `Design:` line is missing, names a folder with no images,
   or whose tree id does not match the folder. Close refuses a task whose branch changes the
   approved design folder's tree id, with the next step. Backend-only plans pass. A story
   approved before this release keeps working with no `Design:` line. Prototype: the coordinator
   runs init when PRODUCT.md is missing and makes the canvas folder `docs/design/prototype/` in a
   fix; the owner (or FDE) approves it with `forge decision new prototype-design` and
   `forge decision accept prototype-design --by <name>`. On a Codex-only host with no artifact
   tool, the guide says to make the artboards as HTML files in the folder. App code: DESIGN pins
   one rule that BUILD and SIGNOFF use. A changed file is app code unless it is under `docs/`,
   `plans/`, `.factory/`, `.forge/`, `.github/`, `.claude/` or `.codex/`, or is a file `forge init`
   or `forge sync` writes (such as AGENTS.md, forge.toml and the Dockerfile), or is a Markdown
   file anywhere (README.md, PRODUCT.md and DESIGN.md included). Canvas artboards live under `docs/design/`, so they are never app code. A prototype
   has a working build when its prototype-build decision is accepted or the default branch has a
   merged commit that changes app code. Tests: a story with a
   user-facing part and no design is refused with the next step; `User-facing | true` is refused
   the same way; a changed folder voids approval; a task branch that changes the folder is refused
   at close; a backend-only story passes; a story approved on the earlier release still starts a
   task. (DESIGN merged all of the above.)
   Small changes (HANDOFF): a plan with a user-facing part may end `## What changes for you` with
   `Design: none (<why>)` in place of a folder, when its parts add no screen and change no flow.
   `design.check` accepts that line, which the approval covers like any other. The task's brief
   carries the signed prototype folder's `SCREENS.md` as context only (see item 4). The cold read prompt tells the
   reader to report as P1 a `Design: none` story whose parts add a screen or change a flow. The
   guide says to write the canvas from the brief's `## Summary`, `## Users` and
   `## Things it keeps track of`, with impeccable and emil-design-eng, so each app has its own
   look. Tests: a story with a user-facing part and `Design: none (only a label changes)` passes
   read and approval and starts a task; `Design: none` with no reason is refused with the next
   step; the cold read prompt names the P1 rule.
2. Canvas sign-off. The sign-off decision (`client-signoff`) gains a `## Signed design` section
   naming `docs/design/prototype/ (<tree id>)`. Accepting sign-off with no working prototype is
   allowed when that tree id matches the folder and the sign-off's own branch changes no app code
   (item 1's rule). A tree id that does not match is refused with the next step to approve the
   changed canvas again; app code on the branch is refused with the next step `forge decision new
   prototype-build`. The repo then counts as signed, as with any sign-off. The first story after a canvas sign-off names the signed folder in its `Design:`
   line, or a newer design approved with its plan.
   Design records. Before any review or check, `forge decision accept client-signoff` (canvas or
   working build) refuses, naming each gap and the next step, unless all of these are in the
   signed tree or, for the root files, on the sign-off branch:
   - `docs/product/BRIEF.md` with a `## Things it keeps track of` section that is not empty once
     its comments are removed. Main's shipped brief has this section, and the setup interview
     fills it. The refusal names the section.
   - `PRODUCT.md` and `DESIGN.md` at the repo root, each not empty (impeccable's init writes
     PRODUCT.md; impeccable writes DESIGN.md with the app's theme tokens, type and colours).
   - `docs/design/prototype/SCREENS.md`: one `## <screen>` section for each screen image, each
     with `Image: <file in the folder>`, `Components: <shadcn component names>` and a `Fields:`
     list, one `- <field>: <type>, required|optional` line each, with `, options: <a> | <b>` for a
     choice list. A field-less screen writes `Fields: none`. An image with no section, or a
     section with no `Components:` line, is a gap.
   - `docs/design/prototype/CHECKS.md` with `## Critique`, `## Polish` and `## Emil checklist`,
     each with its notes and a `Result: passed` line.
   Completeness check. Then accept runs the check through the same engine as the strict sign-off
   review, on Claude with `claude-opus-5-5` at high effort. Forge pins that model as the check's
   own default, as it pins the grill default, and the check does not read `[models.design]`. It
   uses the shipped prompt `src/forge/templates/design-check.md`. The prompt holds the checklist
   below and gives the reviewer `SCREENS.md`, the screen images and the brief's `## Summary`,
   `## Users`, `## Things it keeps track of` and `## Key flows`. The reviewer reports each key
   flow that no screen in `SCREENS.md` carries. Any P0 or P1 finding (a missing screen, field,
   choice-list option or flow, or any other checklist gap) refuses sign-off, lists each finding, and names the next
   step: change the canvas, approve it again with `forge decision accept prototype-design`, then
   accept sign-off again. When the `claude` command is missing, the check runs on Codex with
   `gpt-6.1-sol` at high effort and Forge prints that it fell back. No other model runs it. A passed check writes
   `design_checked: <tree id>` and `brief_checked: <hash of those four brief sections>` in the
   sign-off decision's front matter. The check runs on a canvas-only sign-off too; it is not a code
   review. A repo whose sign-off was accepted before this release is never asked for these.
   Tests: sign-off accepts a matching canvas with no app code; sign-off is refused when its own
   branch changes app code; a changed folder after sign-off is refused as the signed design; the
   first story after sign-off starts from the signed folder; a canvas with no `SCREENS.md`, or an
   image with no section, is refused and the refusal names it; a brief whose
   `## Things it keeps track of` is missing or holds only its comment is refused and the refusal
   names the section; `CHECKS.md` with no passed Emil
   line is refused; a missing `DESIGN.md` is refused; a fake reviewer that reports a missing
   field refuses sign-off and shows the finding; a fake reviewer that reports a key flow with no
   screen refuses sign-off; a clean fake reviewer lets sign-off go on, and the run used
   `claude-opus-5-5` at high even when `[models.design.claude]` names another model; with no
   `claude` command the run used `gpt-6.1-sol` at high and printed the fall-back; an adopted earlier-release repo already signed off starts its next
   story with no check.
3. Working build. `forge decision new prototype-build` records the FDE's reason the canvas cannot
   prove something; `forge decision accept prototype-build --by <owner>` approves it. While the
   prototype is unsigned and has no working build (item 1's rule), close refuses any fix or task
   whose branch changes app code, with the next step `forge decision new prototype-build`; a
   branch that changes only canvas, docs or plan files closes as usual, whatever its kind. Fix
   start does not refuse, because it cannot know which files a fix will change. An unsigned repo
   that already has merged app code counts as having a working build. Once accepted, an unsigned prototype fix's brief asks
   for tests of the demo's steps and of security and data boundaries only, and close's review
   checks those, not per-function proof. Those rounds use a narrow review prompt that checks demo
   breakage, security and data loss only; `[models.light_review]` sets its model and effort
   (default: the review model at medium). Sign-off's full proof: the sign-off decision gains a
   `## Proof` section listing each demo workflow step with the test that proves it; the strict
   sign-off review of a working prototype requires every step to name a passing test. Tests: in
   an unsigned prototype, close refuses a fix that changes app code before the decision and
   closes it after; a canvas-only ui fix closes with no decision; an upgraded prototype with
   merged app code is not refused; a
   prototype round passes close with demo-step tests and no per-function proof; the light prompt
   names only the three checks; the setting changes the model used; a security finding still
   blocks; sign-off refuses a product whose `## Proof` leaves a demo step without a test.
4. Context and routing. The worker brief and the close review input both carry the design folder
   (paths and images), its `SCREENS.md`, the root `DESIGN.md` and `PRODUCT.md`, and short excerpts
   of the skills the part needs (impeccable, emil-design-eng and the frontend role for
   user-facing work, test-audit for test changes), the same on Codex and Claude. The folder is the
   story's `Design:` folder; for a prototype fix, `docs/design/prototype/`; for a `Design: none`
   story, the signed `docs/design/prototype/` when it exists, as context only. For a
   user-facing item, the brief tells the worker to apply DESIGN.md's theme tokens, type and
   colours to the app's theme file (in a starter app, the shadcn variables in
   `apps/web/src/index.css`; in an app without the starter, its own theme file) and to build each
   screen it touches with the components and fields that its own approved folder's `SCREENS.md`
   lists for it. The review
   prompt reports as P1 a built screen that lacks a component or field its `SCREENS.md` section
   lists, only for screens that the item's own approved design folder lists: the story's
   `Design:` folder, or `docs/design/prototype/` for an unsigned prototype's fix. It reports no
   such P1 for a `Design: none` story. It also reports as P1 a starter app that still has the
   starter's neutral tokens when DESIGN.md sets others. A fix's
   kind is named at start: `forge fix start ... --kind ui|backend|mechanical` (stories use the
   task row's User-facing column); ui goes to the design worker, backend to the backend worker,
   mechanical to the lite worker. `--kind` is required for prototype fixes, which no longer force
   the design worker. Every round of a fix uses the kind its record holds, on both tools. Close
   warns (does not block) when the changed files disagree with the kind. Tests: a backend
   prototype fix routes to the backend worker; a ui fix routes to design; round 2 keeps the kind
   on Codex and on Claude (ROUTING merged these); the brief and the review input name the design
   folder and carry `SCREENS.md` and DESIGN.md on Codex and on Claude; a starter app's ui brief
   names `apps/web/src/index.css`, and an adopted app without the starter gets the theme-file line
   without that path; the review prompt names the P1 rule; a `Design: none` story's brief
   carries the signed `SCREENS.md` as context only, and its review input has no P1 rule for
   listed components or fields.
5. Sign-off reuse. For a working prototype, the strict sign-off review run before the customer
   reply saves its result with the product commit, a hash of the answers page, a hash of the
   sign-off decision's `## Signed design`, `## Proof` and `## Decisions` sections, and the review
   rules. Accepting
   sign-off after the reply reuses that result while all four are unchanged and reviews again
   otherwise. A canvas-only sign-off runs no code review. The completeness check is reused while
   `design_checked` matches the signed tree and `brief_checked` matches the brief, and runs again
   otherwise. Tests: review before the reply then
   acceptance on an unchanged product runs one review and one check; a changed answer page, a
   changed proof mapping or a changed signed design runs a second review; a changed brief field
   runs a second check; a canvas-only sign-off runs the check once and no review.
6. Hand-off. The sign-off decision's `## Signed design`, `## Proof` (demo outcomes and their
   tests, when a working prototype exists) and `## Decisions` sections are the evidence record;
   SIGNOFF pins the section names. Every story created after sign-off starts with a
   `## Proven by the prototype` section copied from that record. The cold read treats the section
   as settled and reads only the rest; the plan's parts list only new or production-risk work.
   Tests: the first and the second story after sign-off both start with the section filled, for a
   canvas-only sign-off and for a working-prototype sign-off; the cold read raises no note about a
   proven outcome.

### Completeness checklist

SIGNOFF copies this list into `src/forge/templates/design-check.md` as the check's checklist, in
plain words. It is section 3 of the owner's research checklist of 21 October 2026. The check also
confirms that every thing, field and choice-list option in the brief's
`## Things it keeps track of` appears on a screen in `SCREENS.md`, and that every flow in the
brief's `## Key flows` has its screens.

Entities and fields
- Every entity from the interview appears in: list, detail, create form, edit form.
- Every field of every entity shows in detail and in the form, or the prototype states why not (for example computed, hidden, system field).
- Each field has: label, type, required or optional, sample value, validation rule, help text where unclear.
- List columns chosen on purpose; remaining fields reachable via detail or column visibility.
- Read-only and system fields (id, created by, created at, updated at) marked.
- Relations: link from list/detail to related entity; a way to pick a related record in forms.
- Extended/detail screens exist for every row-level object (tabs for related data, activity, files).

Dropdowns and choice lists
- Every Select, Combobox, radio and filter shows its full option list in the prototype.
- Each list states: fixed or user-editable, default value, empty-list behaviour, search needed (more than ~10 options).
- Status fields list allowed transitions (who can move from X to Y).

States per screen
- Empty (first use, and no results after a filter), loading (skeleton), error (with retry), success (toast), partial/slow.
- Permission denied for each role; hidden or disabled controls explained.
- Offline or session expired state.
- Long text, long names, and large numbers do not break layout.
- Many rows: pagination or scroll shown; zero, one, many examples.

Navigation
- Every screen reachable from the sidebar, a link, the command palette or a row click; no orphan screens.
- Every screen has a way back (breadcrumb, back, cancel).
- After create, edit, delete the user lands somewhere stated.
- Sidebar collapsed, expanded and mobile sheet states shown.
- Deep links and 404 for unknown ids shown.

Forms and validation
- Each required field has an error message in plain words; examples shown for at least one invalid submit per form.
- Server-side error (duplicate, conflict) message shown.
- Cancel and unsaved-changes behaviour defined.
- Multi-step forms show progress and allow going back.

Destructive and risky actions
- Delete, archive, revoke, bulk actions use an AlertDialog naming the item and the effect.
- Undo or restore path stated (soft delete, trash view).
- Bulk select shows count and a clear way to cancel.
- Only permitted roles see the action.

Cross-cutting
- Light and dark shown for at least the shell and one form.
- Phone, tablet and desktop widths shown for the shell, a table and a form.
- Keyboard path: tab order, Cmd+K, Cmd+B, Esc closes dialogs.
- Only shadcn/ui components used; any custom piece listed with its reason.
- Notification, settings, profile and sign-in screens present.
- Copy reviewed: no jargon, buttons use verbs ("Save client", not "Submit").
- Sign-off record: owner confirms entities list, dropdown lists and screen list in plain words.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| DESIGN | Design first | the `Design:` line with tree id in read, approval and close checks, the prototype-design decision rule ROUTING's gate calls, the app-code rule BUILD and SIGNOFF use, the folder layout and renderer | 1 | src/forge/design.py, src/forge/story.py, src/forge/templates/story.md, src/forge/templates/design/support.js | tests/test_design_first.py | ROUTING | no | |
| CONTEXT | Design and skills reach workers and reviewers | design folder, screen list, DESIGN.md and skill excerpts in the brief and the review input on both tools; the brief's rule to apply the app's design to the starter; the review's P1 rule for a screen that misses a listed component or field | 4 | src/forge/templates/brief.md, src/forge/templates/review.md, src/forge/review.py, src/forge/worker.py | tests/test_design_context.py | DESIGN | no | |
| ROUTING | Fixes go to the right worker | owns `fix start`: `--kind`, the unsigned-prototype ui gate hook (pinned with a stub DESIGN fills), prototypes no longer forced to design, the same kind on every round, a warning when files disagree | 4 | src/forge/worker.py, src/forge/roles.py, src/forge/task.py, src/forge/cli.py | tests/test_fix_routing.py | | no | |
| BUILD | Working prototype on request | the prototype-build decision gate at close, the demo-step and boundary test contract, the light review prompt and `[models.light_review]` | 3 | src/forge/design.py, src/forge/close.py, src/forge/score.py, src/forge/templates/review-light.md, src/forge/repo.py | tests/test_prototype_build.py | CONTEXT | no | |
| SIGNOFF | Sign-off on a complete canvas, once | canvas sign-off through `## Signed design`; the design records it requires; the completeness check on Opus with its shipped checklist; the saved sign-off review and check and their reuse; the decision's section names pinned | 2, 5 | src/forge/records.py, src/forge/review.py, src/forge/templates/design-check.md | tests/test_signoff_design.py, tests/test_signoff_reuse.py | CONTEXT | no | |
| HANDOFF | After sign-off | the proven section, cold read treats it as settled, `Design: none` for small screen changes and its cold-read rule, and the guide's prototype, story and design steps (per-app design from the brief, screen list, design records, completeness check) on both synced copies | 6, 1, 2 | src/forge/story.py, src/forge/design.py, src/forge/templates/story.md, src/forge/templates/cold-read.md, src/forge/templates/skill.md, .claude/skills/forge/SKILL.md, .codex/skills/forge/SKILL.md, docs/guide.md | tests/test_signoff_handoff.py, tests/test_design_first.py | DESIGN, BUILD, SIGNOFF | no | |

New moving parts: none

## Notes

- Shared files have one owner each: story.py is DESIGN's, then HANDOFF's after DESIGN merges;
  design.py is DESIGN's, then BUILD's after DESIGN merges, then HANDOFF's after BUILD merges;
  review.py and review.md are CONTEXT's, then SIGNOFF's after CONTEXT merges; the guide and its
  synced copies are HANDOFF's only.
- Line budget: story.py has 1,195 lines and review.py 1,126, against the 1,200-line ceiling.
  HANDOFF puts its new logic in design.py and adds only calls to story.py; SIGNOFF puts the design
  records, the check and its reuse in records.py and the shipped prompt, and adds only the engine
  call to review.py. If SIGNOFF goes over the 400-line part limit, split the reuse into its own
  part after SIGNOFF.
- No part changes Forge's own screens (the board), so no part is user-facing for Forge and this
  story has no design folder.
- Re-planned on 16 October 2026 for canvas-first: PROTOTEST and LIGHTREVIEW became BUILD, which
  runs only for a requested working prototype. ROUTING merged before the re-plan and is unchanged.
- Re-planned on 23 October 2026 for the owner's per-app design flow (21 to 23 October): design
  first only for work that adds a screen or changes a flow, a design per app from its brief, a
  shadcn screen list, the design skills' records and an Opus completeness check before sign-off,
  and the build applies the app's design to the starter. DESIGN and ROUTING merged before this
  re-plan and are unchanged; CONTEXT, SIGNOFF and HANDOFF gained the new work; BUILD is unchanged.
- Deferred by the owner (15 October): preparing the next change while CI runs, and reviewing only
  changed proof entries.
