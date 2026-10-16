# Prototypes start as a signed canvas, a working build comes only when needed, and signed-off work ships without redoing it

6 parts · Risks: none one-way · New moving parts: none

## What changes for you

- Every prototype, and every story with user-facing parts, starts with a canvas design. The
  agent sets up the product record with the design skill's init, then designs the screens in a
  Claude artifact, as was done for the Forge board. On a Codex-only host, the screens are HTML
  artboards in the repo. The approved screens and their images are copied into the repo, and
  the plan names them, so your one plan approval covers the design too. Backend-only stories
  skip this.
- A client can sign off on the finished canvas alone. Production stories then start from the
  signed canvas.
- A working prototype is built only when the FDE asks for one, because the canvas cannot prove
  something such as real data or speed, and you accept that request as a recorded decision.
  Until then, Forge refuses to start app code in an unsigned prototype.
- A working prototype's rounds prove only what the demo needs: the demo's steps work, and
  nothing leaks or loses data. Its light review checks only demo breakage, security and data
  loss, with its own model setting. The full proof is due at sign-off.
- Workers and reviewers on both Codex and Claude get the design and the parts of the skills
  they need, so their work matches the design without extra rounds.
- Each fix goes to the right kind of worker for what it changes: screens, backend or a
  mechanical change. A repeat round keeps the same kind on both tools.
- Sign-off of a working prototype reviews the whole product once and reuses that review while
  nothing changes.
- After sign-off, each new story carries what the canvas and any prototype already proved. Its
  plan and cold read cover only what is new or risky for production.
- Design: a user-facing story's plan ends this section with its line `Design: docs/design/<KEY>/
  (<content id>)`, so approving the plan approves that exact design.

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

## Done when

1. **Every prototype and every story with user-facing parts starts with the design skill's init and an approved canvas whose screens and images live in the repo, and a story names that design in the part the owner approves, so one approval covers both.**
2. **A client can sign off on the finished canvas with no working build, and production stories start from the signed canvas.**
3. **A working prototype starts only after the owner accepts the FDE's recorded request, and its rounds prove the demo's steps and its security and data boundaries under a light review with its own model setting.**
4. **Workers and reviewers on both tools receive the named design and the skill guidance their work needs, and each fix goes to the worker kind named when it starts (screens, backend or mechanical), keeping that kind on every round.**
5. **Sign-off of a working prototype reviews the whole product once and reuses that review while the product and the answers stay unchanged.**
6. **Every story planned after sign-off carries what the canvas and any prototype proved, and its plan and cold read cover only what is new or risky for production.**

## New and existing repos

- **New repos** (init or adoption): canvas-first, canvas sign-off, the working-build decision,
  the prototype contract, the light review setting, sign-off reuse and the hand-off from their
  first prototype or story. Tested on a repo made by `forge init`.
- **Existing repos** (on upgrade to this release): the same rules from their next prototype
  round, story or sign-off. An unsigned prototype that already has merged app code counts as
  having an accepted working-build decision, so its work goes on; its current proof stays until
  its next round. A sign-off already reviewed is reviewed once more, then reused. Existing model
  settings stay; the new light-review setting starts at Forge's default. A story approved before
  this release keeps working without a `Design:` line. Tested on the adopted earlier-release
  fixture moved to this release.

## Risks

Risks: none one-way. Every part reverts with its pull request. The strict sign-off review still
runs before any sign-off of a working prototype, so the lighter prototype rounds never reach
production unchecked. A canvas sign-off ships no code: production stories build and review it.

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
   tool, the guide says to make the artboards as HTML files in the folder. Tests: a story with a
   user-facing part and no design is refused with the next step; `User-facing | true` is refused
   the same way; a changed folder voids approval; a task branch that changes the folder is refused
   at close; a backend-only story passes; a story approved on the earlier release still starts a
   task.
2. Canvas sign-off. The sign-off decision (`client-signoff`) gains a `## Signed design` section
   naming `docs/design/prototype/ (<tree id>)`. Accepting sign-off with no working prototype is
   allowed when that tree id matches the folder; the repo then counts as signed, as with any
   sign-off. The first story after a canvas sign-off names the signed folder in its `Design:`
   line, or a newer design approved with its plan. Tests: sign-off accepts a matching canvas with
   no app code; a changed folder after sign-off is refused as the signed design; the first story
   after sign-off starts from the signed folder.
3. Working build. `forge decision new prototype-build` records the FDE's reason the canvas cannot
   prove something; `forge decision accept prototype-build --by <owner>` approves it. While the
   prototype is unsigned and that decision is not accepted, `forge fix start` refuses every fix of
   kind ui or backend, with the next step; mechanical fixes and fixes that change only `docs/` or
   `plans/` are not refused. The rule uses ROUTING's ui gate hook. An unsigned repo that already
   has merged app code counts as accepted. Once accepted, an unsigned prototype fix's brief asks
   for tests of the demo's steps and of security and data boundaries only, and close's review
   checks those, not per-function proof. Those rounds use a narrow review prompt that checks demo
   breakage, security and data loss only; `[models.light_review]` sets its model and effort
   (default: the review model at medium). Sign-off's full proof: the sign-off decision gains a
   `## Proof` section listing each demo workflow step with the test that proves it; the strict
   sign-off review of a working prototype requires every step to name a passing test. Tests: an
   unsigned prototype refuses a backend fix before the decision and starts it after; a
   mechanical fix is not refused; an upgraded prototype with merged app code is not refused; a
   prototype round passes close with demo-step tests and no per-function proof; the light prompt
   names only the three checks; the setting changes the model used; a security finding still
   blocks; sign-off refuses a product whose `## Proof` leaves a demo step without a test.
