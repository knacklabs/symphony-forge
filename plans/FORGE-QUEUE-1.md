# Forge merges ready changes for you, several at a time, in a safe order

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- One command, `forge land --all`, takes every change that is ready or in close. It closes and
  merges them for you. You or the coordinator no longer run a hand-made merge lane.
- The run starts the oldest change first. It runs several changes at once, up to the agent places
  this machine has, the same count the machine's agent line uses. Each change merges when it
  passes, so a newer change with faster checks can merge before an older one.
- Only one such run works in a repo at a time. A second run stops and says so.
- Two changes that edit the same file do not close at the same time. The newer one waits until the
  older one merges or stops. Then it closes once, on top of the newer main, so the wait costs it
  no second review. A change that is already ready never waits. Forge's own record files, such as
  the spotted-problems list, do not count as the same file.
- A failed check whose log names none of the change's own files runs again once by itself. A
  second failure stops that change.
- When a change needs a worker or you, the run stops only that change. It says why and gives the
  next step, and the other changes go on. The run never answers a question for you.
- The run ends with one summary: what merged, what is ready for a human merge, and what needs you.
  A blocked review always shows there, by name.
- In a repo where a human merges, the run closes every change and merges nothing. Its summary lists
  the ready changes oldest first, with their pull request links, in the order to merge them.

## Why

On the night of 11 to 12 October, the coordinator merged about 25 changes in Forge's own repo with
a hand-made lane. The lane closed and merged ready changes three at a time. It held changes that
edit the same files, retried a flaky check once, and stopped to send findings to workers. Without
the hold, each merge forced a fresh review round on the other changes under review. One change
needed 17 review rounds, partly from this merge churn. The lane script also hid a blocked review:
it showed the change as still in progress. Every client coordinator must build the same lane by
hand today, or merge one change at a time. Forge already has each step in `forge land`; it only
lacks the queue.

## Done when

1. **One land command takes every change that is ready or in close, starts them oldest first, several at a time up to the machine's agent places, and merges each one when it passes; only one such run works in a repo at a time.**
2. **A change not yet ready that edits a file an older change in the run also edits waits until that older change merges or stops, then closes once on top of the newer main.**
3. **A failed check whose log names none of the change's own files runs again once by itself, and a second failure stops that change.**
4. **When a change needs a worker or the owner, the run stops only that change, names why and the next step, goes on with the others, never answers for the owner, and lists that change under "Needs you" in its final summary.**
5. **In a repo where a human merges, the run closes every change, merges nothing, and ends with the ready changes listed oldest first with their pull request links.**

## New and existing repos

- **New repos** (init or adoption): `forge land --all` works from their first change, with nothing
  to set. The guide tells the coordinator to use it in place of a hand-made merge lane. Tested on a
  repo made by `forge init`.
- **Existing repos** (on upgrade to this release): the same command works as soon as they run the
  new release, on the changes they already have in flight, with nothing to migrate and no setting
  to change. The guide arrives through `forge sync` as usual. `forge land <item>` for one change
  works as before. Tested on the adopted earlier-release fixture moved to this release.

## Risks

Risks: none one-way. Every part reverts with its pull request. Each merge in a run still passes
close's tests, review and checks, and each merged change reverts with its own pull request.

Trade-off: a change that shares a file with an older one starts its review later, because it waits
for the older one to merge. It then gets one review, not two.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Every new test file starts with `STORY = "FORGE-QUEUE-1"`; each Done-when item has exactly one
test function, `test_<n>_...`, in `tests/test_queue_land_all.py`, that runs the forge command
(never imports forge), on a repo made by `forge init` and on `tests/fixtures/adopted-v1.2.2` moved
to this release (the `client` fixture in `tests/test_conflicting_pull_requests_stop_check_waits.py`
shows the pattern). Only the existing stubs (GitHub's `gh` as in `tests/test_land.py`, Autoreview
and Codex as in `tests/test_close.py`) and elapsed time are faked. Each test starts two or three
fixes with `forge fix start` and commits their changes, so the run has real worktrees and real git
diffs.

**The shape.** `forge land --all` reuses `land.land` for each change; it adds a queue in front of
it and nothing else. In `src/forge/land.py`:
- The command's `item` argument becomes optional (`nargs="?"`, as `forge stop` does) and `--all`
  is added; exactly one of the two is given, else refuse with a new entry that names both forms:
  "Give one change or --all, not both and not neither." with next action
  "forge land <item>, or forge land --all". The `COMMANDS` listing row names both forms, and
  `forge sync` rewrites `docs/commands.md` from it. No new command: principle 6 keeps the command
  count fixed.
- The parent works from the main checkout (`machine.main_checkout`), whatever folder it starts in,
  and runs every git call and every child there, so a merge that removes a change's worktree never
  removes the parent's folder.
