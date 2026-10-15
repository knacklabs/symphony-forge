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

1. **Every prototype and every story with user-facing parts starts with the design skill's init and an approved design, whose screens and images live in the repo and are named in the plan, so one plan approval covers both.**
2. **Workers and reviewers on both tools receive the named design and the skill guidance their work needs, and each fix goes to the worker kind that matches what it changes, keeping that kind on every round.**
3. **A prototype round proves the demo's steps and its security and data boundaries, and the full proof is required at sign-off.**
4. **The prototype's light review checks only demo breakage, security and data loss, with a model setting of its own.**
5. **Sign-off reviews the whole product once and reuses that review while the product and the answers stay unchanged.**
6. **A story planned after sign-off carries the prototype's proven outcomes and tests, and its plan and cold read cover only what is new or risky for production.**

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

1. Design-first. The guide's prototype and story steps say: run the impeccable skill's `init`
   (PRODUCT.md) when the repo has none, design the screens in a Claude artifact (Design type),
   get the owner's approval of the design with the plan, then copy the artboards into
   `docs/design/<KEY>/` with a renderer (as `docs/board-design/support.js` does) and a 1440 by 900
   image per screen. The plan's builder section names that folder in a `Design:` line. `forge read`
   and the story checks refuse a plan whose user-facing parts (User-facing = yes) have no
   `Design:` line or whose folder has no images; backend-only plans pass. On a Codex-only host
   with no Claude artifact tool, the guide says to make the same artboards as HTML files in the
   folder. Tests: a story with a user-facing part and no design is refused with the next step; a
   backend-only story passes; a story with the folder passes.
2. Context and routing. The worker brief and the close review input both carry the plan's
   `Design:` folder (paths and images) and short excerpts of the skills the part needs (impeccable
   and the frontend role for user-facing parts; test-audit for test changes), the same on Codex
   and Claude. A fix's kind follows what it changes: user-facing files go to the design worker,
   backend files to the backend worker, documents and generated files to the mechanical (lite)
   worker; unsigned prototype fixes stop forcing the design worker. A fix round keeps the kind its
   first round used, on both tools. Tests: a backend prototype fix routes to the backend worker; a
   UI fix routes to design; round 2 keeps round 1's kind on Codex and on Claude; the brief and the
   review input name the design folder.
3. Prototype test contract. For an unsigned prototype fix, the brief asks for tests of the demo's
   steps and of security and data boundaries only; the proof list need not cover every changed
   function. At sign-off, the strict review requires the full proof for the whole product, as
   today. Tests: a prototype round passes close with demo-step tests and no per-function proof;
   sign-off refuses the same product without the full proof.
4. Light review. Unsigned prototype rounds use a narrow review prompt that checks demo breakage,
   security and data loss only, and `[models.light_review]` sets its model and effort (default:
   the review model at medium). Tests: the light review prompt names only those three checks; the
   setting changes the model used; a security finding still blocks.
5. Sign-off reuse. The strict sign-off review's result is saved with the product commit, the
   answers page and the review rules it saw. Accepting sign-off reuses it while all three are
   unchanged and reviews again otherwise. Tests: two acceptance calls on an unchanged product run
   one review; a change to the answers runs a second.
6. Hand-off. The first story planned after sign-off gets a `## Proven by the prototype` section,
   filled from the sign-off record: the demo's outcomes, the tests that prove them and the
   decisions made. The cold read treats that section as settled and reads only the rest; the
   plan's parts list only new or production-risk work. Tests: a story after sign-off starts with
   the section filled; the cold read raises no note about a proven outcome.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| DESIGN | Design first | the `Design:` line rule in read and story checks, the design folder layout and renderer | 1 | src/forge/story.py, src/forge/templates/story.md, src/forge/templates/design/support.js | tests/test_design_first.py | | no | |
| CONTEXT | Design and skills reach workers and reviewers | design folder and skill excerpts in the brief and the review input on both tools | 2 | src/forge/templates/brief.md, src/forge/templates/review.md, src/forge/review.py | tests/test_design_context.py | DESIGN | no | |
| ROUTING | Fixes go to the right worker | kind by changed files, unsigned prototypes no longer forced to design, the same kind on every round | 2 | src/forge/worker.py, src/forge/roles.py | tests/test_fix_routing.py | | no | |
| PROTOTEST | Prototype test contract | demo-step and boundary tests for prototype rounds, full proof at sign-off | 3 | src/forge/close.py | tests/test_prototype_contract.py | CONTEXT | no | |
| LIGHTREVIEW | Light review | narrow prompt and `[models.light_review]` | 4 | src/forge/score.py, src/forge/templates/review-light.md, src/forge/repo.py | tests/test_light_review.py | CONTEXT | no | |
| SIGNOFF | Sign-off once | saved sign-off review and reuse | 5 | src/forge/records.py | tests/test_signoff_reuse.py | | no | |
| HANDOFF | After sign-off | the proven section, cold read treats it as settled, and the guide's prototype, story and design steps on both synced copies | 6, 1 | src/forge/story.py, src/forge/templates/cold-read.md, src/forge/templates/skill.md, .claude/skills/forge/SKILL.md, .codex/skills/forge/SKILL.md, docs/guide.md | tests/test_signoff_handoff.py | DESIGN, PROTOTEST, LIGHTREVIEW, SIGNOFF | no | |

New moving parts: none

## Notes

- Shared files have one owner each: story.py is DESIGN's, then HANDOFF's after DESIGN merges;
  the guide and its synced copies are HANDOFF's only.
- Deferred by the owner (15 October): preparing the next change while CI runs, and reviewing only
  changed proof entries after the first pass.
