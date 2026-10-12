# Reads and reviews score each note on Gain, Work and Harm, and only notes above the bar hold work back

4 parts · Risks: none one-way · New moving parts: none

## What changes for you

- Every note from a plan's cold read and every finding from a code review gets three scores from
  1 to 5. Gain says how much fixing it helps. Work says how much effort the fix takes. Harm says
  what breaks if it goes wrong. The scores are a judgement, not a measurement.
- A note about security, data loss or a migration always gets Harm 4 or more.
- One bar decides what happens to each note:

  | When | What happens |
  |---|---|
  | Harm 4 or 5, or Gain 5 | It holds the work. Fix it now. |
  | Gain 3 or 4, and Work 1 or 2 | The worker fixes it in this round. |
  | Gain 3 or 4, and Work 3 or more | It becomes a follow-up fix. The merge goes on. |
  | Gain 1 or 2 | Forge lives with it and records it. |
  | Harm 3, and it adds scope beyond the Done when or undoes your decision | The coordinator asks you. |

- A Gain 1 or 2 note never holds work back, even when the reviewer calls it serious. Only Harm 4
  or more overrides that.
- Notes below the bar are not lost. The read notes and the pull request list each one with its
  scores, as a follow-up or as lived with.
- A note that you, the coordinator or Forge already settled goes to every later read and review
  as known and accepted. A reader can raise it again only with new evidence of harm.
- Forge stops a change after three rounds only when a note at the bar comes back, or a note with
  Harm 3 or more is still open. When you don't answer a stop in 30 minutes, Forge narrows the
  change on its own only if every open note has Harm 1 or 2. Otherwise it waits for you.
- Stop questions and the coordinator's updates show the open notes as one ranked table: number,
  the problem and who it hits, Gain, Work, Harm, and what the coordinator proposes. Then they say
  what accept, narrow and split each do.
- The coordinator settles reversible Harm 1 and 2 notes itself and tells you after. It asks you
  only for Harm 3 or more, new scope beyond the approved Done when, your approval and merge steps,
  or undoing a decision you made.
- The README explains the scores and the bar, with three worked examples.

## Why

Reviews and reads have one lever today: a note is serious or it isn't. Most serious notes are not
worth a round. From 10 October 15:00 to 11 October, 73 reviews blocked on 135 serious findings.
90 of them (67%) were "Not done", 32 functional, 10 about tests and 3 about standards. Only 9
were raised again in a later round. One fix got 9 serious findings over 5 rounds, each about one
more language, shell or test layout that its Done when never named.

We scored 18 findings from three recent fixes by hand. 8 fall below the bar. Skipping those would
have saved about 4 rounds, roughly 4 hours. The direction is clear; the exact counts are rough.

This one story replaces two fixes that were started but not built: scoring options and findings
on value, effort and risk, and passing the plan's accepted read notes to the code review. It
builds on the fix in flight that makes stop questions plain, and on the fix that gives a stop a
default answer after 30 minutes.

## Done when

1. **Every cold-read note and every review finding shows a Gain, Work and Harm score from 1 to 5, and a note about security, data loss or a migration never shows Harm below 4.**
2. **A read passes and a change reaches Ready when no note is at the bar; a Gain 1 or 2 note never holds work back unless its Harm is 4 or more, and every note below the bar is listed with its scores in the read notes or the pull request.**
3. **A note already settled by the owner, the coordinator or Forge reaches every later read and review as known and accepted, and comes back only with new evidence of harm.**
4. **Forge stops a change after three rounds only when a note at the bar comes back or a note with Harm 3 or more is open, and when the owner doesn't answer in 30 minutes it narrows on its own only if every open note has Harm 1 or 2.**
5. **Every stop question and coordinator update shows the open notes as one table ranked by score, and the coordinator settles reversible Harm 1 and 2 notes itself and tells the owner after.**
6. **The README explains the scores and the bar with three worked examples, and a repo that upgrades in the middle of a change keeps its saved reads and reviews holding work back as before until their next round scores them.**

## New and existing repos

