# A story's parts build on each other instead of clashing through main

3 parts · Risks: none one-way · New moving parts: none

## What changes for you

- A part that waits on another unmerged part, because the plan puts it after that part or because
  both change the same files, no longer waits for that part to merge. As soon as that part's latest
  changes pass review, the next part starts on top of it, with its code already in place. A part
  builds on one unmerged part at a time, and only on one that itself starts from main.
- Its pull request shows only its own changes, and its review and size limit cover only those.
  It is never merged before the part beneath it.
- When Forge merges the part beneath, it points the next pull request at the main branch, moves
  its own changes on top of the merged code, tests it and merges it as usual. You resolve a
  conflict only when its own changes clash with what merged. Stacking follows only merges Forge
  makes: when a person merges the part beneath on GitHub themselves, the next part doesn't build
  on it and waits for it to be on main, as today, and Forge says what to run.
- The board and `forge next` show a stacked part as building on the part beneath it, and once it is
  built, as waiting for that part to merge.
- When a part can't start yet, Forge says which part it waits for and what to run next.
- One line in `forge.toml` turns this off, and parts then wait for merges as they do today.

## Why

A part that comes after another part starts from the main branch only once the earlier part has
merged, so a chain of parts runs strictly one after another: a recent board story's longest chain
was seven parts at two to three hours each. Parts that don't wait on each other but change the same
code each start from main and then clash with each other through main as they merge: one part of
the recent tools story went through four conflict re-closes and took 17.9 hours from start to merge
for about three hours of work. Over the last few days a finish with a conflict took a median of 92
minutes against 35 without. Today's workaround is waiting, or resolving the same clash again after
every merge.

## Done when

1. **A part that waits on one unmerged part that starts from main, because it comes after that part or changes the same files, starts on top of it as soon as that part's latest changes pass review, instead of waiting for it to merge.**
2. **When a part can't start on top of another, Forge says which part it waits for and what to run next: when it waits on more than one unmerged part, on a part that builds on another, on a part on an older Forge release, or on changes that haven't passed review.**
3. **While the part beneath is unmerged, a stacked part's pull request, review and size limit cover only its own changes, and it is never merged before the part beneath it.**
4. **When Forge merges the part beneath, the stacked part's pull request moves to the main branch, its own changes move on top of the merged code, and it is tested and merged as usual; when a person merges it on GitHub instead, nothing new stacks on that work until it is on main, and Forge says what to run.**
5. **The board and Forge's next-step summary show a stacked part as building on the part beneath it, and once built, as waiting for that part to merge.**
6. **One setting turns stacking off, and parts then wait for merges as they do today.**

## New and existing repos

- **New repos** (init or adoption): stacking is on; `forge init` writes no line for it. The guide's
  paragraphs arrive with `forge sync` as usual.
- **Existing repos**: after moving to this release, stacking is on without any change to
  `forge.toml`. Parts started before the upgrade keep their base and finish as today. Turning it
  off needs the new release first, because an older Forge refuses the new setting. Tested on a
  repo adopted on an earlier release and upgraded: a part after a reviewed part starts on top of
  it, and with the setting off it waits as before.

## Risks

Risks: none one-way. Turning the setting off brings back today's waiting for new starts; parts
already started on top of another part finish that way. A stacked part's tests run on the main
branch only after the part beneath merges, so a clash with code that merged meanwhile shows up
then, as it does today for a follow-up fix.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Stacked parts reuse what stacked follow-up fixes already do: `task.fix_start` records `stacked_on`
(the item beneath) and `base` (the start commit); `githooks.fix_base` counts only the item's own
changes while `stacked_on` is unmerged; `close._merge_default` replays only the item's own commits
onto the default branch once `stacked_on` merges, with a lease. This story drops the `kind ==
"fix"` gate there and gives parts the same two fields, so fixes and parts share one path. What
parts add: the start rule, a pull request that targets the base's branch, the retarget, and the
status lines.

