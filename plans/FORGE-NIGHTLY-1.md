# Show a failed full test run under Needs you

1 part · Risks: none one-way · New moving parts: none

## What changes for you

- When the latest full test run on the main branch fails, the board shows it under Needs you. The row looks like the other rows there. When you click it, the run opens on GitHub. (Source: your decision, 11 Nov 2026)
- The next-step text (the list that `forge next` shows the agent) starts the first line about that run with "Needs you". (Source: your decision, 11 Nov 2026)
- Only the full test run that Forge knows counts: its own nightly run, or the workflow that the repo names for its full run. Other scheduled jobs never show under Needs you. They keep the lines that the next-step text shows for them today. A repo with no full test run shows nothing new. (Source: your decision, 11 Nov 2026)
- The row stays until a later full test run passes. A run that is still going or was cancelled does not remove it. Only a nightly run or a run that a person starts by hand counts as a full test run. Another run of the same workflow, for example a check on a pull request, does not remove the row. (Source: your decision, 11 Nov 2026; the last two sentences are the planner's choice)
- While a fix for the failure is in progress, the row says "Fix in progress". The row still shows. (Source: your decision, 11 Nov 2026)
- For every scheduled job, the next-step text also stops hiding a failure behind a newer run that is still going or was cancelled. (Source: the planner's choice, so that the board and the next-step text agree)
- When Forge cannot reach GitHub, it shows no row until it can read GitHub again, as the next-step text does today. (Source: the planner's choice)
- The agent still starts the fix for a failed run without asking you, as it does today. The guide that Forge ships says so. (Source: the planner's choice)
- New client repos get all of this at once. Existing client repos get the board row and the next-step text with the new release, and the new guide sentences after the usual guide update. Forge changes no app file and writes no setting. No model is called, so the model cost does not change. (Source: the planner's choice)

Design: none. The failed run is one more row in the board's existing Needs you list. The same row code draws it, with the same look. There is no new screen, style or layout.

## Why

A client team reported that a failed nightly test run was easy to miss. Today it shows only as a short note in the next-step text, and the board does not show it. On 11 Nov 2026 you decided that a failed full test run shows under Needs you, with a link to the run.

## Done when

1. **A failed latest full test run on the main branch shows under Needs you on the board, and a click on that row opens the run on GitHub.**
2. **The next-step text starts the first line about that run with "Needs you"; other scheduled jobs and repos with no full test run get no row and no such line.**
3. **The row stays until a later full test run passes; a running or cancelled run does not remove it, and a fix in progress changes only its words.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. The part reverts with its pull request. No data or migration changes.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Source: piece 3 of 3 that the owner split from the older plan for GitHub issue 1530. The owner's
decision of 11 Nov 2026 is settled; cite it, do not reopen it: a failed latest full test run on
the default branch shows under Needs you with its run link; the next-step text marks it; only
the full test run Forge knows (its own nightly run or the workflow the repo names), never other
scheduled jobs; the row stays until a later full run passes; a running or cancelled run does not
remove it; a fix in progress changes its words only; a repo with no full run shows nothing.

Story tests start with `STORY = "FORGE-NIGHTLY-1"`, use one test function per Done-when number
(`test_1` to `test_3`, unique across the story's files), run the `forge` command and never import
forge, and assert whole lines. Only `gh` is faked.

### What exists (evidence, on main at fe7caf4e9)

- `src/forge/board_facts.py:395` `failed_schedules(top)`. Line 404: `workflow =
  cfg.get("full_suite_workflow") or "forge.yml"`. Lines 409-416: two requests in parallel, the
  newest 100 `event=schedule` runs of all workflows on the default branch
  (`repos/{owner}/{repo}/actions/runs`), and the `event=workflow_dispatch` runs of `workflow`
  (`actions/workflows/<workflow>/runs`, lines 410-412). Lines 427-429 merge them and sort newest
  first by `created_at`. Lines 430-432 keep, per `workflow_id`, the newest run in any state
  (`latest.setdefault`). Line 450 reports it only when its `conclusion` is `failure`. Lines
  433-448: each failure becomes `{workflow, branch, event, file, jobs, tests}`, read from
  `gh run view <id> --log-failed` and cached per attempt for ever
  (`run-<id>-<attempt>-failure-cache`, `seconds=math.inf`). Line 454: the whole list is cached
  ten minutes as `schedule-cache`. The run's `html_url` and `created_at` are not kept.
- `src/forge/nextstep.py:436-453` `_failed_schedules`: a nested `clean` (lines 438-439), the
  alert key `(<clean(file)>)` (line 442), and three lines per failure: `The latest <kind>
  <workflow> (<file>) run on <branch> failed in: <jobs>.` (line 449), `Failing tests: ...`, and
  `Next: forge fix start "<why>" --done "<done>" --kind mechanical`, where why is `The <kind>
  <workflow> (<file>) run fails on <branch>`. `forge next` reads it in parallel (line 172).
  `claim` (lines 249-251) pins an alert's lines above a started, unmerged fix whose `why` holds
  the key (lines 326 and 348); the rest print at line 405. `nextstep.py` has 1,197 lines (limit
  1,200).
- `src/forge/board_facts.py:537` `team(top, history, items, maps, best, ...)`. Lines 592-602 give
  each fix row its `state` (`work_state`: a merged fix is `done`; a fix missing from `items`
  finished over seven days ago). Line 606 builds `waiting` from `needs_you` (lines 477-495:
  stories, parts and fixes only, sorted oldest first by `since`). Lines 609-611 count
  `len(waiting)` in `team.sentence`. Dropped and promoted fixes are already out of `best`
  (`src/forge/board.py:273-274`). `board.py` has 1,200 lines: do not touch it.
- Which full run Forge knows: `src/forge/prcheck.py:263` gives `forge.yml` its nightly and manual
  full-suite job only when `repo.test_place(cfg) == "ci"` (`src/forge/repo.py:648`) and
  `full_suite_workflow` is empty; `src/forge/fullrun.py:14-20` names the same two workflows.
  `forge.yml` also runs on `pull_request` and `pull_request_target`
  (`src/forge/prcheck.py:47-50`), and a repo's own `full_suite_workflow` may run on pushes too.
- The page: `src/forge/board_app/now.js:13` `VERB` (approval, worker question, merge; every other
  reason says Decide); line 94 keeps in the Me view only entries whose `id` is one of the
  viewer's items; lines 107-109 `open` opens the item drawer; lines 127-133 `ask` draws a Needs
  you row (`button.ask`, `ask-head`, `verb`, `key`, `ask-title`) with `Fix` or the story key in
  the `key` place.
- The pane: `src/forge/mod/hooks/summary.ts:181-184` shows a `team.needs_you` entry with an
  unknown id by its title and its reason in words (here `Failed run.`). No change needed.
- Guide text: `src/forge/templates/run-reference.md:119-129` lists the `team.needs_you` reasons
  and says "Ask the human about each Needs you item as `forge next` words it."
  `src/forge/templates/skill.md:2507-2509` tells the coordinator to start the fix for a failed
  scheduled run without asking; `skill.md:2199` says a failed full run appears in `forge next`.
  `forge sync` writes both files into `.claude/skills/forge/` and `.codex/skills/forge/`
  (`src/forge/story.py:100`).
- Tests that read these requests: `tests/test_testplace_fullrun.py:431-433` requires a
  `forge.yml/runs` call with `event=workflow_dispatch`;
  `tests/test_next_names_a_failed_scheduled_run.py:88-90` requires exactly one `actions/runs`
  call (its workflows are `forge-next-<n>.yml`, never the full run, so its lines do not change);
  `tests/test_repo_full_suite_workflow.py:98-125` covers a named `nightly.yml`. The stub `gh`
  (`tests/conftest.py:341`) answers every call that starts with the given arguments, so both
  per-workflow requests get the same answer in tests; runs must be merged by id.
- Both test fixtures are CI-test repos: a new repo from `forge init --actions yes` gets
  `test_place = "ci"` (`src/forge/init.py:235`), and
  `tests/fixtures/adopted-v1.2.2/client/forge.toml:8` has `checks = ["tests", "forge-pr-check"]`.
  So `forge.yml` is their full run.

### Settled (with the reason)

1. **The full run.** `board_facts.full_workflow(cfg) -> str | None`: `full_suite_workflow` when
   set, else `forge.yml` when `repo.test_place(cfg) == "ci"`, else `None`. A run is a full run
   when its file (the last part of `path`) is that workflow and its `event` is `schedule` or
   `workflow_dispatch`. Reason: the owner's decision names only these two; the event rule keeps a
   pull request or push run of the same workflow from clearing the row (old read note 17).
2. **Its own runs.** `failed_schedules` adds a third parallel request: `actions/workflows/
   <workflow>/runs` with `event=schedule`, beside the existing `event=workflow_dispatch` one,
   which stays as it is (so `test_testplace_fullrun.py:433` keeps passing; old read note 19).
   Merge the three lists by run id before sorting. Reason: other frequent scheduled jobs can no
   longer push the full run's newest result out of the shared 100 (old read note 12). One request
   per event, because GitHub's `event` filter takes one value.
3. **The newest finished run decides.** Per `workflow_id`, skip runs whose `conclusion` is not
   `success` or `failure` before `latest.setdefault`. A run in progress (`null`), cancelled,
   skipped or timed out neither adds nor removes a failure. This also applies to the other
   scheduled workflows in `forge next` (old read note 7).
4. **New fields.** Each failure gets `url` (the run's `html_url`), `created_at` and `full_run`,
   added after the per-attempt cache returns (outside `read`), because those cached entries never
   expire. Rename the ten-minute cache from `schedule-cache` to `failed-runs-cache`, so a list
   cached by an earlier release, which lacks these fields, is never read (old read note 16). No
   test reads either cache.
5. **Shared `clean`.** Move the nested `clean` of `nextstep._failed_schedules` to
   `board_facts.clean` (module level) and call it from nextstep. The board builds the same key
   `(<clean(file)>)` that `claim` matches, so a file such as `nightly@2am.yml` still matches
   (old read note 15). This also frees two lines in `nextstep.py`.
6. **The `forge next` mark.** In `nextstep._failed_schedules`, the first line of an alert whose
   run has `full_run` starts with `Needs you: `, whether a fix claims it or not. Its other lines,
   the fix command and `claim` do not change. `nextstep.py` must stay at 1,200 lines or fewer.
7. **The board entry.** In `team`, only when `full_workflow(cfg)` is not `None` (so a repo with no
   full run makes no extra GitHub call), call `failed_schedules(top)` and add one entry per
   `full_run` failure to `waiting` before line 609 counts it, then sort all entries oldest first
   as `needs_you` does:
   `{"id": "run:<file>", "kind": "run", "title": "The latest full test run on <branch> failed",
   "reason": "failed run", "detail": "<jobs joined with '; '>" or None, "since": <created_at>,
   "waited_seconds": <now - created_at, or None>, "url": <html_url>, "fixing": <bool>}`.
   `fixing` is true when a fix in `best` whose board row `state` is not `done` has a `why` that
   holds the key `(<clean(file)>)`. A fix never hides the entry (old read note 8). Read the
   config with the same `repo.Refused` guard that `failed_schedules` uses.
8. **The row on the page** (`now.js`). Add `'failed run': 'Fix'` to `VERB`. In `ask`, for
   `kind === 'run'` the `key` place shows `Fix in progress` when `entry.fixing`, else
   `Full test run`; the title stays, so the short words fit the one-line row (old read note 14).
   A row with a `url` opens it with `window.open(entry.url, '_blank', 'noopener')` in place of
   the drawer. In `facts`, the Me view also keeps `kind === 'run'` entries (they have no owner).
   Same markup and classes, no CSS change, no new screen or layout, no command on the page. A
   change that needs new styling stops and goes back to the coordinator for a design first.
9. **Guide text, exact words.**
   - `run-reference.md`, in the reasons list after `blocked plan`: "`failed run` (the latest full
     test run on the default branch failed: `kind` is `run`, `id` is `run:<workflow file>`,
     `url` opens the run on GitHub, and `fixing` is true while an open fix names that run)".
     After "Ask the human about each Needs you item as `forge next` words it.", add: "For a
     `failed run`, start the fix that `forge next` names; do not ask the human."
   - `skill.md`, at the end of the paragraph at line 2507: "For the full test run Forge knows
     (`full_suite_workflow`, or `forge.yml` in a CI-test repo), that first line starts with
     `Needs you:`, and the board lists the run under Needs you until a later scheduled or manual
     full run passes. The mark is for the owner; still start the fix without asking."
   - Run `forge sync` so `.claude/skills/forge/` and `.codex/skills/forge/` carry both.

### Done-when details

1. **The row and its click.** New file `tests/test_failed_full_run_row_opens_run.py`,
   `test_1_a_failed_full_test_run_shows_under_needs_you_and_opens_the_run`, on the `client`
   fixture of `tests/test_board_server.py` (parameters `new` and `adopted-v1.2.2`, so an
   earlier-adopted repo is covered), `live` for the real `forge board` page, and a `BROWSER`
   script in real Chrome run the way `tests/test_board_now_screen.py::look` runs it. The stub
   `gh` answers `repos/{owner}/{repo}/actions/runs` with one failed `forge.yml` scheduled run on
   `main` (with `html_url` `https://github.com/acme/shop/actions/runs/41` and a `created_at`),
   `actions/workflows/forge.yml/runs` with no runs, and `run view 41 --log-failed` with one
   failed job.
   - The snapshot's `team.needs_you` holds the entry of Settled 7 with `title` "The latest full
     test run on main failed", `reason` "failed run", `kind` "run", the given `url` and
     `fixing` false; `team.sentence` counts it.
   - On the page, the Needs you strip shows a row with the words `Fix`, `Full test run` and
     "The latest full test run on main failed". A click opens a new page at the run's `url`
     (route `https://github.com/**` to a stub reply so the test stays offline) and opens no
     drawer. In the Me view the same row shows.
2. **The mark and what does not show.** New file `tests/test_failed_full_run_needs_you.py`,
   `test_2_next_marks_only_the_full_test_run`, parameters `new` (`_fresh_client` of
   `tests/test_setup.py`) and `earlier adopted` (the v1.2.2 fixture upgraded and synced as
   `tests/test_next_names_a_failed_scheduled_run.py::test_1` builds it). Each step moves
   `FORGE_NOW` past the ten-minute cache.
   - A failed latest `forge.yml` scheduled run: `forge next` prints exactly
     `Needs you: The latest scheduled forge (forge.yml) run on main failed in: <job>.`, then the
     unchanged `Failing tests:` and `Next: forge fix start ...` lines.
   - A failed scheduled run of another workflow (`backup.yml`): its lines exactly as today, with
     no `Needs you:`; `forge board --json` has no `run` entry.
   - `test_place = "local"` with no `full_suite_workflow`, and the same failed `forge.yml` run in
     the fake: no `Needs you:` line and no `run` entry.
   - `full_suite_workflow = "nightly.yml"` and a failed manual `nightly.yml` run: the line
     `Needs you: The latest manual <name> (nightly.yml) run on main failed in: <job>.` and one
     `run` entry with id `run:nightly.yml`.
3. **When the row goes, and the fix words.** Same file,
   `test_3_the_row_stays_until_a_later_full_run_passes`, both parameters. In order, each with a
   later `FORGE_NOW`:
   - a failed `forge.yml` scheduled run, then a newer run in progress (`conclusion` null), then a
     newer cancelled run, then a newer passing `pull_request` run of `forge.yml` on `main`: the
     entry and the `Needs you:` line stay each time;
   - `forge fix start` with the suggested why: the entry stays with `fixing` true and the same
     title, and `forge next` still prints the `Needs you:` line above the fix's own lines;
   - that fix recorded as merged on `main` (its state file with `status` `merged`, pushed the way
     `tests/test_board_now_screen.py::merged_fixes` does), then a newer failed scheduled run: the
     entry stays with `fixing` false;
   - a newer passing scheduled run: no `run` entry and no `Needs you:` line.

### New and existing repos

- **New repos** (`forge init`): the board row, the `forge next` mark and the guide text at once.
- **Existing repos** (upgrade, then `forge sync`): the row and the mark with the new release; the
  guide sentences after `forge sync`. Nothing in the app or in `forge.toml` changes. The renamed
  cache means a list cached by the earlier release is not reused.

## Tasks

<!-- One row per task. Covers: the Done-when numbers it delivers, at most three. Scope: the paths
it may change. Before writing each Scope, search the code for the files the task needs. The plan
check refuses two tasks whose Scope paths have the same prefix up to the first wildcard, unless
one waits for the other through After, directly or through another task; it names both tasks.
Paths with a segment named `tests`, `test`, `__tests__` or `spec` do not cause Scope overlaps
and can be shared without an After link. Explicit After links still apply.
When tasks need the same production file, put it in the first task's Scope with the shared names and stubs;
tasks that need them wait for that task through After and then own only their files. Keep a file
that a script can make at build time out of the repo and out of every Scope; when the repo keeps such
a file on purpose, give its change to one part that the others wait for. Tests: the
tests it adds or changes. After: the tasks it waits for. When two tasks share a function, field,
file format or command, the first task pins it: it commits the shared names and stubs plus one
test that crosses both sides, and the tasks that use it list it under After. Split tasks so each
owns its files; shared lines (command table, guide list, registry) go to one task or a small last
wiring task; After only when a task needs another task's code. The
Developer column is optional: the lead fills or changes a GitHub username here, below For the
builders, without another approval. Leave it blank for an unassigned part. Forge next uses
the caller's GitHub login; another developer may start it with a warning. Existing tables
without Developer still work. The moving-parts line stays last: "none", or each new dependency, service, datastore,
queue, background job or abstraction layer, with the Done-when item that needs it. -->

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| NIGHTLY | A failed full test run shows under Needs you | `full_workflow`; the full run's own scheduled-runs request; the newest finished run decides; `url`, `created_at` and `full_run` on each failure; the renamed cache; `clean` shared from `board_facts`; the `Needs you: ` mark in `forge next`; one board entry per failed full run, with `fixing`; the row's words and its click in `now.js`; the guide sentences. | 1, 2, 3 | `src/forge/board_facts.py`, `src/forge/nextstep.py`, `src/forge/board_app/now.js`, `src/forge/templates/run-reference.md`, `src/forge/templates/skill.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md`, `.claude/skills/forge/run-reference.md`, `.codex/skills/forge/run-reference.md`, `tests/test_failed_full_run_row_opens_run.py`, `tests/test_failed_full_run_needs_you.py` | `tests/test_failed_full_run_row_opens_run.py::test_1_a_failed_full_test_run_shows_under_needs_you_and_opens_the_run` (new); `tests/test_failed_full_run_needs_you.py::test_2_next_marks_only_the_full_test_run` and `::test_3_the_row_stays_until_a_later_full_run_passes` (new) | | yes | |

The four synced guide copies are rewritten by `forge sync`, not by hand. Run
`tests/test_testplace_fullrun.py`, `tests/test_repo_full_suite_workflow.py` and
`tests/test_next_names_a_failed_scheduled_run.py` as related tests; none of them should need a
change.

New moving parts: none

## Notes

- **Scores (F x H >= 2 x C).** Needs you entry and its click: F 1 to 2, H 2, C 2; close, kept
  because the owner decided it. Newest finished run decides, and the full run's own request: F 2
  (a run is in progress for an hour each night; frequent jobs fill the shared list), H 2 (a
  failure disappears), C 1; 4 >= 2, kept. Keeping the last answer while GitHub cannot be read:
  F 1, H 1, C 1; 1 < 2, left out (the owner's section says so). A failed local full run (repos
  with no CI) under Needs you: F 1, H 2, C 2; 2 < 4, left out; that run prints its fix line when
  it fails.
- **Planner's choices, for the owner to confirm at approval.**
  1. Only scheduled and manual runs of the full workflow count, so a passing pull request or push
     run of that workflow does not remove the row.
  2. The newest finished run decides for every scheduled job in `forge next`, not only the full
     run.
  3. While GitHub cannot be read, no row shows.
  4. The coordinator still starts the fix without asking; the guide says so.
- **Read notes from the older plan, settled here.** 6 (only the full run), 7 (newest finished
  run), 8 (a merged fix never hides a new failure), 9 (the click is tested in Chrome), 10 (one
  test number per item), 12 (the full run's own request), 14 (short words in the key place),
  15 (shared `clean`), 16 (renamed cache), 17 (only scheduled and manual runs count) and 19 (the
  manual request stays, so `test_testplace_fullrun.py` needs no change).
- **No new command or setting.** The entry reuses `team.needs_you`, `failed_schedules` and the
  existing row code.
- **Files near their limits.** `src/forge/nextstep.py` has 1,197 lines; moving `clean` out frees
  two. `src/forge/board.py` has 1,200 lines and is not touched. `src/forge/board_facts.py` has
  617.
- **Guides in flight.** The two other pieces split from the same older plan also edit
  `src/forge/templates/skill.md` and its synced copies. Forge makes overlapping parts wait, so
  this part may wait for one of them; the edits are in different paragraphs.
- **Not verified.** Whether GitHub reports a run whose job hit its time limit as `failure` or as
  `timed_out` (only `failure` makes a row, as today). Whether a `pull_request_target` run of
  `forge.yml` can report `main` as its branch (the event rule covers it either way).
- No client repo or company is named in this story's code, tests, texts or commits.
