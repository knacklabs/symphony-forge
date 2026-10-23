---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-23T14:41:37.300256+00:00
seconds: 608.531
read_hash: f60fac629e52226503dd7c0bb1e6525709320a8c
round: 9
passed: no
doc_seen: f60fac629e52226503dd7c0bb1e6525709320a8c
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 7b2cdaf64ece596209296c741c673c6c07614ebd
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a13ef6-7126-7692-8ac4-4f759a6cdc3a
session:
blocked_rounds: 1
loop_choice:
loop_reason:
---
# Cold read notes

Written by `forge read`. Under every blocking finding, write one disposition line, amend the
doc, then run `forge read <doc>` again until a round has no blocking notes. Notes marked
`Advisory:` are recorded without requiring a disposition or another round:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

A finding inside What counts is cut or deferred. Keep one only when it falls outside that boundary
or is factually wrong, and give as the reason the Leave out line, the missing Raise line, the
cited fact that disproves it, or the human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: Prototype design approval has no defined path.
   Raise: Plan gap. `plans/FORGE-PACE-1.md:37` requires prototypes to receive design approval with a plan, but its implementation at lines 64–73 covers story plans only. Prototypes use fixes; `src/forge/story.py:122–123` refuses story creation before sign-off, and `src/forge/task.py:381–386` creates fixes without a plan or design reference. The required prototype approval artifact and command are unspecified.
   Gain 5, Work 3, Harm 3

   Disposition: cut
2. Blocking: Exporting the design after approval prevents the preceding cold read from passing.
   Raise: Plan gap. `plans/FORGE-PACE-1.md:66–70` says to obtain plan approval, then copy the artboards and images into the repository, while requiring `forge read` to refuse until those images exist. The cold read precedes approval (`src/forge/templates/cold-read.md:3`). Following the stated order stalls every new user-facing story.
   Gain 4, Work 1, Harm 2

   Disposition: cut
3. Blocking: The proposed design reference does not bind approval to the approved design.
   Raise: Not done. `plans/FORGE-PACE-1.md:68` places `Design:` below the builder heading. Approval hashes exclude that section and all image contents (`src/forge/story.py:651–660`, `src/forge/task.py:70–74`). After approval, replacing the reference with another populated folder would satisfy the proposed gate while workers receive a different design. No rule or test covers this ordinary design revision.
   Gain 4, Work 2, Harm 3

   Disposition: cut
4. Blocking: Routing by changed files cannot select the first fix worker.
   Raise: Plan gap. `plans/FORGE-PACE-1.md:77–81` selects and preserves the first round’s kind from changed files. A newly started fix contains only its state record (`src/forge/task.py:381–386`); worker selection happens before its builder runs (`src/forge/worker.py:119–138`). The plan supplies neither an initial classification input nor a rule for this empty-diff case. Its routing tests do not specify that normal starting state.
   Gain 5, Work 3, Harm 3

   Disposition: cut
5. Blocking: “Full proof at sign-off, as today” relies on a contract that does not exist.
   Raise: Plan gap. `plans/FORGE-PACE-1.md:83–87` defers full proof to sign-off without defining its whole-product source or mapping. Existing proof lists map an individual change’s Done-when items to tests (`src/forge/templates/review.md:74–89`). Sign-off bypasses that input and constructs a separate snapshot-review prompt (`src/forge/review.py:976–984`, `src/forge/templates/review.md:297–304`). The builder cannot determine what complete proof must be collected or what its absence must refuse.
   Gain 5, Work 3, Harm 3

   Disposition: cut
6. Blocking: SIGNOFF and HANDOFF share an undefined evidence record.
   Raise: Plan gap. `plans/FORGE-PACE-1.md:92–98` saves a review result, commit, answers and rules, then expects that record to supply proven outcomes, proving tests and decisions. The existing sign-off reviewer returns only a commit (`src/forge/review.py:927`), and acceptance records `reviewed_commit` (`src/forge/records.py:286`). Neither the producer’s task nor an earlier task pins the additional fields, their sources or their format for HANDOFF.
   Gain 5, Work 2, Harm 3

   Disposition: cut
