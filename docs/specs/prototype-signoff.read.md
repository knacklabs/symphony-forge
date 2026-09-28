---
reader: codex (gpt-6-sol)
read_at: 2026-09-28T10:16:25+00:00
read_hash: 163a9bc7d80444b619c5c559c8edef0f6a26053e
amended_hash: 67ba99faf85c49993fc15eeb0d279dda2331d0ec
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. The deployment scope contradicts itself.
   The first prototype fix must add container and platform deploy files, while Out of scope excludes infrastructure code before sign-off. Say which deploy files are allowed before sign-off.
   Disposition: cut Out of scope now names only infrastructure code such as Terraform; the Dockerfile is the one deploy file.

2. The deploy target is not specified.
   “Our platform account” does not identify a platform or its deploy file format. Pin the platform, how the image and managed Postgres are provisioned, and how restricted access is provided. A new platform vendor also needs a stated risk.
   Disposition: cut pinned to our AWS deploy platform, which builds the repo's Dockerfile and provides Postgres (owner, 2026-09-28).

3. The twelve-topic table cannot be implemented as written.
   It names topics but supplies none of the promised questions, options, or defaults. Pin those entries and the exact answer labels and source format; the `Logging` example is outside the twelve topics.
   Disposition: cut the table now gives each topic's question, options with the default first, and must or may wait; the Logging example is now covered by the standards line.

4. Mandatory topics need a sign-off checkpoint.
   “Ask when first matters” may never trigger production hosting or the sign-off person during prototype work. Require a pass over all mandatory topics before review, and define how “Ask the client” is recorded and resolved.
   Disposition: cut added a checkpoint: forge next lists open must-answer topics before the review, and 'ask the client' lines are recorded and resolved on the answers page.

5. Sign-off and review need one bound revision.
   Decisions are currently accepted in a fix checkout, while the proposed review examines product files on the default branch. Define which committed answers and prototype are reviewed, how that revision is tied to the customer’s approval, and when later changes invalidate it. Also specify whether older accepted sign-offs bypass the new review.
   Disposition: cut the review runs in the sign-off fix's checkout after merging the default branch, the decision records the reviewed commit, and earlier accepted sign-offs stay valid.

6. The story cold-read remedy conflicts with the one-read workflow.
   A deferred answer may be resolved after the cold read, but approval currently checks the story document rather than the answers page. Pin where the answer is committed and how approval verifies it is resolved without requiring a second cold read.
   Disposition: cut the answer is recorded in the finding's disposition and the story's Notes, and the story's first task updates the answers page; no second read.

7. The fix allowance has no end rule for work already in progress.
   A fix started before sign-off retains its recorded `allow_large` allowance afterward. Define whether it keeps that allowance or returns to the normal limit.
   Disposition: cut a fix keeps the allowance it started with.

8. Acceptance criterion 8 does not establish the first-day success measure.
   Scaffold files and a guide do not show that a prototype is live and usable. Add an observable deploy and health or demo check, or narrow the success measure.
   Disposition: cut the success measure now has a metric, baseline, target and check date, measuring the live subdomain on the next project.