**The start rule** (`task.stack_base`, pinned by START, called by `forge task start` and `forge
next` so they never disagree). Blockers are today's: the part's unmerged After parts plus started,
unmerged parts whose Scope overlaps (`waits_for` with `_started`). With `stack = "off"` or no
blockers, today's behaviour. The part stacks only when there is exactly one blocker and, read from
that blocker's pushed branch head: it is started; it is on main, meaning it has no `stacked_on`,
or the part in its `stacked_on` was merged by `forge merge` and that merge is in the blocker's
own history: `forge merge` adds a `Forge-merged: <item>` trailer to its squash commit (START adds
the trailer and its reader, CLOSE only uses them), and the commit carrying it for that part is an
ancestor of the blocker's head, so the blocker has already replayed onto main. A merge a person
made on GitHub carries no trailer, by any merge method, so nothing stacks on that blocker until it
is itself on main. Stacks are
two deep at most and a stacked part's base is never rewritten under it; its
`forge.toml` pin equals the default branch's; and its recorded review is `clean` and still covers
that head, by the same check `forge hook pr-check` makes (`review.fingerprint(head, ...) ==
review.changed`, review commit on the branch), so changes pushed after the review don't count as
built. Its base is that blocker's `origin/task/<KEY>-<TASK>`; the overlap check skips it. Any
other case refuses (item 2). One rule for same-story and other-story blockers.

Every new test file starts with `STORY = "FORGE-STACK-1"`, has one `test_<n>_...` per Done-when
item it covers, runs the forge command (never imports forge), and runs on a new repo and on the
previously adopted release fixture upgraded (the `previous` parametrisation the stacked-fix tests
use).

### Done-when details

1. `forge task start` on a stackable part branches from the top blocker's remote branch, carries
   the story doc as today when it differs, writes `stacked_on` and `base` into the part's state,
   and prints `Started <item> on top of <base item> on <branch> in <path>`. Test: A's close
   records a clean review (stub review); B After A starts and A's head is an ancestor of B; C with
   no After whose Scope overlaps A starts on A too.
2. Refusals in `task.REFUSALS`, each before any branch or commit:
   `"base_not_started": ("{item} builds on {base}, which hasn't started yet.", "forge task start {base}")`,
   `"base_not_built": ("{item} builds on {base}, whose latest changes haven't passed review.", "forge close {base}")`,
   `"base_stacked": ("{item} waits for {base}, which builds on {below}, so it starts once {below} merges.", "forge next")`,
   `"base_older": ("{item} waits for {base}, which runs an older Forge release, so it starts once {base} merges.", "forge next")`,
   `"two_bases": ("{item} waits for {deps}, so it starts once all but one of them merge.", "forge next")`.
   Test: each case refuses with its line, and no branch, worktree or remote branch is created:
   A not started; A reviewed, then a new commit pushed on A without a new review; B stacked on A
   and reviewed, and D After B, both while A is unmerged and after `forge merge` of A but before
   B's close replays it (D starts on B once that close has run); A started before the upgrade on the older pin; D After two
   unmerged parts.
3. `close` uses the part's own changes while `stacked_on` is unmerged: the size limit and the review
   base from the recorded `base` (as `fix_base`; `review.run` fetches a ref under `refs/remotes/`,
   so point a local one at it), the pull request opened with `--base` the base part's branch, no
   default-branch merge, no CI wait and no ready receipt; it ends with `Reviewed <item>; it is
   tested and merges after <base item> merges.` and `Next: forge next`. `forge merge` refuses with
   `"stacked": ("{item} builds on {base}, which hasn't merged yet.", "forge merge {base}")`.
   `forge hook pr-check` fails a stacked part's pull request while its base is unmerged with
   `<item> builds on <base item>; Forge checks its pull request once it targets <default>.` It
   fails rather than passes so a pass can never carry over to the default branch; the replay's
   push reruns it. `forge land` stops at the close line. Test: parent with 300 changed lines and
   child with 200 under a 400 limit closes; the stub `gh` sees the base part's branch as `--base`;
   the review stub's base excludes the parent's files; no checks are awaited; `forge merge` and
   pr-check refuse with their lines.
4. `forge merge` of a part, after GitHub reports it merged and before deleting its remote branch,
   points every open pull request based on that branch at the default branch (`gh pr list --base
   <branch> --state open`, then `gh pr edit <n> --base <default>`) and prints `Next: forge close
   <item>` for each. A failed retarget refuses before deleting:
   `"retarget": ("Forge could not point {other}'s pull request at {default}, so it kept {item}'s branch.", "check that pull request, then forge merge {item}")`.
   `close` of a stacked part whose base has merged retargets its own pull request when it still
   targets the base's branch refuses, since only Forge's merges are followed:
   `"base_merged_by_hand": ("{item} builds on {base}, which was merged on GitHub outside Forge, so its pull request still targets {base}'s branch.", "gh pr edit {number} --base {default}, then forge close {item}")`,
   with the pull request's real number. It fires only while the pull request targets the base's
   branch, never because the base's merge lacks the trailer, so once retargeted close carries on.
   Otherwise close replays as follow-up fixes do, then runs a new review (no reuse of the pre-replay review, whose commit the replay
   removed), waits for checks and records ready as usual. Test: after `forge merge` of A (stub
   `gh`), the retarget call comes before the branch delete; `forge close B` then replays B onto the
   squashed default branch, B's head no longer holds A's original commits, the real `forge hook
   pr-check` passes on B's new head against the default branch, and `forge merge B` merges; with A
   merged on GitHub (merge commit) and its branch kept, `forge close B` refuses with its line and
   D After B refuses to start (`base_stacked`); the test then runs the printed `gh pr edit <n>
   --base main` (the stub `gh` then reports base main) and `forge close B` again, which replays B
   onto the default branch, reviews it afresh, waits for checks and records it ready, and `forge
   merge B` merges; a clash in B's own changes stops with the existing
   replay refusal.
