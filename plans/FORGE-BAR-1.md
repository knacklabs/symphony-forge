# Clients choose which added-work review notes hold their work

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- You can set a minimum Gain for review findings that ask for added work: another check, a
  retry, a guard or a flag for a rarer case. A finding of this type with a lower Gain does not
  stop the merge. Forge keeps it in Known issues, with its scores and the reason.
- You can list kinds of work that a change must not miss, such as legal must-haves or safety
  steps. A review finding of one of these kinds stops the merge at any score. The worker cannot
  decline it. Only you can accept it.
- Security, data loss and migration findings, and findings against the app's constitution or
  Forge's database, module tables and shadcn rules, still stop the merge, whatever the minimum
  is.
- The pull request shows the Gain, Work and Harm scores of each review finding, also of a
  finding that stops the merge.
- You tell your agent which minimum and which kinds you want. The agent writes them in
  forge.toml in a fix. They apply after that fix merges.
- New repos and existing repos keep today's review bar until you set these. An upgrade adds no
  setting.
- Plan reads and the prototype sign-off review keep today's bar.

Design: none (no screens; it changes how close holds review findings and what the pull request shows)

## Why

Review holds work by one fixed bar. A finding that asks for a retry or a guard for a rarer case
can stop a change that the owner wants to ship. A legal must-have with a low score can pass.
A client owner asked to set this bar for their own repo. Forge already scores each finding on
Gain, Work and Harm and keeps findings below the bar as follow-ups, so the two settings use these
scores and this record.

## Done when

1. **In a repo whose forge.toml sets `added_work_min_gain` to 4 or 5, a review finding that asks for added work and has a lower Gain does not block. Close keeps it in Known issues with its scores and the reason. A finding with Harm 4 or more, Gain 5, or a score that Forge raises by its own rules still blocks.**
2. **In a repo whose forge.toml lists kinds in `always_block`, a review finding of one of those kinds blocks the merge at any score, also when it is marked as a rare case or the review is light. The worker cannot decline it.**
3. **Close and the pull request show the Gain, Work and Harm scores of each review finding beside its reason, a blocking finding too.**
4. **A repo that sets neither setting keeps today's review bar exactly: a new repo from `forge init`, and an existing repo after upgrade and `forge sync`, which gets no new forge.toml line. A value of `added_work_min_gain` other than 3, 4 or 5 stops Forge with a message that names the allowed values.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request.

Trade-off: the reviewer marks added work and the must-not-miss kinds. A finding that it does not
mark follows today's bar.

Trade-off: Forge reads the two settings from forge.toml on the default branch, as it reads the
review rules. A fix that changes them gets today's bar in its own review.

Trade-off: plan reads and the prototype sign-off review keep today's bar. A plan or a prototype
that misses a legal must-have is held only by the reader's or reviewer's own scores.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-BAR-1"`. Tests run the forge command and never
import forge. Follow `tests/test_database_review.py`: `_client_repo` and `_scored` from
`tests/test_score_notes.py` (new client from `forge init`, or `tests/fixtures/adopted-v1.2.2/client`
moved to this release with `forge sync`), `env.reviews(blocked(...))` for the faked Autoreview
report, `env.close(item)` and `env.prompt()`. To set a setting, append it to `forge.toml` on
`main` after `_client_repo`, commit with the hooks off as `_client_repo` does, and push, so
`origin/main` carries it.

### How it works (pinned by BARRULES)

- **The settings.** Two new top-level keys in `src/forge/repo.py`: `KEYS` gets
  `"added_work_min_gain": int` and `"always_block": list`; `DEFAULTS` gets
  `"added_work_min_gain": 3` and `"always_block": []`. `_config_problem` adds one check:
  `added_work_min_gain` not in 3, 4, 5 gives `added_work_min_gain must be 3, 4 or 5`, so the
  refusal reads `forge.toml is not usable: added_work_min_gain must be 3, 4 or 5.` The existing
  list check covers `always_block`. Value 3 is today's bar: no Gain 1 or 2 finding holds today,
  and Gain 3 holds only with Harm 3 and Work 1 or 2.
- **Which forge.toml.** `review.run` and `review.bound_review` read both keys from
  `repo.default_config(top)`, the default branch's forge.toml, as `story.agents_section` reads
  the review rules from the default branch.