7. Blocking: The unchanged sign-off test can pass without implementing review reuse.
   Raise: Test. `plans/FORGE-PACE-1.md:94–95` requires two acceptance calls to run one review. Existing code already does that when the first call accepts: the second returns immediately for an accepted decision (`src/forge/records.py:240–242`). The actual duplicated-review path is review before the customer reply, followed by acceptance after recording it (`src/forge/records.py:286–301`). The named test does not require that path and therefore permits the reported problem to remain.
   Gain 4, Work 2, Harm 3

   Disposition: cut
8. Blocking: The hand-off implementation covers only the first production story.
   Raise: Not done. `plans/FORGE-PACE-1.md:21–22` promises inherited prototype proof for **each new story**, but lines 96–100 prescribe and test it only for the **first** story after sign-off. Story creation independently starts from its template each time (`src/forge/story.py:148–151`); nothing carries that first story’s section into subsequent stories. The second story can repeat the planning and cold-read work this change promises to eliminate.
   Gain 4, Work 1, Harm 2

   Disposition: cut

## Round 2

9. Blocking: Disputed keep 3: moving the design reference into `Why` still does not bind approval.
   Raise: Not done. The new rule at `plans/FORGE-PACE-1.md:67–71` assumes `Why` is approved text. Both approval hashes exclude it (`src/forge/story.py:83`, `src/forge/task.py:70–74`). Updating the images and their matching tree id in `Why` therefore leaves the approval hash unchanged; task start still accepts that hash (`src/forge/task.py:260–265`). The newly prescribed placement does not provide the promised approval invalidation.
   Gain 4, Work 2, Harm 3

   Disposition: cut
10. Blocking: The new optional prototype flag leaves the normal prototype build path outside the design gate.
   Raise: Plan gap. `plans/FORGE-PACE-1.md:74–77` gates a build marked `--prototype`, but does not define what happens when that flag is omitted. Existing fix creation automatically identifies prototypes from repository state (`src/forge/task.py:384–385`, `src/forge/repo.py:519–526`). An ordinary `forge fix start ... --kind ui` in that repository remains a prototype build, yet the proposed rule does not require its design approval. The named gate test can pass while this normal path bypasses it.
   Gain 4, Work 2, Harm 3

   Disposition: cut
11. Blocking: DESIGN and ROUTING introduce a shared command contract without an owner or dependency.
   Raise: Plan gap. `plans/FORGE-PACE-1.md:76` introduces `--prototype`; lines 84–87 introduce `--kind`. Both require the same `fix start` argument row and `fix_start` implementation (`src/forge/task.py:433–436`, `src/forge/task.py:363–386`). The tasks at lines 118–120 can run independently, and neither first pins their combined behavior, including the design-preparation fix that must run before approval. Assign the shared command contract to one task and make the gate consumer depend on it.
   Gain 4, Work 2, Harm 2

   Disposition: cut
12. Blocking: Sign-off reuse excludes the newly introduced proof and decisions from its validity check.
   Raise: Plan gap. `plans/FORGE-PACE-1.md:93–108` makes `## Proof` and `## Decisions` sign-off evidence, but permits reuse based only on product commit, answers and review rules. Decision files are excluded from the product snapshot (`src/forge/review.py:854–868`), and recording the customer reply edits that decision before acceptance commits it (`src/forge/records.py:255–286`, `301–302`). Changing a proof mapping during that edit leaves all three cache inputs unchanged, allowing acceptance and subsequent story hand-off to use evidence the cached review never checked.
   Gain 4, Work 2, Harm 3

   Disposition: cut

## Round 3