5. `forge next` lists a stackable part with `Next: forge task start <item>  # <worker> builds it on
   top of <base item>`; a started stacked part's line says `<item> is building on <base item>.`,
   and once its review is clean and the base is unmerged, `<item> is built and waits for <base
   item> to merge.` with the base's next step; after the base merges, `Next: forge close <item>`.
   The board's part status for the last two cases reads `Building on <base name>` and `Waiting for
   <base name> to merge`, by part name, in whichever module derives part status when SHOW starts
   (board.py today). Test: these lines in order across one A-then-B run, and `forge board --json`
   shows both statuses.
6. `repo.KEYS["stack"] = str`, `DEFAULTS["stack"] = "on"`, `CHOICES["stack"] = ("on", "off")`. With
   `off`, start and `forge next` behave as today. Test: `stack = "off"` refuses B with today's
   waiting line; `stack = "maybe"` refuses as `stack must be one of on, off`; the upgraded
   fixture has no line and stacks.

## Tasks

Each part adds its own paragraph to `src/forge/templates/skill.md` (the story-planning section
next to the After rules) and regenerates `.claude/skills/forge/` and `.codex/skills/forge/` with
`forge sync`; those are left out of Scope. The worker brief doesn't change: workers build in their
checkout as before.

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| START | Parts start on top of reviewed work | The `stack` setting, `task.stack_base` with the start rule, the `Forge-merged` trailer `forge merge` writes and its reader, stacked starts with `stacked_on` and `base`, the start refusals, `forge next` listing stackable parts as able to start, the settings paragraph in docs/guide.md | 1, 2, 6 | src/forge/repo.py, src/forge/task.py, src/forge/nextstep.py, src/forge/merge.py (the trailer line only), docs/guide.md | tests/test_stack_start.py | | no | |
| CLOSE | Stacked parts close, move to main and merge | Own-change size, review and pull request while the base is unmerged, the merge and pr-check refusals, land stopping, the retarget in merge, close's refusal after a merge made outside Forge, the replay gate opened to parts | 3, 4 | src/forge/close.py, src/forge/merge.py, src/forge/githooks.py, src/forge/prcheck.py, src/forge/land.py | tests/test_stack_close.py | START, FORGE-MAINONCE-1/ONCLASH | no | |
| SHOW | Next and the board show stacked parts | The building-on and waiting-for-base lines in `forge next`, the close step after the base merges, the board's two statuses | 5 | src/forge/nextstep.py, src/forge/board.py, src/forge/board_facts.py | tests/test_stack_status.py | START | no | |

New moving parts: none

## Notes

- Owner direction (2026-10-11): cut time-to-merge for this repo and client repos by letting a
  story's parts build on each other instead of clashing through main; stacking can be turned off.
- Decided: read note 7 (a person's merge on GitHub): stacking follows only merges Forge makes
  through `forge merge`; after a merge a person makes on GitHub, by any method, the next part
  doesn't stack and waits for that part to be on main, as today (owner, 2026-10-11).
- Runs after FORGE-MAINONCE-1 ("Pull requests take in main only on a real clash"): CLOSE waits
  for its ONCLASH part, which changes how close takes in main in the same function CLOSE changes.
  START and SHOW don't touch close and need no such wait.
- CLOSE and SHOW run side by side after START (no shared file). SHOW overlaps the board story's
  board work; the overlap guard holds it until those parts merge, and its status line goes in
  whichever module then derives part status.
- Stacks are two deep at most: a part never builds on a part that builds on another, so a
  stacked part's base branch is never replayed under it. In a longer chain, the third part starts
  on the second once the first has merged and the second has moved onto main and passed review
  again.
- Forge shrinks: no new command or module; stacked fixes and stacked parts share one replay path
  (the fix-only gate goes), and conflict re-closes through main drop for parts that stack.
- No client repo is named anywhere in this story's code, tests, texts or commits.