4. Context and routing. The worker brief and the close review input both carry the design folder
   (paths and images) and short excerpts of the skills the part needs (impeccable and the frontend
   role for user-facing work, test-audit for test changes), the same on Codex and Claude. A fix's
   kind is named at start: `forge fix start ... --kind ui|backend|mechanical` (stories use the
   task row's User-facing column); ui goes to the design worker, backend to the backend worker,
   mechanical to the lite worker. `--kind` is required for prototype fixes, which no longer force
   the design worker. Every round of a fix uses the kind its record holds, on both tools. Close
   warns (does not block) when the changed files disagree with the kind. Tests: a backend
   prototype fix routes to the backend worker; a ui fix routes to design; round 2 keeps the kind
   on Codex and on Claude; the brief and the review input name the design folder.
5. Sign-off reuse. For a working prototype, the strict sign-off review run before the customer
   reply saves its result with the product commit, a hash of the answers page, a hash of the
   sign-off decision's `## Proof` and `## Decisions` sections, and the review rules. Accepting
   sign-off after the reply reuses that result while all four are unchanged and reviews again
   otherwise. A canvas-only sign-off runs no code review. Tests: review before the reply then
   acceptance on an unchanged product runs one review; a changed answer page or a changed proof
   mapping runs a second; a canvas-only sign-off runs none.
6. Hand-off. The sign-off decision's `## Signed design`, `## Proof` (demo outcomes and their
   tests, when a working prototype exists) and `## Decisions` sections are the evidence record;
   SIGNOFF pins the section names. Every story created after sign-off starts with a
   `## Proven by the prototype` section copied from that record. The cold read treats the section
   as settled and reads only the rest; the plan's parts list only new or production-risk work.
   Tests: the first and the second story after sign-off both start with the section filled, for a
   canvas-only sign-off and for a working-prototype sign-off; the cold read raises no note about a
   proven outcome.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| DESIGN | Design first | the `Design:` line with tree id in read, approval and close checks, the prototype-design decision rule ROUTING's gate calls, the folder layout and renderer | 1 | src/forge/design.py, src/forge/story.py, src/forge/templates/story.md, src/forge/templates/design/support.js | tests/test_design_first.py | ROUTING | no | |
| CONTEXT | Design and skills reach workers and reviewers | design folder and skill excerpts in the brief and the review input on both tools | 4 | src/forge/templates/brief.md, src/forge/templates/review.md, src/forge/review.py | tests/test_design_context.py | DESIGN | no | |
| ROUTING | Fixes go to the right worker | owns `fix start`: `--kind`, the unsigned-prototype ui gate hook (pinned with a stub DESIGN fills), prototypes no longer forced to design, the same kind on every round, a warning when files disagree | 4 | src/forge/worker.py, src/forge/roles.py, src/forge/task.py, src/forge/cli.py | tests/test_fix_routing.py | | no | |
| BUILD | Working prototype on request | the prototype-build decision gate, the demo-step and boundary test contract, the light review prompt and `[models.light_review]` | 3 | src/forge/design.py, src/forge/close.py, src/forge/score.py, src/forge/templates/review-light.md, src/forge/repo.py | tests/test_prototype_build.py | CONTEXT | no | |
| SIGNOFF | Sign-off on the canvas, once | canvas sign-off through `## Signed design`, the saved sign-off review and reuse, the decision's section names pinned | 2, 5 | src/forge/records.py, src/forge/review.py | tests/test_signoff_reuse.py | CONTEXT | no | |
| HANDOFF | After sign-off | the proven section, cold read treats it as settled, and the guide's prototype, story and design steps on both synced copies | 6, 1, 2 | src/forge/story.py, src/forge/templates/cold-read.md, src/forge/templates/skill.md, .claude/skills/forge/SKILL.md, .codex/skills/forge/SKILL.md, docs/guide.md | tests/test_signoff_handoff.py | DESIGN, BUILD, SIGNOFF | no | |

New moving parts: none

## Notes

- Shared files have one owner each: story.py is DESIGN's, then HANDOFF's after DESIGN merges;
  design.py is DESIGN's, then BUILD's after DESIGN merges; the guide and its synced copies are
  HANDOFF's only.
- Re-planned on 16 October 2026 for canvas-first: PROTOTEST and LIGHTREVIEW became BUILD, which
  runs only for a requested working prototype. ROUTING merged before the re-plan and is unchanged.
- Deferred by the owner (15 October): preparing the next change while CI runs, and reviewing only
  changed proof entries.
