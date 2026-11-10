# List prototype gaps after sign-off and close each one before production

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- After a customer signs off a prototype, the next-step view and the board show a short list headed "Before production". Forge builds the list itself from what it already knows. It makes no model call and saves no new file or record. (Source: your working choice, 10 Nov 2026; you confirm it when you approve this story)
- The list has up to three lines. One line says that sample data is still on, so the app has no back end, no tests and no CI. One line names the parts that were built with only the light review. One line names the files that carry the "Demo only" label.
- Each line gets one normal change, started with the usual start step. A normal change has the full review, and its tests follow the repo's settings. The sample-data line comes first. Its change turns sample data off and sets the test command and checks, so every later change runs tests.
- The whole list stays on screen while a change for one of its lines is in progress, so no open line is hidden.
- A line leaves the list on its own when its fact changes: sample data is turned off, the "Demo only" labels are gone, or later changes name every light-reviewed part.
- Forge cannot see when a person presses Promote on the deploy platform. So Forge cannot hold the first production release, and it refuses nothing. The list stays visible until it is empty. The guide tells the agent not to promote while a line is open, unless you accept the rest.
- A new client repo gets all of this from Forge itself, and the guide text from `forge init`. An existing client repo gets the list the day it moves to the new release, with no migration and no file change. A repo that is still marked as a prototype and already has an accepted sign-off sees its own gaps at once. A repo marked as live shows no list. An existing repo gets the guide text with `forge sync`. (Source: the Forge review rules)

