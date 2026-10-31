# Hand over client work to another machine

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- A person can give a client project to another FDE (the person who builds the client's app). Any item that is on GitHub can be continued, closed and merged from any machine, with no setup. A ready item merges from a machine that has never seen it, so the person who started it does not have to merge it. (Source: your decision 19, 31 Oct 2026)
- The decisions and lessons the agent wrote in its handoff notes are saved in the repo as a short file, `docs/handover.md`. A new clone starts its first session with those notes in view. (Source: your decision 19)
- The guide gets a short "Hand over" section with three steps: push everything, reassign each item, continue on the new machine. (Source: your decision 19)
- A new client repo gets all of this at `forge init`. An existing client repo gets the guide text with `forge sync` and the new behaviour with the Forge release. It gets no new file until its first hand over. (Source: the Forge review rules)

Design: none (no screens)

## Why

Handoff notes live in a folder that Git never saves, so they stay on the old laptop. A ready item's merge record lives in the same folder, and `forge merge` also needs a local copy of the item. Today a second machine cannot continue, close or merge an item that the first machine started. It is told that the person who started it must do it.

## Done when

1. **A ready item that was started on laptop A is merged with `forge merge` from laptop B. B has no local copy of the item and no record is copied by hand.**
2. **The decisions and lessons part of the agent's handoff notes is saved in a committed file, and a new clone shows it at the start of a session.**
3. **The guide has a Hand over section that names the three steps, and the coordinator skill file (`src/forge/templates/skill.md`) says the same thing.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none one-way. Each part reverts with its pull request.

Trade-off: a machine can take over an item that another person started, with no check that it was assigned to them. The assignment is the sign of intent. The tool asks nothing more. See the Notes.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-HANDOVER-1"`. Tests run the forge command and never import forge. Live (platform) tests use the style of `tests/test_next_local_progress.py::test_8` (real `close`, then remove the worktree and local branch, only GitHub faked by `github` and `pull`). The earlier-adopted case uses the `tests/fixtures/adopted-v1.2.2` fixture as in `tests/test_mcp_resources_guide.py::test_3`.

### Done-when details

<!-- Under each Done-when item's number: its evidence, edge cases and the tests that prove it.
Workers and reviewers get the entries of the items they cover. An item with nothing to add has
no entry. -->

1. Merge from another machine (MERGE).
   - `src/forge/task.py`: new `pick_up(item, branches)`. It does `git fetch -q origin <branch>`, then for the first branch whose state file at `origin/<branch>` names that branch, it runs `git worktree add -q -b <branch> <_folder> origin/<branch>` with the upstream set. It returns the path, or `None`. Reason: one helper fixes continue, close and merge, and it copies the `fix_drop` pattern (`src/forge/task.py:747-749`).
   - `close._worktree` (`src/forge/close.py:635`) calls `pick_up` before it refuses with `not_started`. `worker.checkout` (`src/forge/worker.py`, about lines 90-101) calls it before `no_checkout`. Task branch: `task/<KEY>-<TASK>`. Fix branches: `fix/<item>` and `forge/<item>`. `merge` and `land` both reach `close._worktree`.
   - `merge.merge` (`src/forge/merge.py`): when the local record is missing or invalid, read the pull request (`gh pr view`, which `merge` already runs) and use `time_records.from_body(pr["body"])["ready"]` (the pull request body already carries it, `src/forge/time_records.py:420-426`; `nextstep._item_readiness` reads it as `"shared": True`). It counts only when `review == "clean"` and `commit == headRefOid`. Then build `{"commit", "review": "clean", "base"?}` in memory. Create `path.parent` before `_save_ready`, because `.git/forge/ready/` may not exist on a new machine (`close` does `path.parent.mkdir`). If neither exists, keep the refusal `not_ready` ("Next: forge close <item>"). `close` on B now works through `pick_up`.
   - `merge`'s existing checks stay: head match, default-branch retest, tests or checks wait, `--match-head-commit`, remote branch delete, tidy. `merge` tidies away the worktree it made, because the head did not advance and the tree is clean.
   - `nextstep.py`: the ready, no-worktree, `merge = "agent"` line (about line 1052) becomes "<label> is ready to merge." with "Next: forge merge <item>". Change one line, so the file does not grow (1157 of 1200). Also, a worktree with a shared record whose HEAD equals the record commit and `merge = "agent"` gets "Next: forge merge <item>". Today it says "close it here". Keep the behind-the-pull-request line. Items that are not ready keep "runs on their machine".
   - Tests, in `tests/test_handover_merge.py::test_1_a_ready_item_merges_from_a_machine_with_no_checkout`, parameters `new repo` and `earlier adopted`.
     - `new repo`: real close on A makes the pull request body. Remove the worktree and branch, fetch, then `forge next` on B names `forge merge <item>`. `forge merge <item>` on B calls `gh pr merge` once with the recorded head, and the worktree is gone after. A fix and a story task are both covered.
     - `earlier adopted`: the pull request body has no ready record (older release). `forge merge` refuses with Next `forge close <item>`. `forge close <item>` on B, with no checkout, works. Then `forge merge` succeeds.
   - Edit the assertions that say "merges it from their machine" in `tests/test_next_local_progress.py` (`test_8`, agent case), `tests/test_fix_pane_grouped_board.py` (about lines 260-266) and `tests/test_board_counts.py` (about lines 217-222). The lines change to the new wording and carry a command.
2. The notes file (HANDOVER).
   - `docs/handover.md` is the one home for settled notes. It has the heading `## Decisions and lessons` with one line per decision or lesson. `.git/forge/handoff.md` stays the local scratch pad between hand overs, and "Current state" stays uncommitted because `forge next` derives it from git and GitHub.
   - `nextstep.context_hook` (`src/forge/nextstep.py:196`) also prints the `## Decisions and lessons` part of `docs/handover.md` as read from `story.landed_ref(top)`, so any checkout shows the default branch's notes. It prints nothing when the file or heading is missing. About 6 lines.
   - The guide tells the agent to write the file with an ordinary fix at hand over. Copy the new lines from the local notes into `docs/handover.md`. Keep it under about 30 lines, and drop lines that are no longer true.
   - Test `tests/test_handover_notes.py::test_2_a_new_clone_shows_the_committed_notes`, parameters `new repo` and `earlier adopted`. `new repo`: push a `docs/handover.md` to the default branch, clone, and `forge hook context` prints the notes after the `forge next` lines. `earlier adopted`: with no file, `forge hook context` output is unchanged and exits 0.
3. The guide (GUIDE). `src/forge/templates/skill.md` gets a "Hand over" section after "## Handoff" (about line 756). `docs/guide.md` gets the same, short, near "Merging a ready item". `forge sync` rewrites `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`. Also change the Handoff paragraph's last sentence from "The file is local and never committed" to say that at hand over the notes go to `docs/handover.md`. Also change the sentence at about line 685 that says an item merged from another machine "shows forge next's line naming who merges it". The board no longer names who merges.
   - The three steps in plain words:
     1. Push everything: in each worktree, commit and push; write the notes to `docs/handover.md` through a fix, and merge it.
     2. Reassign: `forge assign <KEY or KEY/TASK> <login>` for each story and part. Fixes cannot be reassigned, and the new machine continues them without it.
     3. Continue: on the new machine, `forge next`, then `forge work`, `forge close` or `forge merge` on each item. Forge makes the checkout from GitHub.
   - Test `tests/test_handover_guide.py::test_3_the_guides_state_hand_over`, parameters `new init` and `previous release`, with the setup of `tests/test_mcp_resources_guide.py::test_3`. Both synced skill copies hold the three steps (compare with whitespace collapsed). After `forge sync` on the earlier release, `git status --porcelain` lists only expected files.
   - Run `tests/test_guides_agree.py` too.

### New and existing repos

- New repos (`forge init`): the guide text, the session-start notes line and agent-side merge from any machine. No `docs/handover.md` until the first hand over.
- Existing repos (upgrade then `forge sync`): the same guide text and behaviour. Items closed under an earlier release have no ready record in the pull request body. On such items `forge merge` on a new machine says to run `forge close` first, and that now works there. One earlier-adopted case in each of tests 1 to 3.

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
| MERGE | Continue, close and merge from any machine | `task.pick_up`, its use in `close._worktree` and `worker.checkout`, the shared ready record in `merge`, the new `forge next` lines, and the updated old assertions. | 1 | `src/forge/task.py`, `src/forge/close.py`, `src/forge/worker.py`, `src/forge/merge.py`, `src/forge/nextstep.py` (the two ready lines only), `tests/test_handover_merge.py` (new), `tests/test_next_local_progress.py`, `tests/test_fix_pane_grouped_board.py`, `tests/test_board_counts.py` | `tests/test_handover_merge.py::test_1` (new) | | no | |
| HANDOVER | Notes file and the Hand over guide | `context_hook` prints the committed notes. The Handoff paragraph and the new Hand over section in `skill.md` and `docs/guide.md`. Synced copies. | 2, 3 | `src/forge/nextstep.py` (`context_hook` only), `src/forge/templates/skill.md`, `docs/guide.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_handover_notes.py` (new), `tests/test_handover_guide.py` (new) | `tests/test_handover_notes.py::test_2`, `tests/test_handover_guide.py::test_3` (new) | MERGE | no | |

HANDOVER follows MERGE because the guide's third step is true only after MERGE, and both change `nextstep.py` in different functions. Both parts stay far under the module limit of 1,200 lines (`close.py` 1168 and `nextstep.py` 1157 get only a few lines).

New moving parts: none

## Notes

- **Scores (F x H >= 2 x C).**
  - MERGE: F 2 (a machine change happens about weekly across the first 1,000 users), H 2 (a broken step), C 2 (about 80 lines, no model call or user step): 4 >= 4. Kept. Model cost: none. The retest and review calls are the ones that `merge` and `close` already make.
  - HANDOVER: F 2, H 2 (lost decisions mean wrong information), C 1 (about 6 lines of code plus text): 4 >= 2. Kept. Model cost: no model call. The notes add a few lines of input to each session start, kept small by the 30-line advice.
  - A `forge handover` command: F 2 x H 2 = 4 < 2 x 3. Cut.
  - Writing the committed notes automatically at each compaction: cut. It would dirty whatever branch is open, and the hook stays offline.
  - Saving the "Current state" part: cut. Principle 2: `forge next` already derives it from git and GitHub.
- **Planner choices the owner did not make.**
  1. Home for the notes is `docs/handover.md`, not `docs/context/`, because `src/forge/journey.py` reads that folder as client notes. It is not under `.factory`, which holds item state.
  2. Notes are written by an ordinary fix at hand over, so there is no new command and no change to the offline hook.
  3. A machine may take over a started item with no check that it is assigned to that person. Failure mode: two people build the same branch and the second push is refused. Likelihood: low, since hand over names who continues. A check would cost an extra assigned-to-me rule, so I added none without your buy-in.
  4. Fixes cannot be reassigned (`forge assign` takes a story or part). The guide says so. Making fixes assignable is a separate decision.
- Dependency: this story does not touch the FORGE-NOSCREENS-1 scope (starter screens and the feature command) and needs nothing from it.
