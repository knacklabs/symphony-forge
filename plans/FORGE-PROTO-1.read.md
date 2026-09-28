---
reader: codex (gpt-6-sol)
read_at: 2026-09-28T10:26:52+00:00
read_hash: 965609a1fe40dd94a5423e280b2cdc86234ddf18
amended_hash: 235eb71e4d43637b506a941af88996eb1541e4ff
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. SIGNOFF is missing a required dependency on NEXT.
   The plan says SIGNOFF imports the answers parser that NEXT adds to `nextstep.py`, but SIGNOFF’s `After` column omits NEXT. Add that dependency, or give the parser to an earlier task. [Plan](/plans/FORGE-PROTO-1.md:71).
   Disposition: cut SIGNOFF now waits on NEXT, which owns the parser.

2. The proposed review path does not yet establish a whole-prototype review.
   Forge’s current Autoreview call uses branch mode against a base commit, and its instructions anchor findings to changed files. The plan must pin how SIGNOFF reviews unchanged product files, defines “product file,” and verifies Astra at high effort without fallback; the existing invocation also passes model and effort as `codex=...`. Split SIGNOFF into review coverage and acceptance validation if this exceeds the task’s size limit. [Review invocation](/src/forge/review.py:228) · [review instructions](/src/forge/templates/review.md:114).
   Disposition: cut the Notes pin an empty root commit in the review clone, the product-file definition and the codex=gpt-6-astra high arguments, checked by a test.

3. A sign-off template alone cannot enforce the customer’s attestation.
   `decision_accept` currently requires only the three generic decision sections. SIGNOFF must pin and validate the named customer person, approval place and date, demo address, and a word-for-word quote of the reviewed answers page, including what `--by` means for this decision. Otherwise an incomplete decision can become accepted. [Acceptance code](/src/forge/records.py:230) · [template](/src/forge/records.py:94).
   Disposition: cut Done-when 8 now makes acceptance validate the customer, where and when, the demo and the word-for-word answers, and says what --by means.

4. The shared answers parser needs a validity contract before NEXT and SIGNOFF use it.
   The line formats do not say how to handle duplicate or malformed topics, and Done-when 6–7 omit a must-answer topic incorrectly marked `later`. Pin which checkout’s answers page is authoritative and make invalid must-answer lines count as open for `forge next` and block acceptance. [Formats and consumers](/plans/FORGE-PROTO-1.md:84) · [current `forge next` flow](/src/forge/nextstep.py:65).
   Disposition: cut the parser reads the checkout's own brief, and missing, ask-the-client, wrongly deferred, repeated or malformed must-answer lines count as open and block.

5. DEPLOY cannot deliver the stated runtime from the scoped Dockerfile alone.
   The new client scaffold contains documents, while the stack convention names app directories but pins no frontend build command, backend static-serving path, migration command, or health endpoint. Assign those runtime contracts to DEPLOY or explicitly to the prototype fix before claiming Done-when 10. [Scaffold](/src/forge/init.py:68) · [stack layout](/src/forge/templates/conventions/stack.md:19).
   Disposition: cut DEPLOY pins the build, serve, migrate and health contract in the stack conventions; the prototype's first fix builds to it.

6. The deferred-answer handoff stops at the cold-read finding.
   The confirmed spec also requires the disposition to record the answer, the story Notes to carry `Decided: ...`, and the first task to update `BRIEF.md`. TOPICS covers only the `Decide first:` check. Assign and verify the remaining handoff so the decision reaches the answers page. [TOPICS scope](/plans/FORGE-PROTO-1.md:70).
   Disposition: cut Done-when 9 and TOPICS now carry the whole hand-off: disposition, Decided line in Notes, first task updates the answers page.

7. Remove task ordering that is only file or documentation coordination.
   SIGNOFF’s link to GATE appears to serialize separate functions in `records.py`; DEPLOY’s link to TOPICS and DOCS’ links to SIGNOFF and DEPLOY name no code they consume. Give each shared line a single owner or a small final wiring task, and reserve `After` for actual dependencies. [Tasks table](/plans/FORGE-PROTO-1.md:69).
   Disposition: cut DEPLOY and DOCS wait on nothing; SIGNOFF waits only on NEXT's parser; Forge's overlap rule orders shared files.

8. Startup migrations need a stated risk and failure contract.
   Done-when 10 runs migrations whenever the image starts, including when the same image later serves production. The plan’s “Risks: none” does not cover failed, concurrent, or destructive migrations. Pin startup and health behavior and the data protection expected before deployment. [Deployment requirement](/plans/FORGE-PROTO-1.md:52) · [risk entry](/plans/FORGE-PROTO-1.md:58).
   Disposition: cut added the migration risk with its containment, and health answers only after migrations succeed.
