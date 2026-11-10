# List prototype gaps after sign-off and close each one before production

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- After a customer signs off a prototype, the next-step view and the board show a short list headed "Before production". Forge builds the list itself from what it already knows. It makes no model call and saves no new file or record. (Source: your working choice, 10 Nov 2026; you confirm it when you approve this story)
- The list has up to three lines. One line says that sample data is still on, so the app has no back end, no tests and no CI. One line names the parts that were built with only the light review. One line names the files that carry the "Demo only" label.
- Each line gets one normal change, started with the usual start step. A normal change has the full review, and its tests follow the repo's settings. The sample-data line comes first, because its change turns tests and CI on for every later change.
- A line leaves the list on its own when its fact changes: sample data is turned off, the "Demo only" labels are gone, or a later change names every light-reviewed part.
- Forge cannot see when a person presses Promote on the deploy platform. So Forge cannot hold the first production release, and it refuses nothing. The list stays visible until it is empty. The guide tells the agent not to promote while a line is open, unless you accept the rest.
- A new client repo gets all of this from Forge itself, and the guide text when it is set up. An existing client repo gets the list the day it moves to the new release, with no migration and no file change. A repo that already has an accepted sign-off sees its own gaps at once. It gets the guide text when it refreshes its Forge files after the upgrade. (Source: the Forge review rules)