- **New repos** (init or adoption): from their first read and review, every note is scored and
  the bar decides what holds work back. The guide carries the table rule and the coordinator's
  rule. Tested on a repo made by `forge init`.
- **Existing repos** (on upgrade to this release): the next read round and the next review are
  scored and judged by the bar, with nothing to migrate and no setting to change. The guide
  arrives through `forge sync` as usual. Reads and reviews saved before the upgrade have no
  scores. They keep holding work back exactly as before until their next round. Tested on the
  adopted earlier-release fixture moved to this release, with a blocked review and a blocked read
  saved before the upgrade.

## Risks

Risks: none one-way. Every part reverts with its pull request. After a revert, scores stay in
saved notes as plain text, and Forge goes back to blocking on the reviewer's serious label.

Trade-off, accepted by the owner on 2026-10-11: a finding the reviewer calls serious but scores
Gain 1 or 2, with Harm below 4, no longer holds the merge. The pull request lists it instead.
Scores are the reviewer's judgement. Only the reviewer scores, so a worker can't lower them, and
scores change nothing in CI.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Every new test file starts with `STORY = "FORGE-SCORE-1"`; each Done-when item has exactly one
test function, `test_<n>_...`, that runs the forge command (never imports forge), on a repo made by
`forge init` and on `tests/fixtures/adopted-v1.2.2` moved to this release (the `client` fixture in
`tests/test_conflicting_pull_requests_stop_check_waits.py` shows the pattern). Only the existing
`env` stubs (GitHub's `gh`, Autoreview and Codex, as in `tests/test_close.py`, and the cold reader
as in `tests/test_cold_read_blocking_notes.py`) and elapsed time are faked; the stubs write the
scored findings and notes each test needs.

**The score line.** One line, the same in both places: `Gain <g>, Work <w>, Harm <h>`, each an
integer 1 to 5. A cold-read note carries it as the note's last line. A review finding carries it
as the first line of the finding's `body`. Autoreview's finding schema sets
`additionalProperties: false` (allowed: title, body, priority, confidence, category,
code_location), so the scores can't be separate JSON fields; the body line is the place Autoreview
passes through (principle 7: adapt, never mirror). `priority` stays as Autoreview's field, and the
bar ignores it except for unscored saved results.

**The rubric** (in both templates, marked "judgement, not measurement"):

| Score | Gain (how much fixing helps) | Work (effort to fix) | Harm (what breaks if it goes wrong) |
|---|---|---|---|
| 1 | wording, a rare edge nobody named | a line, no new test | nothing; a revert undoes it |
| 3 | a Done-when item partly unmet for a named case; a test that passes with the code broken | one file and one command-level test, under an hour | client-visible behaviour change, reversible by a revert |
| 5 | security, data loss, the main case of a Done-when item not done | a new module, a second platform or language, a migration | one-way: data, a migration, a release clients upgrade to |

Anchors: "Close's default test selection breaks Go repos" Gain 3, Work 4, Harm 2; "Close skips
Jest `__tests__` folders" Gain 2, Work 2, Harm 1; "A blocked review is shown as waiting for checks
when tests pass on retry" Gain 3, Work 2, Harm 1; "Promotion accepts an uncommitted roadmap entry"
Gain 4, Work 2, Harm 2. From scoring about 60 findings by hand on 11–12 October: "A stuck stop's
narrow or split answer never reaches the worker" Gain 4, Work 1, Harm 1 (fix now); "Land shows a
generic waiting line instead of the stop question" Gain 3, Work 1, Harm 1 (fix now); "Doctor credits
a model to the wrong file in a rare mix of local settings" Gain 2, Work 1, Harm 1 (live with);
"Upgrade pull requests are checked by the previous release" Gain 2, Work 4, Harm 1 (live with); "A
proof test checks only the question's first lines" Gain 2, Work 1, Harm 1 (live with).