13. Blocking: The new backend exemption contradicts design approval before the prototype’s first build.
   Raise: Not done. `plans/FORGE-PACE-1.md:39` requires approval before the first prototype build, but the changed rule at lines 78–83 explicitly permits backend builds before approval and requires a test proving that exemption. An API-first prototype can therefore begin implementation before its design is approved. Backend fixes use the same prototype build lane (`src/forge/task.py:381–386`); the plan defines no separate preparation-only restriction.
   Gain 4, Work 1, Harm 2
   Disposition: cut

## Round 4

No findings.

## Round 5

14. Blocking: The inherited gate hook cannot refuse backend builds.
    Raise: Plan gap. `plans/FORGE-PACE-1.md:106–108` requires backend fixes to be refused through ROUTING’s hook, but its merged caller invokes that hook only for `ui` (`src/forge/task.py:518–519`). The plan explicitly leaves ROUTING unchanged at line 166, and BUILD owns no caller change. Filling the hook cannot make the newly required backend-refusal test pass.
    Gain 5, Work 2, Harm 3

   Disposition: cut

15. Blocking: BUILD and SIGNOFF depend on an undefined distinction between canvas and working app.
    Raise: Plan gap. `plans/FORGE-PACE-1.md:59–60`, `97–109` and `131–139` use app-code presence to grant build permission and choose whether strict review runs. No earlier task pins that shared predicate or its treatment of canvas HTML and generated scaffolding. `forge init` already writes a Dockerfile (`src/forge/init.py:138–147`), while `repo.is_prototype` determines only stage and sign-off status (`src/forge/repo.py:530–552`). BUILD and SIGNOFF can therefore implement incompatible classifications.
    Gain 5, Work 2, Harm 3

   Disposition: cut

16. Blocking: The docs-only exception cannot be evaluated at fix start.
    Raise: Plan gap. `plans/FORGE-PACE-1.md:106–108` exempts fixes that change only `docs/` or `plans/`, including an initial canvas-artboard fix. At that point the command has only why, done-when, kind and slug (`src/forge/task.py:579–584`); it creates the checkout before any worker changes files (`src/forge/task.py:522–528`). The plan supplies no prospective paths or other input for distinguishing a docs-only UI fix from a UI app build. The mechanical-fix test does not prove this separate exception.
    Gain 4, Work 2, Harm 2

   Disposition: cut

17. Blocking: Disputed keep 12: the newly added signed-design reference is outside review reuse.
    Raise: Plan gap. `plans/FORGE-PACE-1.md:138–139` adds `## Signed design` to the sign-off evidence, but lines 131–134 hash only Answers, Proof, Decisions and review rules alongside the product commit. Decision files are excluded from the product snapshot (`src/forge/review.py:894–908`). Switching the reference between two existing canvas folders while recording the customer’s reply leaves those cache inputs unchanged, allowing reuse against a different named design and copying it into subsequent stories as settled evidence.
    Gain 4, Work 2, Harm 3

   Disposition: cut

## Round 6

18. Blocking: A root README is treated as a working build and grants build permission.
    Raise: Functional. The new classification at `plans/FORGE-PACE-1.md:93–98` counts `README.md` as app code. An existing unsigned canvas repo with a merged README therefore becomes a working prototype on upgrade, despite having no app or accepted build request. Subsequent app changes bypass the decision gate, and canvas sign-off incorrectly requires working-product proof. Forge already recognizes root Markdown as documentation (`src/forge/review.py:577–583`).
    Gain 4, Work 2, Harm 3

   Disposition: cut

19. Blocking: Unmerged app code can pass through canvas sign-off and escape the build-decision gate.
    Raise: Plan gap. The new working-build predicate checks an accepted request or app changes on the default branch (`plans/FORGE-PACE-1.md:97–98`), while lines 112–115 permit app code to exist on an unmerged fix. Canvas sign-off on that fix therefore sees no working build and skips strict review. Acceptance records the decision in that checkout (`src/forge/records.py:301–302`), and `repo.is_prototype` immediately treats its local accepted sign-off as signed (`src/forge/repo.py:545–551`). The subsequent close no longer applies the unsigned-prototype gate, allowing those app changes to merge without the requested owner decision.
    Gain 5, Work 2, Harm 3

   Disposition: cut

