# Prototypes start from an approved design and reach sign-off faster, and signed-off work ships without redoing it

7 parts · Risks: none one-way · New moving parts: none

## What changes for you

- Every prototype, and every story with user-facing parts, starts with a design. The agent sets
  up the product record with the design skill's init, then designs the screens in a Claude
  artifact, as was done for the Forge board. The approved screens and their images are copied
  into the repo, and the plan names them, so your one plan approval covers the design too.
  Backend-only stories skip this.
- Workers and reviewers on both Codex and Claude get the design and the parts of the skills
  they need, so their work matches the design without extra rounds.
- Each fix goes to the right kind of worker for what it changes: screens, backend or a
  mechanical change. A repeat round keeps the same kind on both tools.
- A prototype round proves what the demo needs (the demo's steps work, and nothing leaks or
  loses data). The full proof is due at sign-off, not on every demo round.
- The prototype's light review looks only for what breaks the demo, security and data loss,
  with its own model setting, so demo rounds come back faster.
- Sign-off reviews the whole product once and reuses that review while nothing changes.
- After sign-off, each new story carries what the prototype already proved. Its plan and cold
  read cover only what is new or risky for production, not work the demo already showed.
- Design: a user-facing story's plan ends this section with its line `Design: docs/design/<KEY>/
  (<content id>)`, so approving the plan approves that exact design.

## Why

The owner wants prototypes to move fast before sign-off and features to ship fast after it. An
audit of Forge on 15 October 2026 found that prototypes still carry most of the production
contract (full proof lists, a "light" review that runs the full review and only blocks less), that
sign-off runs its whole-product review twice and keeps neither, that new stories after sign-off
re-plan and re-check work the prototype already proved, that every prototype fix is routed to the
design worker even when it changes only backend code, and that reviewers never receive the design
references. The owner also wants the design skill used fully, starting from its init, and the
design made first in a Claude artifact before anything user-facing is built.

## Done when

1. **Every prototype and every story with user-facing parts starts with the design skill's init and an approved design whose screens and images live in the repo; a story names that design in the part the owner approves, so one approval covers both, and a prototype's design is approved before its first user-facing build.**
2. **Workers and reviewers on both tools receive the named design and the skill guidance their work needs, and each fix goes to the worker kind named when it starts (screens, backend or mechanical), keeping that kind on every round.**
3. **A prototype round proves the demo's steps and its security and data boundaries, and the full proof is required at sign-off.**
4. **The prototype's light review checks only demo breakage, security and data loss, with a model setting of its own.**
5. **Sign-off reviews the whole product once and reuses that review while the product and the answers stay unchanged.**
6. **Every story planned after sign-off carries the prototype's proven outcomes and tests, and its plan and cold read cover only what is new or risky for production.**

## New and existing repos

- **New repos** (init or adoption): design-first, the prototype contract, the light review
  setting, sign-off reuse and the hand-off from their first prototype or story. Tested on a repo
  made by `forge init`.
- **Existing repos** (on upgrade to this release): the same rules from their next prototype
  round, story or sign-off. A prototype already under way keeps its current proof until its next
  round; a sign-off already reviewed is reviewed once more, then reused. Existing model settings
  stay; the new light-review setting starts at Forge's default. Tested on the adopted
  earlier-release fixture moved to this release.

## Risks

Risks: none one-way. Every part reverts with its pull request. The strict sign-off review still
runs before any sign-off, so the lighter prototype rounds never reach production unchecked.

## For the builders

### Done-when details

1. Design-first, in this order. Story: run impeccable's `init` (PRODUCT.md) when the repo has
   none; design the screens in a Claude artifact (Design type); copy the artboards into
   `docs/design/<KEY>/` on the story branch with a renderer (as `docs/board-design/support.js`
   does) and a 1440 by 900 image per screen; write `Design: docs/design/<KEY>/ (<tree id>)` as the
   last line of the plan's `## What changes for you` section, which the approval hash covers,
   where `<tree id>` is the git tree id of that folder; then cold read, then the owner's approval.
   Because the line is in the approved text, approval covers that exact design; changing the folder changes the tree id and voids the
   approval like any other edit. `forge read` and approval refuse a plan with a user-facing part
   (User-facing = yes) whose `Design:` line is missing, names a folder with no images, or whose tree
   id does not match the folder. Backend-only plans pass. Prototype: before its first ui fix,
   the coordinator makes the same design folder `docs/design/prototype/` in a fix, and the owner
   (or FDE) approves it with `forge decision new prototype-design` and `forge decision accept
   prototype-design --by <name>`; while the prototype is unsigned, every fix of kind `ui`
   (see item 2), with or without any flag, is refused until that decision is accepted, and its
   brief names the folder; backend and mechanical prototype fixes are not gated. On a Codex-only host with no artifact
   tool, the guide says to make the artboards as HTML files in the folder. Tests: a story with a
   user-facing part and no design is refused with the next step; a changed folder voids approval;
   a backend-only story passes; an unsigned prototype's ui fix before the design decision is refused, and a backend one is not.