Design: none (the list reuses the board's existing sign-off block and its style; no new screen)

## Why

A prototype that signs off with sample data, no tests and only the light review is not ready for real use. Today the gaps sit in a static checklist and in review notes. Nothing shows them as open work after the customer says yes, so a prototype can go to production with its gaps unseen. You chose to keep the fast sign-off and to list the gaps afterwards, not to add a full review before sign-off.

## Done when

1. **While sample data is still on after sign-off, the list shows it as an open gap, and the line goes away when sample data is turned off, also when that change merged from another checkout.**
2. **The list names the files that carry the "Demo only" label and the parts that were built with only the light review. Each line goes away when its fact changes: the labels are gone, or later changes name the parts.**
3. **When more than one gap is open, the list shows all of them together, in a fixed order, and keeps showing them while a change for one of them is in progress.**
4. **The guide tells the agent to start one normal change for each line and not to promote while a line is open, and it says plainly that Forge cannot see the release and refuses nothing.**

## Risks

Risks: none one-way. Each part reverts with its pull request. No migration, no data change, no app file changes.

Trade-offs, in plain words:
- The list shows only what Forge can see. It cannot see a missing back end, except through the sample-data setting, and it cannot see a feature that nobody labelled "Demo only". The gap check at sign-off and the reviews of the build changes are the guards for those.
- A part leaves the light-review line only when a later change names it in its text. If the agent forgets the names, the line stays. That costs one more look, and nothing blocks.
- The light-review line can also name a small documentation change that was started while the prototype was unsigned. Forge cannot tell it from a code change without a new record.
- Forge does not hold the first production release. Only the guide and the visible list guard it.

Model cost: none for the list. It uses git facts and the settings. The changes that the lines start cost what any normal change costs.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-PRODGAP-1"`. Tests run the forge command and never import forge. Test numbers 1 to 4 follow the Done-when items; 5 is the light-review line (Done-when 2, second half). Reuse the setups of `tests/test_sample_checklist.py` (`brief`, the board read through `forge board --json` and its `signoff` key), `tests/test_journey_next.py` (`_publish`, to put fixture commits on main) and `tests/test_proto_signoff.py` (the earlier-release fixture copy). Only GitHub and the review tools are faked. Fixtures reach the default branch by a push to the remote from a second clone or worktree, never by a commit in the checkout that the command reads (see Settled 1).

### What exists (evidence)

- Sign-off and the sample-data switch are built (FORGE-SAMPLE-1 and its fix). `repo.sample_data(top, cfg, ref)` in `src/forge/repo.py` is true only for a client repo whose `forge.toml` has `stage = "prototype"` and `sample_data = true`. With `cfg=None` it reads `forge.toml` from `ref`; with a `cfg` it ignores `ref`. A sign-off record's old `sample_data: true` line does not turn it on. It stays true after sign-off until a person writes `sample_data = false`.
- After an accepted sign-off the repo is no longer a prototype for `repo.is_prototype(top, cfg, refs)` (it looks for an accepted record in the given refs, by default the checkout and the default branch), while `cfg["stage"]` stays `prototype`. So "signed off" is `cfg["repo"] == "client"`, `cfg["stage"] == "prototype"` and not `repo.is_prototype(top, cfg, (landed,))`.
- Merged work lands on the remote default branch, not in the main checkout. `merge.py` runs `git fetch origin <default>` and does not update the main checkout, and `story.landed_ref(top)` returns `origin/<default>` as last fetched. The board and `journey.step_line` already read landed facts. `nextstep.signoff` reads its brief and settings from the checkout.
- The earlier-release fixture (`tests/fixtures/adopted-v1.2.2/client/forge.toml`) has `stage = "live"`. A live repo never had sample mode or the prototype allowance. An earlier-adopted prototype is such a copy with `stage = "prototype"` written, as `tests/test_proto_next.py` and `tests/test_sample_checklist.py` do.
- What `forge next` shows after sign-off today: `journey.step_line` in `src/forge/journey.py` names "Step 5 of 7: set up tests" while `repo.sample_data` is true. Nothing lists the other gaps.
- The one gap check before the demo is `review.md` block `<!-- sample-signoff -->`, run by `records._signoff_review(..., sample_data=True)`. It runs once, before sign-off, and sends its non-P0 findings to the item's Known issues. It checks the demo, not production gaps. This story does not change it.
- The checklist shape already exists. `nextstep.signoff(top, cfg)` returns `{"line": str, "open": [{"item", "say"}]}`. `nextstep._report` prints the line, and prints each row as `- <item>. Say: "<say>"` only when `quiet` (nothing else in progress). `board.py` puts the same dict in the board snapshot under `signoff`, and `src/forge/board_app/now.js` shows it. `signoff()` returns the empty dict once the repo is not a prototype. This story fills that case. It adds no second list, key or block.
- The light review leaves two records in the fix's state (`.factory/fixes/<name>.json`): `allow_large = "Prototype before sign-off"` (written by `task.fix_start` in an unsigned prototype) and `review.blocking_level`, which the review result carries as `"P0"` when the light bar was used (`review.py` sets `"blocking_level": "P0" if light else "P1"`). The earlier release saved the same `review.blocking_level` (`tests/fixtures/forge-v1.2.2/src/forge/review.py`), so old and new states agree. `fix_kind` is not in older states, so the plan does not use it. A fix keeps its allowance after sign-off but gets `"P1"` then (`review.blocking_level` checks `repo.is_prototype(top, refs=(base, commit))`), so the allowance alone is not enough and `review.blocking_level == "P0"` is the exact source. A docs-only change also gets `"P0"` anywhere (`docskip.only_docs`), so the allowance is required too.
- The state of a story can reach the default branch with its first part, before the story is done; `story.completed` is what says a story is done. `board._machine_history(top)["stories"]` already holds `story.completed(...)` for each story.
- The "Demo only" label is the agent's own rule in `src/forge/templates/skill.md`. Nothing in Forge reads it today.
- No release is visible to Forge. Searched `src/forge/*.py` for release, production, Promote and deploy: `releases.py` and `upgrade.py` are about Forge's own versions. Promote is pressed in Mainline, a separate paid product, and deployment happens only on an explicit request. `conventions/deploy.md` and `docs/start-a-prototype.md` ("Prepare the first production release") are text only.
- Sample mode and the first change. While `sample_data` is true, `worker.py` (`TEST_STEPS["sample"]`) tells a worker not to add or run tests or CI, and `prcheck.ships` writes no workflow. The change for the sample-data line only edits `forge.toml` (and `forge sync` then writes the workflow); it adds no test or CI file, so the worker rule does not conflict. A worker may edit `forge.toml` only when the item's own Done-when names it (`task.settings_allowed`, which checks `"forge.toml" in done_when`); `tests/test_sample_setup.py::test_7_turning_sample_data_off_needs_a_settled_personal_data_answer` already starts such a fix with `--done "forge.toml turns sample_data off"` and closes it. Intake writes the Done-when itself (`intake.py`, `templates/start.md`), so an idea that leaves out the file name can produce a change that close then refuses.
- Size limits: `src/forge/nextstep.py` has 1193 lines against the 1200-line limit of `tests/test_rules.py::test_5_forge_stays_small`, and `src/forge/board.py` has exactly 1200. The new code therefore goes in a new module, and both files get only in-place edits.

### Settled (with the reason)

1. **The list reads landed facts, not the checkout.** `gaps.listing` takes the signed-off test, the sample-data setting and the label search from the default branch as last fetched: `repo.is_prototype(top, cfg, (landed,))`, `repo.sample_data(top, ref=landed)` (no `cfg`, so it reads `forge.toml` at that ref), and `git grep -l -F "Demo only" <landed> -- <paths>` (the `<landed>:` prefix is cut from each result). `cfg` from the checkout supplies only `repo` and `stage`, which a merge does not change. Reason: a merge from a worktree updates only the remote default branch, so reading the checkout would show closed gaps or miss new ones.
2. **The list is derived, never stored.** `forge next` and the board compute it on each call. Reason: principle 2 (one home per fact) and your bookkeeping rule.
3. **A line becomes a change with `forge start` (rows 2 and 3) or `forge fix start` (row 1), one change per line.** Forge picks a fix or a story for rows 2 and 3, as for any idea. Row 1 is always a settings-only fix, and its Done-when must name `forge.toml`, so the guide tells the agent to start it as `forge fix start "Turn off sample data" --done "<the row's Say text>" --kind mechanical`. Reason: `forge start` routes by size and a story still needs your approval, but intake writes the Done-when itself and could leave out the file name; `fix start` keeps the Say text as written. One story with the lines as tasks would force a plan and an approval for work that is often one small fix, and would copy the list into a plan file, which is a second home. At most three lines exist.
4. **The module is `src/forge/gaps.py`, with `listing(top, cfg, history=None)`.** It returns the same dict as `nextstep.signoff` plus `"always": True` when the list has rows. In `signoff()` the first check becomes `if not repo.is_prototype(top, cfg): return gaps.listing(top, cfg, history)`; the `has_client_input` check keeps its place for prototypes. `signoff` gets an optional `history` argument. `_report` passes the `history` it already has, and `board.py` passes none (the listing then calls `board._machine_history(top)`).
5. **Rows are always shown.** In `_report` the row condition `if quiet` becomes `if quiet or shown.get("always")`, one edit in place. A prototype's sign-off checklist keeps its quiet rule. Reason: with the old rule the heading would stay while the other gaps and their start phrases vanish as soon as the agent starts the first change. The guide tells the agent to look at what is in progress before it starts a line, so a line is not started twice.
6. **Line text is pinned here so the tests and the guide agree.** The heading is `Before production: <n> open gap(s)`. Rows, in this order:
   - Sample data: item `Sample data is on, so the app has no back end, no tests and no CI`; say `forge.toml sets the test command and checks and no longer has sample_data, Personal data is settled, and forge sync has written the CI workflow`. Shown while `repo.sample_data(top, ref=landed)` is true.
   - Light review: item `<n> part(s) had only the light review: <names>`; say `Review and test these parts in full: <names>`. `<names>` are fix names (the file names under `.factory/fixes/`), comma-separated. Shown for each landed fix state with `allow_large == "Prototype before sign-off"` and `review.blocking_level == "P0"`, whose name no other landed item names (see 7).
   - Demo only: item `<n> file(s) carry the "Demo only" label: <files>`; say `Build each demo-only feature properly or remove it: <files>`. `<files>` come from the `git grep` in Settled 1 over tracked files, leaving out `docs/`, `plans/`, `.factory/`, `.claude/`, `.codex/`, `.github/`, `tests/`, `AGENTS.md` and `README.md`. The label is exact and case-sensitive, as the guide writes it.
7. **How the light-review line clears.** A name counts as named when a landed fix's `why` or `done_when` contains it as a whole word (not inside a longer name), or when a story that `story.completed` reports as done has it in its `title`. A fix that is itself in the light-review set does not count as naming. A story whose first part has landed but is not done does not count. The Say text carries every name, so a change started from it usually names them. When a name is left out, the line stays and shows the names that no change has named. That is visible, never blocking.
8. **No sample-data line means no tests line.** Forge cannot read test coverage per part. Sample mode has no tests by definition, so the sample-data line and the light-review line already cover "no tests".
9. **Where the list shows.** The sign-off conditions for a prototype are unchanged. The new case is a signed-off client prototype. Outside a client repo, outside `stage = "prototype"` (a live repo included), and for Forge's own repo the dict is empty. The block title in `now.js` changes from `Open before sign-off` to `Open items`, one string.
10. **No refusal and no new gate.** Forge sees no release, so no command can honestly refuse on one. The two existing refusals stay as they are: close waits for a settled `Personal data` answer on the fix that turns sample data off, and a new story needs the approved app rules.

### Done-when details

1. Sample-data line (LIST).
   - Test `tests/test_prodgap_list.py::test_1_sample_data_gap_shows_after_signoff_and_clears`, parameters `new client` and `earlier adopted`.
   - New client: a client made by `forge init`, `forge.toml` with `sample_data = true`, an accepted sign-off record on the remote default branch. After a `git fetch`, `forge next` in the main checkout prints `Before production: 1 open gap` and, with nothing else in progress, the row `- Sample data is on, so the app has no back end, no tests and no CI. Say: "<the Say text>"`. `forge board --json` holds the same `line` and one `open` row under `signoff`. Before the sign-off record is accepted, the line is `Sign-off: ...` as today and no `Before production` text shows. The test then starts the change from the printed text with `forge fix start "Turn off sample data" --done "<the Say text>" --kind mechanical`, and checks that the fix state's `done_when` names `forge.toml` (the close of such a fix is covered by `test_sample_setup.py::test_7`). A second clone then pushes `sample_data = false` (and the test command) to the remote default branch while the main checkout keeps the old file; after a `git fetch` in the checkout, the line and row are gone.
   - Earlier adopted: the fixture copy with `stage = "prototype"`, the current version and an accepted sign-off record, pushed to the remote default branch. With `forge.toml` holding no `sample_data` line, no sample-data row shows (an old record's `sample_data: true` line does not count). After the agent writes `sample_data = true` and the change reaches the remote default branch, the row shows. A copy that keeps `stage = "live"` shows no list.
2. Demo-only line (LIST).
   - Test `tests/test_prodgap_list.py::test_2_demo_only_labels_show_and_clear`, parameters `new client` and `earlier adopted`.
   - A signed-off client with `sample_data = false` and two files on the remote default branch, one app file with `Demo only` in a UI string and one `docs/` page that says it. `forge next` prints `Before production: 1 open gap` and the row `- 1 file carries the "Demo only" label: <the app file>. Say: "Build each demo-only feature properly or remove it: <the app file>"`. The docs page is not listed. A second clone pushes a change that removes the label while the main checkout keeps the old file; after a `git fetch`, the line is gone. The earlier-adopted client shows the same row for the same file.
3. All gaps together (LIST).
   - Test `tests/test_prodgap_list.py::test_3_open_gaps_show_together_and_stay_while_work_runs`, parameters `new client` and `earlier adopted`.
   - A signed-off client with `sample_data = true`, a labelled file and a light-reviewed landed fix. `forge next` prints `Before production: 3 open gaps` and the three rows in the order sample data, light review, demo only. The board's `signoff` holds the same three rows. After the agent starts the change for the first row (`forge fix start`), `forge next` still prints the heading and all three rows, with the started work listed too. Once the sample-data line clears, the heading reads `2 open gaps` and the other two rows remain in order.
4. The guide (GUIDE).
   - `src/forge/templates/skill.md`: in the Sign-off area, a short paragraph "After sign-off". The agent reads `Before production` in `forge next`; first checks what is already in progress so no line is started twice; starts the sample-data line as `forge fix start "Turn off sample data" --done "<the row's Say text>" --kind mechanical` and every other line with `forge start "<the row's Say text>"`; keeps each change's text naming the parts the line lists, so the line clears; does not press or ask for Promote while a line is open, unless the owner accepts the rest in chat; says plainly to the owner that Forge cannot see the release and refuses nothing. The paragraph says that a normal change has the full review level and that tests follow the repo's settings once the sample-data line is done.
   - `src/forge/templates/conventions/deploy.md` ("First production release"): add as a first step "Run `forge next`: no `Before production` line may be open, or the owner accepts the rest in writing." `docs/start-a-prototype.md` ("Prepare the first production release") gets the same step, and its sentence "plan and build the remaining production work through stories" points to the list. `docs/guide.md` gets one sentence.
   - `src/forge/templates/brief.md` does not change. Workers build the changes as they build any change, and the worker's rules do not change: the sample-data change is settings only and adds no test file (see the evidence on sample mode).
   - Test `tests/test_prodgap_guide.py::test_4_the_guide_says_what_to_do_with_each_gap`, parameters `new init` and `previous release`, built like `tests/test_after_demo_guide.py::delivered`. The synced skill copies and `deploy.md` hold the sentences (whitespace collapsed). `previous release`: after `forge sync`, `git status --porcelain` lists only synced files and no app file.
5. Light-review line (LIST; Done-when 2, second half).
   - Test `tests/test_prodgap_list.py::test_5_light_reviewed_parts_show_and_clear_when_named`, parameters `new client` and `earlier adopted`.
   - Landed fix states on the remote default branch: `build-login` (allowance, `review.blocking_level` `P0`), `fix-copy` (allowance, `review.blocking_level` `P1`, a full review after sign-off), `add-orders` (allowance, `P0`, status `dropped`), `tune-search` (no allowance, `P0` as a docs-only change) and `old-page` (the earlier release's shape: allowance and `P0`, no `fix_kind`). `forge next` prints a row naming `build-login` and `old-page` only, with the Say `Review and test these parts in full: build-login, old-page`.
   - A landed fix whose `why` is `Review and test build-login in full` clears `build-login` only. A landed light-reviewed fix that names `old-page` does not clear it. A name that is a prefix of another (`build-login` and `build-login-2`) clears only the one it names.
   - A story whose first part has landed but is not done, with `old-page` in its title, does not clear the name. After the story is done (its last part merged), the name clears. The test builds the story the way the existing story tests do.
   - No model call: the test sets the review and worker tools to fail if called, and the command still lists the gaps.

### New and existing repos

- **New repos** (`forge init`, with or without a starter): the list code arrives with the Forge release the repo is pinned to. The guide text arrives at `forge init`. The list shows after the repo's own first sign-off.
- **Existing repos** (after upgrade and `forge sync`): the list code arrives at upgrade. A repo that is still marked as a prototype and has an accepted sign-off shows its gaps at once, from its own settings, fix records and files on the default branch. A repo marked as live shows nothing. The guide text arrives with `forge sync`. No migration, no record, no app file. A repo without a sign-off sees no change.

## Tasks

<!-- One row per task. Covers: the Done-when numbers it delivers, at most three. Scope: the paths
it may change. Before writing each Scope, search the code for the files the task needs. The plan
check refuses two tasks whose Scope paths have the same prefix up to the first wildcard, unless
one waits for the other through After, directly or through another task; it names both tasks.
Paths with a segment named `tests`, `test`, `__tests__` or `spec` do not cause Scope overlaps
and can be shared without an After link. Explicit After links still apply.
When tasks need the same production file, put it in the first task's Scope with the shared names and stubs;
tasks that need them wait for that task through After and then own only their files. Tests: the
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
| LIST | The Before production list | `gaps.listing` with the three lines read from the default branch; `nextstep.signoff` and the board fall through to it once a prototype is signed off; rows always shown; the board block title | 1, 2, 3 | `src/forge/gaps.py` (new), `src/forge/nextstep.py`, `src/forge/board.py`, `src/forge/board_app/now.js`, `tests/test_prodgap_list.py` (new), `tests/test_sample_checklist.py`, `tests/test_proto_next.py`, `tests/test_journey_next.py` | `tests/test_prodgap_list.py` (`test_1`, `test_2`, `test_3`, `test_5`: `new client`, `earlier adopted`) | | no | |
| GUIDE | What the agent does with each gap | The "After sign-off" paragraph in the skill, the first-release step in the deploy page and the prototype page, the guide sentence, and the synced copies | 4 | `src/forge/templates/skill.md`, `src/forge/templates/conventions/deploy.md`, `docs/start-a-prototype.md`, `docs/guide.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_prodgap_guide.py` (new) | `tests/test_prodgap_guide.py` (`test_4`: `new init`, `previous release`) | LIST | no | |

GUIDE waits for LIST because LIST pins the heading and the three row texts that the guide quotes. The existing tests named in LIST's Scope may need a changed expectation only where a signed-off fixture now shows a `Before production` line. The edits to `nextstep.py` and `board.py` are in place and add no net line.

New moving parts: none

## Notes

- **Owner's choice, to confirm at approval (10 Nov 2026).** The working choice is "list the gaps after sign-off, then make each a normal change". It is not "a full review before sign-off". Reason: sample-data sign-off stays fast and light, and the full review and tests still happen before any production release, one change per gap. If you prefer the full review before sign-off, this story is the wrong one.
- **The light-review line: choose between keeping it and dropping it.** Recommended: keep it, using the exact source in the plan. A part counts only when its saved state has both the prototype allowance and a recorded light review level; the earlier release saved the same two facts, so old repos work and no new field is added. The price is a clearing rule that depends on a later change naming the part (fixes by their text, stories only when done), and a small documentation change from the prototype phase can appear in the line. If you do not want that price, the other choice is to drop the light-review line. The list then has two lines (sample data and "Demo only"), Done-when 2 loses its second half, and the part of the code that reads fix records and stories goes away. The light-review gap is then covered only by the guide text.
- **Scores (F x H >= 2 x C).** Each part's model-cost effect is stated.
  - Sample-data line: F 3 (every sample-data prototype that signs off), H 2, C 1 (reads the setting that the journey line already reads). 6 >= 2. Kept. No model call.
  - Demo-only line: F 2, H 2 (a demo feature reaches users as if it were real), C 1 (one `git grep`, about 10 lines). 4 >= 2. Kept. No model call.
  - Light-review line: F 2, H 2, C 2 (a read of landed fix and story records and a name match, about 50 lines). 4 >= 4. Kept, with the drop option above. No model call.
  - Showing all rows while work runs: F 3, H 2, C 1 (one condition). 6 >= 2. Kept.
  - Refusing the first production release: F 1, H 3, C 3 (Forge sees no release, so it would need a hook into a separate product). 3 < 6. Cut. The list and the guide stay.
  - A stored list, a gap record or a new command: cut by principle 2 and your bookkeeping rule.
  - A model pass to find gaps nobody labelled: F 1 (the gap check and the reviews already read the code), H 2, C 2 (one model call). 2 < 4. Cut.
  - A line for an empty test setting: it repeats the sample-data line, so it is cut as the same fact twice.
- **Other questions for the owner, each with a recommendation.**
  1. Confirm the choice above. Recommended: confirm.
  2. Forge cannot see the release, so it refuses nothing, and only the guide and the visible list hold it back. Recommended: accept. The other way needs a hook into the deploy product.
  3. The agent starts the changes with no extra OK from the FDE. Recommended: no extra OK. The lines are derived and not optional, and a story still needs your approval.
  4. The "Demo only" label is matched as exact text. Recommended: exact. A label that nobody wrote cannot be found without a model call.
  5. A repo marked as live shows no list, even with an accepted sign-off, because it never had sample mode or the prototype allowance. Recommended: accept.
- **Not verified.** The cost of calling `board._machine_history(top)` from the listing on the board path (the `forge next` path passes the history it already has). The builder measures `forge board --json` and `forge next` on a repo with many fixes and reports the time. If the board path is slow, the listing reads only `.factory/fixes/*.json` from the default branch with one `git ls-tree` and a `git cat-file --batch`, which gives the same data.
- No client repo is named in this story's code, tests, texts or commits.