## Round 7

20. Blocking: A canvas content mismatch now sends the user to request a working build.
    Raise: Functional. The new “otherwise” at `plans/FORGE-PACE-1.md:105–107` applies both to app-code changes and to a mismatched canvas tree id. Revising the canvas while sign-off is pending therefore produces `forge decision new prototype-build` even when no app code exists. That command creates a separate decision (`src/forge/records.py:218–226`); it does not repair the signed-design reference. The prescribed recovery cannot resolve this normal canvas-sign-off failure.
    Gain 3, Work 2, Harm 2

   Disposition: cut

## Round 8

No findings.

## Round 9

21. Blocking: The promised Opus check selects a setting that defaults to Sonnet.
    Raise: Plan gap. `plans/FORGE-PACE-1.md:165` specifies `[models.design.claude]` as Opus at high, but new repos receive Sonnet at xhigh (`src/forge/init.py:108–110`), and older repos default to the same (`src/forge/repo.py:473`, `663`). No task owns changing those defaults. The test at plan line 182 verifies selection of the design setting, so it passes while the required Opus check runs on Sonnet.
    Gain 4, Work 2, Harm 3
   Disposition: cut - the completeness check pins Claude Opus 5.5 (claude-opus-5-5) at high as its own Forge default, as Forge pins the grill default, and does not read [models.design]; with no claude command it runs on gpt-6.1-sol at high and says so; no other model runs it (details 2 and its tests).

22. Blocking: The completeness check relies on an entity inventory that the shipped brief does not collect.
    Raise: Plan gap. `plans/FORGE-PACE-1.md:167–168` requires `## Things it keeps track of` as the source of entities, fields and options. The shipped brief has Summary, Users, Key flows and Constraints, but no such inventory (`src/forge/templates/skeleton/docs/product/BRIEF.md:5–27`). Neither the new collection instructions nor the refusal rules require that section to be populated. A client following the existing brief can therefore reach the check without the field inventory needed to detect omissions.
    Gain 4, Work 2, Harm 3
   Disposition: keep - main's shipped docs/product/BRIEF.md already has `## Things it keeps track of`, which the setup interview fills; the plan now also has sign-off refuse, naming the section, when that section is missing or empty (details 2 and its test).

23. Blocking: The completeness check omits the brief’s explicit screen-flow requirements.
    Raise: Not done. The inputs prescribed at `plans/FORGE-PACE-1.md:167–168` exclude `## Key flows`, where the shipped brief records user journeys (`src/forge/templates/skeleton/docs/product/BRIEF.md:19–23`). A canvas can contain every entity and field yet omit a required import wizard or checkout flow. The checker receives neither requirement, so the new contract cannot establish the promised absence of missing screens against the brief.
    Gain 4, Work 2, Harm 3
   Disposition: cut - the check also reads the brief's `## Key flows` and reports each flow that no screen carries; the brief hash covers that section (details 2, its test, and the checklist lead).

24. Blocking: Small-change stories can be blocked by superseded prototype requirements.
    Raise: Functional. `plans/FORGE-PACE-1.md:135–138` sends `Design: none` stories the original signed prototype folder, while lines 212–214 require every touched screen to retain its listed fields and components. After an approved production story removes a prototype field, a subsequent label-only story receives the obsolete list and incurs a P1 for that intentional removal. Brief generation currently reads the current story (`src/forge/worker.py:496–513`); the new rule supplies no resolution of intervening approved designs, and its label-only test covers no such preceding change.
    Gain 4, Work 2, Harm 3
   Disposition: cut - a `Design: none` story gets the signed screen list as context only; the review holds a missing listed component or field only on screens that the item's own approved design folder lists (details 1 and 4, and a test in item 4).