Design: none (the list reuses the board's existing sign-off block and its style; no new screen)

## Why

A prototype that signs off with sample data, no tests and only the light review is not ready for real use. Today the gaps sit in a static checklist and in review notes. Nothing shows them as open work after the customer says yes, so a prototype can go to production with its gaps unseen. You chose to keep the fast sign-off and to list the gaps afterwards, not to add a full review before sign-off.

## Done when

1. **While sample data is still on after sign-off, the list shows it as an open gap, and the line goes away when sample data is turned off.**
2. **The list names the files that carry the "Demo only" label, and the line goes away when the labels are gone.**
3. **The list names the parts that were built with only the light review. A part leaves the list when a later change names it.**
4. **The guide tells the agent to start one normal change for each line and not to promote while a line is open, and it says plainly that Forge cannot see the release and refuses nothing.**

## Risks

Risks: none one-way. Each part reverts with its pull request. No migration, no data change, no app file changes.

Trade-offs, in plain words:
- The list shows only what Forge can see. It cannot see a missing back end, except through the sample-data setting, and it cannot see a feature that nobody labelled "Demo only". The gap check at sign-off and the reviews of the build changes are the guards for those.
- A part leaves the light-review line only when a later change names it in its text. If the agent forgets the names, the line stays. That costs one more look, and nothing blocks.
- Forge does not hold the first production release. Only the guide and the visible list guard it.

Model cost: none for the list. It uses git facts and the settings. The changes that the lines start cost what any normal change costs.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-PRODGAP-1"`. Tests run the forge command and never import forge. Test numbers follow the Done-when items. Reuse the setups of `tests/test_sample_checklist.py` (`brief`, the board read through `forge board --json` and its `signoff` key), `tests/test_journey_next.py` (`_publish`, to put fixture commits on main) and `tests/test_proto_signoff.py` (`_adopted_client`, the earlier-release client). Only GitHub and the review tools are faked.

### What exists (evidence)

- Sign-off and the sample-data switch are built (FORGE-SAMPLE-1 and its fix). `repo.sample_data(top, cfg, ref)` in `src/forge/repo.py` is true only for a client repo whose `forge.toml` has `stage = "prototype"` and `sample_data = true`. A sign-off record's old `sample_data: true` line does not turn it on. It stays true after sign-off until a person writes `sample_data = false`.
- After an accepted sign-off the repo is no longer a prototype for `repo.is_prototype(top, cfg)` (it looks for an accepted record in the checkout and on the default branch), while `cfg["stage"]` stays `prototype`. So "signed off" is `cfg["repo"] == "client"`, `cfg["stage"] == "prototype"` and `not repo.is_prototype(top, cfg)`.
- What `forge next` shows after sign-off today: `journey.step_line` in `src/forge/journey.py` names "Step 5 of 7: set up tests" while `repo.sample_data` is true. Nothing lists the other gaps. The text Forge prints for the first step is the step name only; there is no `Next:` line for it.
- The one gap check before the demo is `review.md` block `<!-- sample-signoff -->`, run by `records._signoff_review(..., sample_data=True)`. It runs once, before sign-off, and sends its non-P0 findings to the item's Known issues (`records._signoff_known`). It is a check of the demo, not a list of production gaps. This story does not change it.
- The checklist shape already exists. `nextstep.signoff(top, cfg)` returns `{"line": str, "open": [{"item", "say"}]}`. `nextstep._report` prints the line, and prints each row as `- <item>. Say: "<say>"` only when nothing else is in progress. `board.py` puts the same dict in the board snapshot under `signoff`, and `src/forge/board_app/now.js` shows it as one quiet block. `signoff()` returns the empty dict once the repo is not a prototype. This story fills that empty case. It adds no second list, no second snapshot key and no second block.
- The light review is recorded in the fix's own state. `task.fix_start` writes `allow_large = "Prototype before sign-off"` into `.factory/fixes/<name>.json` when a fix starts in an unsigned prototype, and `review.blocking_level` gives such a fix the P0-only level. A fix keeps the allowance it started with. Tasks cannot start before sign-off, so only fixes carry it. The state also holds `fix_kind` (`backend`, `ui` or `mechanical`), `why` and `done_when`. States on the default branch are read by `board._machine_history(top)["states"]` (path to state); a state there has landed.
- The "Demo only" label is the agent's own rule in `src/forge/templates/skill.md` ("Label extra features \"Demo only\""). Nothing in Forge reads it today.
- No release is visible to Forge. Searched `src/forge/*.py` for release, production, Promote and deploy: `releases.py` and `upgrade.py` are about Forge's own versions. Promote is pressed in Mainline, which is a separate paid product, and deployment happens only on an explicit request. `conventions/deploy.md` ("First production release") and `docs/start-a-prototype.md` ("Prepare the first production release") are text only.
- Size limits: `src/forge/nextstep.py` has 1193 lines against the 1200-line limit of `tests/test_rules.py::test_5_forge_stays_small`, and `src/forge/board.py` has exactly 1200. The new code therefore goes in a new module, and `nextstep.py` and `board.py` get no net line.

### Settled (with the reason)

1. **The list is derived, never stored.** `forge next` and the board compute it on each call. Reason: principle 2 (one home per fact) and your bookkeeping rule. Git and `forge.toml` already hold every fact. A stored list would need its own upkeep and could disagree with them.
2. **A line becomes a change with `forge start "<the line's Say text>"`, one change per line.** Forge then picks a fix or a story, as it does for any idea. Reason: `forge start` exists, routes by size, and a story still needs your approval. One story with the lines as tasks would force a plan and an approval for work that is often one small fix, and it would copy the list into a plan file, which is a second home. At most three lines exist, so three starts at most.
3. **The module is `src/forge/gaps.py`, with `listing(top, cfg, history=None)`.** It returns the same dict as `nextstep.signoff`. In `signoff()` the first check becomes `if not repo.is_prototype(top, cfg): return gaps.listing(top, cfg, history)`, and the `has_client_input` check keeps its place for prototypes. `signoff` gets an optional `history` argument. `_report` passes the `history` it already has, and `board.py` passes none (the listing then calls `board._machine_history(top)`). Both edits change a line in place.
4. **Line text is pinned here so the tests and the guide agree.** The heading is `Before production: <n> open gap(s)`. Rows, in this order, with `<n>` filled in:
   - Sample data: item `Sample data is on, so the app has no back end, no tests and no CI`; say `Set up tests and CI, settle Personal data, then turn off sample data`. Shown while `repo.sample_data(top, cfg)` is true.
   - Light review: item `<n> part(s) had only the light review: <names>`; say `Review and test these parts in full: <names>`. `<names>` are fix names (the file names under `.factory/fixes/`), comma-separated. Shown for each fix on the default branch that has `allow_large == "Prototype before sign-off"`, `fix_kind` of `backend` or `ui`, and a status other than `dropped`, and whose name no other landed item names (see 6).
   - Demo only: item `<n> file(s) carry the "Demo only" label: <files>`; say `Build each demo-only feature properly or remove it: <files>`. `<files>` come from one `git grep -l -F "Demo only"` over tracked files in the checkout, leaving out `docs/`, `plans/`, `.factory/`, `.claude/`, `.codex/`, `.github/`, `tests/`, `AGENTS.md` and `README.md`. The label is exact and case-sensitive, as the guide writes it.
5. **No sample-data line means no tests line.** Forge cannot read test coverage per part. Sample mode has no tests by definition, so the sample-data line and the light-review line already cover "no tests". A separate line for an empty `test` setting is cut (see Notes).
6. **How the light-review line clears.** A fix name counts as named when another landed fix's `why` or `done_when`, or a landed story's `title`, contains it as a whole word (not inside a longer name). A landed fix that is itself light-reviewed does not count as naming. The `Say` text carries every name, so a change started from it usually names them. The mismatch case is the failure mode: the line stays and shows the names that no change has named. That is visible, never blocking.
7. **Where the list shows.** The sign-off conditions for a prototype are unchanged. The new case is a signed-off client prototype. Outside a client repo, outside `stage = "prototype"`, and for Forge's own repo the dict is empty. The board block title in `now.js` changes from `Open before sign-off` to `Open items`, one string.
8. **No refusal and no new gate.** Forge sees no release, so no command can honestly refuse on one. The two existing refusals stay as they are: close waits for a settled `Personal data` answer on the fix that turns sample data off, and a new story needs the approved app rules.

### Done-when details

1. Sample-data line (LIST).
   - Test `tests/test_prodgap_list.py::test_1_sample_data_gap_shows_after_signoff_and_clears`, parameters `new client` and `earlier adopted`.
   - New client: a client made by `forge init`, `forge.toml` with `sample_data = true`, an accepted sign-off record on main. `forge next` prints `Before production: 1 open gap`, and, with nothing else in progress, the row `- Sample data is on, so the app has no back end, no tests and no CI. Say: "Set up tests and CI, settle Personal data, then turn off sample data"`. `forge board --json` holds the same `line` and one `open` row under `signoff`. Before the sign-off record is accepted, the line is `Sign-off: ...` as today and no `Before production` text shows. After the setting is `sample_data = false` (committed to main) the line and row are gone.
   - Earlier adopted: `_adopted_client(old_signoff=True)`, the earlier-release client with an old accepted sign-off whose record says `sample_data: true`, after the move to this release. With `forge.toml` holding no `sample_data` line, no sample-data row shows (the record's old line does not count). After the agent writes `sample_data = true` in `forge.toml`, the row shows.
2. Demo-only line (LIST).
   - Test `tests/test_prodgap_list.py::test_2_demo_only_labels_show_and_clear`, parameters `new client` and `earlier adopted`.
   - A signed-off client with `sample_data = false` and two tracked files, one app file with `Demo only` in a UI string and one `docs/` page that says it. `forge next` prints `Before production: 1 open gap` and the row `- 1 file carries the "Demo only" label: <the app file>. Say: "Build each demo-only feature properly or remove it: <the app file>"`. The docs page is not listed. After the label is removed from the app file and committed, the line is gone. In the earlier-adopted client the same file shows the same row.
3. Light-review line (LIST).
   - Test `tests/test_prodgap_list.py::test_3_light_reviewed_parts_show_and_clear_when_named`, parameters `new client` and `earlier adopted`.
   - Landed fix states on main: `build-login` (`allow_large` "Prototype before sign-off", `fix_kind` `ui`), `fix-copy` (same allowance, `fix_kind` `mechanical`), `add-orders` (same allowance, `backend`, status `dropped`), and `tune-search` (no allowance, started after sign-off). `forge next` prints a row naming only `build-login` and the Say `Review and test these parts in full: build-login`. After a landed fix whose `why` is `Review and test build-login in full` is on main, the row is gone. A landed fix that is itself light-reviewed and names `build-login` does not clear it. A name that is a prefix of another name (`build-login` and `build-login-2`) clears only the one it names.
   - No model call: the test sets the review and worker tools to fail if called, and the command still lists the gaps.
4. The guide (GUIDE).
   - `src/forge/templates/skill.md`: in the Sign-off area, a short paragraph "After sign-off". The agent reads `Before production` in `forge next`; for each line runs `forge start "<the line's Say text>"`, sample-data line first; keeps each change's text naming the parts the line lists, so the line clears; does not press or ask for Promote while a line is open, unless the owner accepts the rest in chat; says plainly to the owner that Forge cannot see the release and refuses nothing. The paragraph says that a normal change has the full review level and, once the sample-data line is done, tests.
   - `src/forge/templates/conventions/deploy.md` ("First production release"): add as a first step "Run `forge next`: no `Before production` line may be open, or the owner accepts the rest in writing." `docs/start-a-prototype.md` ("Prepare the first production release") gets the same step, and its sentence "plan and build the remaining production work through stories" points to the list. `docs/guide.md` gets one sentence.
   - `src/forge/templates/brief.md` does not change. Workers build the changes as they build any change, and the worker's rules do not change: a change that a line starts is an ordinary fix or task.
   - Test `tests/test_prodgap_guide.py::test_4_the_guide_says_what_to_do_with_each_gap`, parameters `new init` and `previous release`, built like `tests/test_after_demo_guide.py::delivered`. The synced skill copies and `deploy.md` hold the sentences (whitespace collapsed). `previous release`: after `forge sync`, `git status --porcelain` lists only synced files and no app file.

### New and existing repos

- **New repos** (`forge init`, with or without a starter): the list code arrives with the Forge release the repo is pinned to. The guide text arrives at `forge init`. The list shows after the repo's own first sign-off.
- **Existing repos** (after upgrade and `forge sync`): the list code arrives at upgrade. A repo with an accepted sign-off shows its gaps at once, from its own `forge.toml`, fixes and files. The guide text arrives with `forge sync`. No migration, no record, no app file. A repo without a sign-off sees no change.

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
| LIST | The Before production list | `gaps.listing` with the three lines; `nextstep.signoff` and the board fall through to it once a prototype is signed off; the board block title | 1, 2, 3 | `src/forge/gaps.py` (new), `src/forge/nextstep.py`, `src/forge/board.py`, `src/forge/board_app/now.js`, `tests/test_prodgap_list.py` (new), `tests/test_sample_checklist.py`, `tests/test_proto_next.py`, `tests/test_journey_next.py` | `tests/test_prodgap_list.py` (`test_1`, `test_2`, `test_3`: `new client`, `earlier adopted`) | | no | |
| GUIDE | What the agent does with each gap | The "After sign-off" paragraph in the skill, the first-release step in the deploy page and the prototype page, the guide sentence, and the synced copies | 4 | `src/forge/templates/skill.md`, `src/forge/templates/conventions/deploy.md`, `docs/start-a-prototype.md`, `docs/guide.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_prodgap_guide.py` (new) | `tests/test_prodgap_guide.py` (`test_4`: `new init`, `previous release`) | LIST | no | |

GUIDE waits for LIST because LIST pins the heading and the three row texts that the guide quotes. The existing tests named in LIST's Scope may need a changed expectation only where a signed-off fixture now shows a `Before production` line. The edit to `nextstep.py` and `board.py` is in place and adds no net line.

New moving parts: none

## Notes

- **Owner's choice, to confirm at approval (10 Nov 2026).** The working choice is "list the gaps after sign-off, then make each a normal change". It is not "a full review before sign-off". Reason: sample-data sign-off stays fast and light, and the full review and tests still happen before any production release, one change per gap. If you prefer the full review before sign-off, this story is the wrong one.
- **Scores (F x H >= 2 x C).** Each part's model-cost effect is stated.
  - Sample-data line: F 3 (every sample-data prototype that signs off), H 2, C 1 (reads the setting that the journey line already reads). 6 >= 2. Kept. No model call.
  - Demo-only line: F 2, H 2 (a demo feature reaches users as if it were real), C 1 (one `git grep`, about 10 lines). 4 >= 2. Kept. No model call.
  - Light-review line: F 2, H 2, C 2 (a read of landed fix states and a name match, about 40 lines). 4 >= 4. Kept. No model call.
  - Refusing the first production release: F 1, H 3, C 3 (Forge sees no release, so it would need a hook into a separate product). 3 < 6. Cut. The list and the guide stay.
  - A stored list, a gap record or a new command: cut by principle 2 and your bookkeeping rule.
  - A model pass to find gaps nobody labelled: F 1 (the gap check and the reviews already read the code), H 2, C 2 (one model call). 2 < 4. Cut. Can come back as its own story if gaps keep slipping through.
  - A line for an empty test setting: F 1 (sample mode already covers it), H 2, C 1. 2 >= 2 would pass, but it repeats the sample-data line, so it is cut as the same fact twice.
- **Questions for the owner, each with a recommendation.**
  1. Confirm the choice above. Recommended: confirm.
  2. Forge cannot see the release, so it refuses nothing, and only the guide and the visible list hold it back. Recommended: accept. The other way needs a hook into the deploy product.
  3. A part leaves the light-review line when a later change names it in its text. Recommended: accept, because a stuck line is visible and blocks nothing. The other way is a field that the follow-up change sets on the old fix, which is a new record.
  4. The agent starts the changes with no extra OK from the FDE. Recommended: no extra OK. The lines are derived and not optional, and a story still needs your approval. The owner can still say "later" to the agent, as for any idea.
  5. The "Demo only" label is matched as exact text. Recommended: exact. A label that nobody wrote cannot be found without a model call.
- **Not verified.** The cost of calling `board._machine_history(top)` from the listing on the board path (the `forge next` path passes the history it already has). The builder measures `forge board --json` and `forge next` on a repo with many fixes and reports the time. If the board path is slow, the listing reads only `.factory/fixes/*.json` from the default branch with one `git ls-tree` and a `git cat-file --batch`, which gives the same data.
- No client repo is named in this story's code, tests, texts or commits.