**Lessons from scoring by hand** (go into both templates' rubric text, in plain words):
- Raise a finding only after checking it against the code at the current commit, and name the
  file and line. Hand scoring found several stop findings already fixed at the reviewed commit, and
  several suggested changes that could not work.
- A "Not done" finding scores Gain by how much of the Done-when stays unmet: the main case unmet is
  Gain 4–5; one more rare combination on a clause whose main case works is Gain 1–2. One fix
  drew a new rare angle on the same clause in each of four rounds, and another reached nine rounds.
  When earlier rounds already raised a clause, the body says so and proposes narrowing that clause.
- Only the reviewer scores. The coordinator and the worker never re-score: they follow the bar's
  outcome, and the coordinator asks the owner only in the bar's "ask the owner" row. Notes in a
  proof list do not lower a score; before scoring, a lived-with finding the Done-when names word
  for word came back every round.

**The bar, as code** (`score.bar`, checked top-down):
1. Harm ≥ 4, or Gain 5 → `block`.
2. Gain 3–4 and Work ≤ 2 → `fix now` (at the bar; holds the work like `block`).
3. Gain 3–4 and Work ≥ 3 → `follow-up` (below the bar).
4. Gain ≤ 2 → `live with` (below the bar).

"At the bar" means `block` or `fix now`, at any priority. The bar's "ask the owner" row (Harm 3
with new scope, or undoing an owner decision) is the coordinator's judgement, not code: Forge can't
tell new scope from text. It lives in the guide (part GUIDE). The row order joins the owner's two
rules: "Gain 1–2 never blocks" means the serious label never overrides the bar; the Harm floor
exists so that security, data loss and migration notes do block.

**The Harm floor.** `score.normalise(title, body)` raises Harm to 4 when it was scored lower and
the `Raise:` line is Security or Data loss, or the title or the body names a migration. The
rewritten score line ends `(floor: security)`, `(floor: data loss)` or `(floor: migration)`, so
whoever reads the notes sees why. A cold-read note passes its first line as the title and the rest
as the body.

**Unscored notes** (saved before the upgrade, or a reader that forgot the line): a cold-read note
with no score line is judged by its `Blocking:`/`Advisory:` label as today (unmarked = blocking).
A saved review result whose findings have no scores is judged by priority, as `review.blocking`
does today. A new review finding with no score line, or one out of range, makes `_finding` return
None, so the run fails with today's "it wrote findings Forge cannot read" and close's existing
second attempt runs. SCORES therefore updates, in the same change, every existing test that builds
review findings without a score line, so main stays green: the `finding` helper in
`tests/test_close.py` (lines 60–64) writes a default score line (`Gain 5, Work 2, Harm 4` for
P0, which is `block`; `Gain 3, Work 2, Harm 1` for P1; `Gain 2, Work 1, Harm 1` for P2/P3), which
keeps each test's outcome under today's and the light gate, the P0 refusal case
near line 268 included; other tests with their own unscored findings get the same line.