- **The added-work mark.** The reviewer adds a body line `Adds work: <what it adds>`. Match it
  in `src/forge/score.py` with `ADDS = re.compile(r"^[ \t]*Adds work:[ \t]*\S", re.I | re.M)`,
  beside `RARE`.
- **The must-not-miss mark.** The reviewer titles the finding `Must: <kind>: <what is missing>`.
  Match `^(?:Not fixed:\s*)*Must:\s*([^:]+):` on the title (after the existing `[P1]` strip), and
  compare the kind, trimmed and case-folded, with the case-folded `always_block` entries. A
  `Must:` title whose kind is not listed is an ordinary finding.
- **The classification** goes in `review.bound_review`, where Forge already keeps a `Case: rare`
  finding as a follow-up. It reuses the two records that exist; it adds no field:
  - A listed `Must:` finding gets `required_done_when = True` and `continue`s, as an approved
    `Not done` does today. Put it before the `finding.pop("required_done_when", False)` line.
    This already makes `review.blocking`, `score.remember` (outcome `open`), the light review,
    the `known:` dismissal clean-up and `review.declines` (which skips `required_done_when`)
    treat it as blocking at any score. The round-limit stop still lets the owner accept it.
  - A finding with an `Adds work:` line whose `score.bar(score.of(finding))` is `fix now`, whose
    score line has no `(floor:` mark, and whose Gain is below `added_work_min_gain` gets the
    follow-up reason `Adds work below this repo's minimum Gain <n>`, in the same `elif` chain as
    the rare case. A `block` outcome (Harm 4 or more, Gain 5) and every floored finding
    (`score.normalise` marks the line for security, data loss, migration, constitution, shadcn,
    module tables and database; the last four have Gain 4 and Work 2, so they are `fix now` and
    would fall at minimum 5 without this check) are never changed.
  - When no reason applies now and the finding's saved `follow_up` starts with
    `Adds work below this repo's minimum Gain`, remove that `follow_up`, so a saved finding holds
    again after the owner lowers or removes the minimum. Other saved reasons (split, decline,
    rare) stay as they are. In the same step, also remove a carried `known:` dismissal that came
    from that added-work reason (the repair-review path in `review.py` turns a repeated deferred
    finding into one), as the cleanup already does for `required_done_when`. `score.holds`,
    `score.remember`, `known_issues._rows`, close's `Does not block:` line and the pull
    request's follow-up list then read it as they read a rare case today.
  - Put the two matches in one small function in `src/forge/score.py` (for example
    `repo_bar(title, body, scores, min_gain, kinds)` that returns `"must"`, a follow-up reason or
    `""`), so `src/forge/review.py` (1,197 lines today) stays at 1,200 lines or fewer. If it
    still goes over, fold the review-rules and constitution appends in `run` into one loop with
    the two new blocks.
- **The reviewer prompt.** Two new blocks in `src/forge/templates/review.md`, each between its
  own marker and the next `<!-- `, as `<!-- constitution -->` is. `review.run` appends a block
  only when its setting differs from the default, so a repo with neither gets the same prompt as
  today. The light review gets them by the same `run` path. A sign-off review (`signoff_prompt`
  set) gets neither block: `review.py` calls `bound_review` only for reviews without a sign-off
  prompt, so sign-off keeps today's bar for both prompt and classification.
  - `<!-- added-work -->`, heading `## Added work`, with `$min_gain`: "When a finding asks for
    code beyond the fix of a broken path, such as another check, a retry, a guard or a flag for a
    rarer case, add the line `Adds work: <what it adds>` to its body after the score line. This
    repo keeps such a finding as a follow-up when its Gain is below $min_gain, unless it scores
    Harm 4 or more or Gain 5."
  - `<!-- always-block -->`, heading `## Kinds a change must not miss`, with `$kinds` (the list
    joined with `, `): "This repo lists kinds of work that a change must not miss: $kinds. When
    the change misses one, report a P1 finding titled `Must: <kind>: <what is missing>`, with the
    kind as listed, and score it as usual. Forge holds such a finding at any score. Use the
    `Must:` title for no other finding."