- One run per repo: the parent holds a lock file in the main checkout's `repo.forge_dir`, with its
  process id, for the whole run. A second `forge land --all` in the same repo refuses while that
  process runs: "A land run already works in this repo." with next action "wait for it to end,
  then forge land --all". A lock whose process no longer runs is taken over.
- Each change runs as its own child `forge land <item>` process, because close and merge change
  the working folder (`close.py` line 446, `merge.py` line 165), so threads can't share one
  process. The parent prints each child's lines prefixed with the change's name, and one line
  when a change starts, waits, stops, merges or is ready.
- A child started by `--all` runs with fix rounds off, through a private environment seam like
  the existing `FORGE_LAND_ROUNDS` one. With it, land never calls `worker.work`, never waits in
  `_wait_for_choice`, and never records a review-loop stop of its own. Where land today starts a
  fix round, it refuses with the problem close gave and the next step `forge land <item>` (which
  runs the worker's fix rounds as today).
- The places: at most `machine.half_cores()` children at once, the agents lane size that
  `forge lanes --json` reports. Reviews and plan reads take no place in the machine's line today,
  so the run's own cap is what limits it.

### Done-when details

1. Selection, from `story.worktrees(top)` with each branch's state (`repo.read_state`), as
   `close._worktree` reads it: every task and fix whose status is `reviewing`, `fixing`,
   `waiting for checks` or `ready`. Left out, and named in one line each: `started` and `working`
   (still with a builder), a change whose pull request already merged, and a busy change. Busy
   means another command already works on it: it has a running or waiting entry in
   `machine.entries()` for this repo and item (a worker, a review or a test run), or
   `board.active_runs(top, item)` shows a run of any kind, `ci` included, with a start and no end.
   `checks.wait` already records its wait as a `ci` run (`repo.record_run`), so a close or land
   that waits only for CI counts as busy while the process that recorded the run is still alive
   (the same pid-and-start identity the machine lanes check); a run whose process has ended counts
   as ended, so a killed close never keeps its change busy, and a long CI wait stays busy. The run never starts a second
   close on a busy change. A change in a review-loop stop (`hotspot`) goes straight to "Needs you" with its stop
   question, as item 4 says. Order: the run starts changes oldest first, by the commit that added
   the item's state file (the same `git log -1 --diff-filter=A` that `land.land` already runs),
   ties by name. Each child merges when its own close passes, so merges need not follow that
   order; only a shared file (item 2) makes one change wait for another. The run takes the set it
   finds at start; a change that becomes ready later waits for the next run.
   Test (one), run from one selected fix's worktree: three fixes in close, with no shared files.
   The `gh` stub records each call with a time. The run starts their closes oldest first and
   merges all three; the number of changes in close at one time never exceeds the agents size from
   `forge lanes --json`; with two or more places, two changes are in close at the same time; the
   run ends normally after the worktree it started in is removed. A fourth fix still `started` is
   named as left out and is not touched. A second `forge land --all` started while a live process
   holds the lock refuses with the one-run message and changes nothing. A fifth fix whose events
   show a `ci` run start with no end, from a minute ago, is named as busy and is not closed.
2. Changed files of a change: `git diff --name-only -z --no-renames origin/<default>...HEAD` in its
   worktree, as `land._rerun` reads them, less exactly two of Forge's own record paths:
   `plans/spotted.json` and everything under `.factory/`. Close writes these during a run and its
   merge step resolves them by itself, so they never make a change wait. Every other file counts,
   generated or not (a user's Husky hook among them). FORGE-MAINONCE-1's per-change spotted files
   need no exemption: each change writes only its own. Readiness is the one `forge next` uses,
   `nextstep._item_readiness(item, state, top)`: a clean ready receipt whose commit matches the
   branch head, and checks not failing. Close leaves a passed change's stored status at
   `waiting for checks`, so the stored status alone never decides this. A change that is not ready
   by that rule is held while any older change in the run
   that is still queued, held or in close shares a changed file with it. It goes on when each such
   change merges or stops. A ready change is never held: it goes straight to merge, and a change
   already reviewed keeps today's rules for a new review. The held line names the older change and
   one shared file. In a repo where a human merges, nothing merges in the run, so the run holds
   nothing (item 5). Main comes into the released change through close's own rule; with
   FORGE-MAINONCE-1 that is only on a real clash. Test (one): fixes A (older) and B, neither
   reviewed yet, both edit one file on different lines, and fix C edits another; A and C also both
   record a spotted line in close. Fix D, closed to ready earlier (its receipt matches its head),
   edits A's file and merges without a wait. B starts its close only after A's merge, which the `gh` stub's
   call log shows; C closes alongside A; B gets one review (one Autoreview call). In a second case
   A stops on a blocked review: B then closes and merges, and A is listed under "Needs you".
3. Land's rule stays: the child's close path calls `land._rerun` on a red check (once per pushed
   head, only when every failure is a first-attempt job whose log names none of the change's
   files and the tests passed here). One change: "the tests passed here" counts a passed record
   (`review.passed_record`) for either `test` or the command close itself ran this round
   (`fast_test` with its base filled in, as `review.close_test` builds it), since close records
   only the command it ran. Today `_rerun` (`land.py` line 140) checks `test` alone, so a repo with
   `fast_test` never re-runs. On a second red the child refuses with fix rounds off, as item 4
   says. Test (one), in a repo whose `fast_test` differs from `test`: the `gh` stub reports one
   failed check whose log names no changed file, then green after the re-run: the change merges
   and the output says "Re-running ... once". A second change whose check fails again after the
   re-run is listed under "Needs you" with the failed check and `forge land <item>` as its next
   step.
4. Stops: a child that ends with a refusal stops only its change. The parent keeps the refusal's
   problem and next action as the reason, and releases the changes held behind it. A blocked
   review, failing tests or failing checks give `forge land <item>` (fix rounds). A review-loop
   stop gives the stop question that `review.stop_question` prints and `forge next` repeats, with
   its `forge close <item> --resolve` step. Any other refusal keeps close's or merge's own text.
   The run never passes `--dismiss`, `--resolve` or an accept; the repo's 30-minute default answer
   still applies through `close.check_stop` as today, on a later run. The final summary keeps the
   shape the guide already gives: `Merged (n): ... · Ready to merge (n): ... · Needs you (n): ...`,
   each "Needs you" entry with its reason and next step on its own line. The run exits non-zero
   when any change needs you. Test (one): one fix whose review is blocked and one clean fix; the
   clean one merges; the summary lists the blocked one under "Needs you" with the review's finding
   title and `forge land <item>`; no Codex worker stub call is made; a third fix already in a
   review-loop stop is listed with its stop question and its state file is unchanged.
5. With `merge = "human"` on the default branch (`close.merger` says "human"), each child ends at
   land's existing "is ready; a human merges its pull request" line. The run holds nothing, merges
   nothing, and its summary lists the ready changes under "Ready to merge" oldest first, each with
   its pull request link. Test (one): two fixes that share a file, in a repo with the human merge
   setting: both close at the same time, the `gh` stub sees no `pr merge` call, and the summary
   lists both links, the older one first.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| QUEUE | The land queue | `forge land --all`: one run per repo from the main checkout, selection, oldest-first starts, children up to the agent places, the overlap hold, fix rounds off with stops and next steps, the final summary; the guide's land row and paragraph | 1, 2, 4 | `src/forge/land.py`, `src/forge/templates/skill.md`, `docs/guide.md`, `docs/commands.md`, `.claude/skills/forge/`, `.codex/skills/forge/` (the last three regenerated by `forge sync`) | `tests/test_queue_land_all.py` (`test_1`, `test_2`, `test_4`) | | no | |
| HUMAN | Human merges and retries | The human-merge run: no holds, no merges, the ready list oldest first with links; the proof that a flaky check re-runs once in the run; the guide's line on both | 3, 5 | `src/forge/land.py`, `src/forge/templates/skill.md`, `docs/guide.md`, `docs/commands.md`, `.claude/skills/forge/`, `.codex/skills/forge/` | `tests/test_queue_land_all.py` (`test_3`, `test_5`) | QUEUE | no | |

New moving parts: none

## Notes

- Builds on FORGE-MAINONCE-1 (approved and in flight): close brings main in only on a real clash.
  With it, a change released after an overlapping one merges takes main in at most once, and a
  change that shares no file takes no merge from main at all. This story needs none of its code,
  so no part waits on it; until it merges, close still brings main in each round as today.
- The two parts both edit `src/forge/land.py`, so HUMAN waits for QUEUE.
- Considered and left out: a new `forge queue` command. Principle 6 keeps a fixed command count,
  and `forge land` already holds every step.
- Considered and left out: fix rounds inside the run. The owner wants the run to stop and route a
  change that needs a worker; `forge land <item>` already runs those rounds for one change.
- Considered and left out: a re-run of any failed check once, whatever its log says. The existing
  rule already re-runs flaky failures once and never re-runs a failure that names the change's own
  files, so a real failure stops at once.
- Considered and left out: GitHub's merge queue. It needs repo settings most repos don't have, and
  Forge adapts to GitHub rather than mirrors it (principle 7).
- `land.py` is at 208 lines; both parts together stay far under 1,200.
- No client repo is named anywhere in this story's code, tests, texts or commits.