2. Context and routing. The worker brief and the close review input both carry the design folder
   (paths and images) and short excerpts of the skills the part needs (impeccable and the frontend
   role for user-facing work, test-audit for test changes), the same on Codex and Claude. A fix's
   kind is named at start: `forge fix start ... --kind ui|backend|mechanical` (stories use the
   task row's User-facing column); ui goes to the design worker, backend to the backend worker,
   mechanical to the lite worker. `--kind` is required for prototype fixes, which no longer force
   the design worker. Every round of a fix uses the kind its record holds, on both tools. Close
   warns (does not block) when the changed files disagree with the kind. Tests: a backend
   prototype fix routes to the backend worker; a ui fix routes to design; round 2 keeps the kind
   on Codex and on Claude; the brief and the review input name the design folder.
3. Prototype test contract. For an unsigned prototype fix, the brief asks for tests of the demo's
   steps and of security and data boundaries only, and close's review checks those, not
   per-function proof. Sign-off's full proof: the sign-off decision (`client-signoff`) gains a
   `## Proof` section listing each demo workflow step with the test that proves it; the strict
   sign-off review requires every step to name a passing test. Tests: a prototype round passes
   close with demo-step tests and no per-function proof; sign-off refuses a product whose `## Proof`
   leaves a demo step without a test.
4. Light review. Unsigned prototype rounds use a narrow review prompt that checks demo breakage,
   security and data loss only, and `[models.light_review]` sets its model and effort (default:
   the review model at medium). Tests: the light prompt names only those three checks; the setting
   changes the model used; a security finding still blocks.
5. Sign-off reuse. The strict sign-off review run before the customer reply saves its result with
   the product commit, a hash of the answers page, a hash of the sign-off decision's `## Proof` and
   `## Decisions` sections, and the review rules. Accepting sign-off after the reply reuses that
   result while all four are unchanged and reviews again otherwise. Tests:
   review before the reply then acceptance on an unchanged product runs one review; a changed
   answer page or a changed proof mapping runs a second.
6. Hand-off. The sign-off decision's `## Proof` section (demo outcomes and their tests) and its
   `## Decisions` section are the evidence record; SIGNOFF pins both section names. Every story
   created after sign-off starts with a `## Proven by the prototype` section copied from that
   record. The cold read treats the section as settled and reads only the rest; the plan's parts
   list only new or production-risk work. Tests: the first and the second story after sign-off
   both start with the section filled; the cold read raises no note about a proven outcome.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| DESIGN | Design first | the `Design:` line with tree id in read and approval checks, the prototype-design decision rule ROUTING's gate calls, the folder layout and renderer | 1 | src/forge/story.py, src/forge/templates/story.md, src/forge/templates/design/support.js | tests/test_design_first.py | ROUTING | no | |
| CONTEXT | Design and skills reach workers and reviewers | design folder and skill excerpts in the brief and the review input on both tools | 2 | src/forge/templates/brief.md, src/forge/templates/review.md, src/forge/review.py | tests/test_design_context.py | DESIGN | no | |
| ROUTING | Fixes go to the right worker | owns `fix start`: `--kind`, the unsigned-prototype ui gate hook (pinned with a stub DESIGN fills), prototypes no longer forced to design, the same kind on every round, a warning when files disagree | 2 | src/forge/worker.py, src/forge/roles.py, src/forge/task.py, src/forge/cli.py | tests/test_fix_routing.py | | no | |
| PROTOTEST | Prototype test contract | demo-step and boundary tests for prototype rounds, full proof at sign-off | 3 | src/forge/close.py | tests/test_prototype_contract.py | CONTEXT | no | |
| LIGHTREVIEW | Light review | narrow prompt and `[models.light_review]` | 4 | src/forge/score.py, src/forge/templates/review-light.md, src/forge/repo.py | tests/test_light_review.py | CONTEXT | no | |
| SIGNOFF | Sign-off once | saved sign-off review and reuse; the sign-off decision's `## Proof` and `## Decisions` sections pinned | 3, 5 | src/forge/records.py, src/forge/review.py | tests/test_signoff_reuse.py | CONTEXT | no | |
| HANDOFF | After sign-off | the proven section, cold read treats it as settled, and the guide's prototype, story and design steps on both synced copies | 6, 1 | src/forge/story.py, src/forge/templates/cold-read.md, src/forge/templates/skill.md, .claude/skills/forge/SKILL.md, .codex/skills/forge/SKILL.md, docs/guide.md | tests/test_signoff_handoff.py | DESIGN, PROTOTEST, LIGHTREVIEW, SIGNOFF | no | |

New moving parts: none

## Notes

- Shared files have one owner each: story.py is DESIGN's, then HANDOFF's after DESIGN merges;
  the guide and its synced copies are HANDOFF's only.
- Deferred by the owner (15 October): preparing the next change while CI runs, and reviewing only
  changed proof entries after the first pass.