- **Guide and brief.**
  - `src/forge/templates/skill.md`, section `## Closing`, after the paragraph that has
    ``A `Case: rare` finding never blocks.``: "The owner can set two review settings in
    forge.toml. `added_work_min_gain` (3, 4 or 5; 3 is the default and today's bar) keeps a
    finding with an `Adds work:` line and a lower Gain as a follow-up, unless it scores Harm 4 or
    more or Gain 5, or Forge raised its score by a floor. The prototype sign-off review and plan
    reads keep today's bar. `always_block` lists kinds, such as legal or safety: a finding titled
    `Must: <kind>:` with a listed kind blocks at any score, and the worker cannot decline it.
    Close reads both from the default branch. Ask the owner before you change them, as for every
    setting."
  - `src/forge/templates/brief.md`, after the line that ends `with its Gain, Work and Harm
    scores.`: "In a repo with an `always_block` setting, a `Must: <kind>:` finding blocks at any
    score and you cannot decline it; fix it or name the line that proves it wrong."
  - `forge sync` rewrites `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`.

### Done-when details

1. Added work below the minimum (BARRULES).
   - Test: `tests/test_review_bar.py::test_1_added_work_below_the_minimum_gain_is_a_follow_up`,
     parametrised `new-client` and `adopted-v1.2.2`. Set `added_work_min_gain = 5`. The review
     gives four P1 findings, each with an `Adds work:` line except the second:
     `Retry the upload` scored `Gain 4, Work 2, Harm 1`; `Upload drops the file name` scored
     `Gain 4, Work 2, Harm 1` with no mark; `Check the upload token` scored
     `Gain 3, Work 2, Harm 1` under `Raise: Security` (the floor makes it Harm 4); and
     `Database: Upload.size` scored `Gain 2, Work 3, Harm 1` (the floor makes it Gain 4, Work 2).
     Close exits 1 with the last three open, and lists the first with
     `Does not block: Adds work below this repo's minimum Gain 5.` and its score line. The
     prompt has the `## Added work` block with `5`. Then remove the key from forge.toml on
     `main`, push, and run close again with no new commit: `Retry the upload` is open again.
2. Kinds a change must not miss (BARRULES).
   - Test: `tests/test_review_bar.py::test_2_a_listed_kind_blocks_at_any_score`, parametrised
     `new-client` and `adopted-v1.2.2`. Set `always_block = ["legal"]`. The review gives
     `Must: Legal: the cookie notice is missing` scored `Gain 1, Work 1, Harm 1` with
     `Case: rare - one country`, and `Must: tone: a softer error` scored the same. Close exits 1
     with the legal finding open and the tone finding not blocking. A worker commit with
     `Declined: Must: Legal: the cookie notice is missing (app.py): not worth the code - small`
     leaves it open on the next close. The prompt has the `## Kinds a change must not miss` block
     with `legal`.
   - The light review needs no test of its own: `review.blocking` reads `required_done_when`
     before the level, and the approved `Not done` tests already prove that path.
3. Scores on every finding (BARSCORES).
   - In `close._block`, a blocking finding's line gets `; Gain <g>, Work <w>, Harm <h>` after
     `blocks the merge`, when it has scores. The line goes to `blocking` by the blocking
     condition, not by a compare of the note text with `"blocks the merge"`, as it does today.
   - A follow-up line shows its `follow_up` reason before its scores:
     `: <reason>; Gain <g>, Work <w>, Harm <h>`. Today `line or finding.get("follow_up", "")`
     picks the score text first and drops the reason; take the reason first and let the existing
     `note += f"; {line}"` add the scores. Lived-with lines have no reason and stay as they are.
     Close's own terminal list already prints each finding's reason and its body with the score
     line.
   - Test: `tests/test_review_finding_scores.py::test_3_every_finding_shows_its_scores`,
     parametrised `new-client` and `adopted-v1.2.2`: a blocking P1 scored `Gain 4, Work 2,
     Harm 1`, a P1 scored `Gain 4, Work 2, Harm 1` with `Case: rare - one browser`, and a P2
     scored `Gain 2, Work 1, Harm 1`. Close's output has the three score lines, and the pull
     request body has `: blocks the merge; Gain 4, Work 2, Harm 1`,
     `: Rare case outside normal use; Gain 4, Work 2, Harm 1` and the lived-with line with its
     scores. The rare case stands in for every follow-up reason, so this part needs nothing
     from BARRULES.
   - Change the exact expected line in
     `tests/test_review_block_reads_clean_or_lists_blockers.py::test_2` to end in
     `blocks the merge; Gain 4, Work 2, Harm 1`. Other tests match `blocks the merge` and the
     follow-up titles and scores as a part of the line and keep passing.
4. Defaults keep today's bar (BARRULES).
   - Test: `tests/test_review_bar.py::test_4_no_setting_keeps_todays_bar`, parametrised
     `new-client` and `adopted-v1.2.2`, with neither key set: the `Adds work:` finding scored
     `Gain 3, Work 2, Harm 3` blocks, the `Must: legal:` finding scored `Gain 1, Work 1, Harm 1`
     does not block, the prompt has neither new heading, the repo's forge.toml has neither key
     after `forge sync`, and the synced `.codex/skills/forge/SKILL.md` has the new Closing
     paragraph. Then `added_work_min_gain = 2` in forge.toml makes `forge next` exit 1 with
     `forge.toml is not usable: added_work_min_gain must be 3, 4 or 5.`
   - Existing tests on the bar (`tests/test_score_notes.py`, `tests/test_two_round_limit.py`,
     `tests/test_close_explains_findings_and_requires_done_when.py`) keep passing unchanged.

### New and existing repos

- **New repos** (`forge init`): forge.toml gets no new line; both keys have their defaults, so
  the bar is today's. The guide paragraph and the brief sentence arrive with init. The owner's
  agent adds a key in a fix when the owner asks.
- **Existing repos** (on upgrade to this release, after `forge sync`): forge.toml does not
  change, so the bar is today's. The guide paragraph arrives with sync and the brief sentence
  with the release. Tested on the adopted earlier-release fixture in items 1 to 4.

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
| BARRULES | The added-work minimum and the kinds a change must not miss | The two forge.toml keys and their check, the `Adds work:` and `Must:` matches, the classification in `bound_review`, the two reviewer prompt blocks, the guide paragraph and the brief sentence, on new and existing repos | 1, 2, 4 | `src/forge/repo.py`, `src/forge/score.py`, `src/forge/review.py`, `src/forge/templates/review.md`, `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_review_bar.py` (new) | `tests/test_review_bar.py` (`test_1`, `test_2`, `test_4`) | | no | |
| BARSCORES | Scores and reasons on every finding in the pull request | The score line on each blocking finding, and the reason before the scores on each follow-up, in the pull request's review block | 3 | `src/forge/close.py` (`_block` only), `tests/test_review_finding_scores.py` (new), `tests/test_review_block_reads_clean_or_lists_blockers.py` | `tests/test_review_finding_scores.py::test_3` (new); the changed expected line in `test_review_block_reads_clean_or_lists_blockers.py::test_2` | | no | |

The two parts share no file and no name, so they can run at the same time.

New moving parts: none

## Notes

- Owner decisions (26 Oct 2026, settled): use the existing Gain and Work scores, with no new
  score such as how often a case happens; a repo sets the minimum Gain for a finding that adds
  work, and a list of kinds that always block; the defaults keep today's bar exactly, for new
  repos and for existing repos on upgrade.
- Planner choices the owner did not make: (1) the reviewer marks added work with a body line
  `Adds work: <what>` and a must-not-miss kind with the title `Must: <kind>: <gap>`, beside the
  existing `Case: rare` and `Constitution:` forms; (2) the minimum changes only an unfloored
  finding that would be `fix now`: Harm 4 or more, Gain 5 and every floor still block, so the
  allowed values are 3 (today), 4 and 5, and a Gain 1 or 2 finding stays lived with, as today;
  (3) a listed `Must:` finding reuses the hold that an approved
  `Not done` gets, so it blocks also when marked rare or in a light review, and the worker cannot
  decline it; (4) both settings come from the default branch, as the review rules do; (5) plan
  reads and the prototype sign-off review keep today's bar; (6) the prompt blocks appear only when a setting is set, so a repo with
  neither gets today's prompt.