**Light reviews.** The prototype's light review passes `--max-priority P3` like every other review
(`review.py` near line 583, and the fingerprint's level stays as today), and Forge applies the
P0-only level after scoring: under it only `block` counts. A P1 scored Gain 5 or Harm 4 is never
filtered out before the bar sees it. BAR updates `tests/test_aha_review.py` (lines 49–50) and
`tests/test_reviews_use_repository_tool.py` (line 31), which today expect `--max-priority P0`, to
expect P3 and to show the P0-only level applied after scoring.

**Stop-question call sites.** SCORES pins `score.table(rows)` as a stub that returns today's
bullet lines, and makes `story.stop_question`, `story.read_question` and `close.stop_question`
pass each row's scores and call it (a one-line call site each). GUIDE then fills `score.table`
alone, so BAR and GUIDE share no path and build in parallel after SCORES.

### Done-when details

1. New module `src/forge/score.py` (pinned by SCORES, used by the other parts): `parse(text)`
   returns `(gain, work, harm)` or None from the score line; `normalise(title, body)` applies the
   Harm floor and returns the scores and the body with the score line rewritten; `bar(scores)`
   returns `block`, `fix now`, `follow-up`, `live with`, or None for no scores. `review._finding`
   calls `normalise` on the finding's title and body and adds `gain`, `work`, `harm` to the finding
   dict; the module docstring's list of fields Forge reads stays true (title, body). `forge read`
   runs each new note of the reader's output through `normalise` where it numbers them
   (`story.read`, near line 340). Templates: `cold-read.md` (first round and both later-round
   blocks) and `review.md` (How to report, and the sign-off block below `<!-- signoff -->`, which
   `review.signoff` sends alone and which gets one attempt) gain the rubric table, the anchors, the
   score line format, the Harm floor rule and "judgement, not measurement". In this part they keep
   today's `Blocking:`/`Advisory:` labels and P0–P3 wording, so main stays consistent until BAR
   merges. Test (one): a review stub writes, on its first attempt, one finding with no score line;
   on the second, one finding scored `Gain 3, Work 2, Harm 1`, one Security finding scored
   `Harm 2`, and one titled with a migration under `Raise: Functional` scored `Harm 1`. Close
   prints all three, the second as `Harm 4 (floor: security)` and the third as
   `Harm 4 (floor: migration)`. A sign-off review stub's one scored finding is read and refused as
   a blocking sign-off issue. A read stub's note scored `Harm 1` that names a migration is saved in
   the read notes as Harm 4 with `(floor: migration)`.
2. `review.blocking` uses `score.bar` when a finding has scores, else today's priority rule; under
   `blocking_level == "P0"` only `block` counts. The sign-off gate in `review.run` (`review.py`
   near lines 599–611) selects findings with `score.bar` (`block` or `fix now`) in place of
   `SERIOUS`, unscored ones by priority as today. `worker._fix_round` takes the same list: the
   repair brief names every undismissed finding at the bar, at any priority, and drops the ones
   below it (unscored saved findings: P0/P1 as today). `story.passed` and `story.undisposed`: a
   scored note at the bar blocks; a scored note below it passes, and `forge read` writes
   `Disposition: keep - below the bar (follow-up)` or `(live with)` under it, so it needs no
   disposition by hand. `close._block` lists the review's below-bar findings under "Follow-ups" and
   "Lived with", each with its score line, inside the folded section. The templates' "What blocks
   the merge" section and the read's Blocking/Advisory rule say the bar decides; labels and
   priority stay only as Autoreview's field and for old notes. Test (one): a fix whose review has a
   P1 scored Gain 2, Work 1, Harm 1 and a P2 scored Gain 4, Work 4, Harm 2 reaches Ready, and its
   pull request lists both with scores. A P2 scored Gain 3, Work 1, Harm 1 blocks close, and the
   next `forge work` brief names it and not a below-bar P1 of the same review. A story read whose
   only note scores Gain 2 passes, and its notes show the automatic disposition. A sign-off review
   with a P1 scored Gain 2, Work 1, Harm 1 passes sign-off; one with a P2 scored Gain 3, Work 1,
   Harm 1 is refused as a blocking sign-off issue.
3. Carry-forward reads only what is already stored: the read notes file (every note, its score
   line and its disposition) and the saved review results in the item's state. Nothing new is
   written. Read rounds: `$dispositions` lists every disposed note, below-bar ones included, each
   with its scores (today only blocking ones); the later-round blocks drop "Previous advisory notes
   are recorded only" and say a settled note comes back only as `Disputed keep <n>: <new harm
   evidence>`. Reviews: a new `$accepted` block in `review.md` under How to report lists, as known
   and accepted, (a) for a task, the story's read notes with a `keep` or `defer` disposition, the
   automatic below-bar ones and an owner's accept; (b) this item's earlier below-bar findings with
   scores; (c) this item's owner-accepted findings (the `accepted` dismissals that `_rulings` skips
   today). `review.instructions` fills it. A repeat with the same file and title is already ignored
   (`review._settled`); extend that to below-bar findings of earlier rounds and to owner-accepted
   findings, which stay settled until a finding titled `Disputed keep <n>` names new harm evidence.
   Test (one): a story with a kept read note and a below-bar note: the task's review prompt (the
   Autoreview stub saves its argv) lists both as known and accepted; after the owner accepts a
   blocking finding, the next review's prompt lists it and a repeat of it is ignored; a second
   review round's prompt lists the first round's below-bar finding; a later read round's prompt
   lists the earlier below-bar note.
4. Close's three-round stop (`close.py` near lines 192 and 269, and `_three_blocked_reviews`) fires
   only when a finding at the bar repeats an earlier round's (same file and title), or when any
   open finding, at or below the bar, has Harm ≥ 3; otherwise the worker goes on as in rounds 1 and
   2. The read loop stop (`story._blocked_reads`, `read_loop`) fires on the third blocked round
   only when a note at the bar is a `Disputed keep`, or when any open note, at or below the bar,
   has Harm ≥ 3. The 30-minute default answer (from the
   stop-default-answer fix, review stops only) records narrow only when every open finding, at the
   bar or below it, has Harm 1 or 2; with any Harm ≥ 3 open it keeps waiting. Unscored saved
   results stop as today. Test (one): three blocked rounds with new Harm 1 findings each time go on
   to a fourth round; a third round with a new Harm 1 finding at the bar and an open Harm 3
   follow-up stops; with elapsed time
   past 30 minutes, a stop with only Harm 2 findings records narrow, and a stop with a Harm 2
   finding at the bar plus a Harm 3 follow-up stays stopped.
5. `score.table(rows)` renders the ranked table `# | Problem, for whom | Gain | Work | Harm |
   Proposed`, ranked by bar (block, fix now, follow-up, live with), then Harm and Gain descending,
   then Work ascending. "Problem, for whom" is `story.plain` of the note (from stop-question-plain);
   "Proposed" is the bar's outcome in words ("fix now", "fix this round", "follow-up fix", "live
   with"). It returns the table when every row has scores, else today's bullets; the call sites in
   `story.stop_question`, `story.read_question` and `close.stop_question` are SCORES' (see
   Stop-question call sites), so GUIDE changes only `score.table` and the guide.
   Guide (`src/forge/templates/skill.md`, in GUIDE's Scope): rewrite the close-stop paragraph near
   lines 1109–1114 (every in-boundary P0/P1 gets a fix round, "never a dismissal for being
   unnecessary, rare or low value") so the bar decides which findings get a fix round, and the
   review-loop and read-loop paragraphs near lines 1217–1235 ("Close holds the fourth review after
   three consecutive rounds blocked by serious findings, whatever files they were in") so they
   state item 4's stop rule. Add: the coordinator shows the same table in every update that lists
   notes or findings; it never re-scores a note and follows the bar's outcome; it settles reversible Harm 1 and 2 notes itself (a disposition or a
   dismissal, with the scores in its reason) and tells the owner after, in a line; it asks the
   owner only for Harm ≥ 3, new scope beyond the approved Done when, owner gates (approve, merge),
   or undoing an owner decision. Test (one): a stopped review and a stopped read each print the
   table ranked as above, through `forge close`, `forge read` and `forge next`; the guide synced
   into a new and an upgraded repo has the coordinator rule, and neither the "never a dismissal for
   being ... low value" sentence nor the "three consecutive rounds ... whatever files they were in"
   sentence.
6. README: a new section after "How it works", "How Forge weighs a note": the three scores, the
   bar table, and three worked examples: "close's default test selection breaks Go repos" (Gain 3,
   Work 4, Harm 2 → a follow-up fix, the merge goes on); a finding that a migration drops a column
   (Harm 4 → holds the merge); a wording note on a plan (Gain 1 → lived with). Plain English, no
   client names. Upgrade needs no code beyond SCORES' unscored rule and BAR's fallbacks. Test
   (one): on the adopted fixture with a blocked review saved by the earlier release (P1, no scores)
   and a blocked read saved before the upgrade (a `Blocking:` note, no scores), moved to this
   release: `forge close` still stops on the saved review's finding until a new round, and `forge
   next` still reports the read as not passed; after one new scored round each, the bar decides.
   The same test checks the README section names the three scores, the bar's rows and the three
   examples.

## Tasks

SCORES, BAR and README may add a paragraph to `src/forge/templates/skill.md` and regenerate
`.claude/skills/forge/` and `.codex/skills/forge/` with `forge sync`; GUIDE owns the guide's
rewrites and lists it in Scope. The host copies are left out of every Scope column so the parts run
in parallel. If they clash on the guide, the part closed second brings main in, keeps both changes
and regenerates the copies.

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| SCORES | Scores on every note | New `score.py` with `parse`, `normalise` (Harm floor on title and body), `bar`, the unscored rule and a `table` stub; `review._finding` and the reader-output step of `story.read` score and floor every finding and note; `story.stop_question`, `story.read_question` and `close.stop_question` pass scores to `score.table`; the rubric and score line in the cold-read, review and sign-off templates; existing tests' findings given a default score line | 1 | `src/forge/score.py`, `src/forge/review.py`, `src/forge/story.py`, `src/forge/close.py`, `src/forge/templates/cold-read.md`, `src/forge/templates/review.md` | `tests/test_score_notes.py`, `tests/test_close.py` | | no | |
| BAR | The bar decides | `review.blocking`, the sign-off gate in `review.run` and `worker._fix_round` follow the bar; light reviews ask for every priority and apply P0-only after scoring; `story.passed` and `undisposed` pass below-bar notes with an automatic disposition; `close._block` lists follow-ups and lived-with findings; the `$accepted` block and `_settled` carry settled and owner-accepted notes forward; the three-round stops and the 30-minute default judged by the bar | 2, 3, 4 | `src/forge/review.py`, `src/forge/worker.py`, `src/forge/story.py`, `src/forge/close.py`, `src/forge/templates/cold-read.md`, `src/forge/templates/review.md` | `tests/test_score_bar.py`, `tests/test_close_holds_after_three_blocked_reviews.py`, `tests/test_cold_read_blocking_notes.py`, `tests/test_aha_review.py`, `tests/test_reviews_use_repository_tool.py` | SCORES | no | |
| GUIDE | Ranked table and coordinator rule | `score.table` filled in, so every stop question shows the ranked table; the guide's close-stop and loop paragraphs rewritten to the bar, plus the table rule and the coordinator autonomy rule | 5 | `src/forge/score.py`, `src/forge/templates/skill.md` | `tests/test_score_table.py` | SCORES | yes | |
| README | README and upgrade | The README section with the three examples; the proof that saved unscored reads and reviews keep holding work back after an upgrade | 6 | `README.md` | `tests/test_score_upgrade.py` | BAR | no | |

New moving parts: none

## Notes

- Builds on two fixes in flight: stop-question-plain (GUIDE's table replaces its bullet list in
  `story.stop_question`) and stop-default-answer (BAR changes its 30-minute rule). Both merge
  before any part starts (SCORES pins the stop-question call sites, so it needs stop-question-plain too); if one hasn't, the part waits and says so.
- Replaces two fixes started but not built: value-effort-risk and accepted-notes-to-review. Close
  both branches without merging once this story is approved; their Done-when lines are items 3, 5
  and 6 here.
- BAR and GUIDE share no path: SCORES pins the `score.table` stub and its call sites, GUIDE
  changes only `score.py` and the guide, so they build in parallel after SCORES.
- SCORES and BAR both edit the two templates and `review.py`: SCORES adds the rubric and score
  line and keeps today's labels, and touches only `_finding` and the docstring; BAR changes what
  blocks, the later-round text, `blocking`, `instructions`, `_settled` and the light review's
  priority. Each merge leaves main consistent.
- Size: `story.py` is about 1,150 lines with stop-question-plain. The bar, floor and table live in
  the new `score.py` so `story.py` stays under 1,200; if it would cross, the part moves more note
  handling into `score.py`, never past the ceiling.
- Not now: tuning the bar by repo size; a board chart of value against work (a later board
  story).
- No client repo is named anywhere in this story's code, tests, texts or commits.
