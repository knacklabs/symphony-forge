# Forge learns where code keeps breaking

3 parts · Risks: none · New moving parts: one shared list file in the repo

## What changes for you

- Workers and reviews jot down problems they notice outside the change in hand. Forge keeps one
  list of them in the repo, writes each problem once, merges the list by itself when two changes
  add to it, and nobody edits it by hand.
- Workers note those problems and leave them alone, so a change never grows because of them. The
  one exception is a bug that stops the change itself from working.
- When problems keep piling up in one file, the next-step list names that file with a ready
  command for a fix that simplifies it. The agent starts that fix on its own, like any other
  ready work, without asking you.
- When that fix is merged, the file's noted problems count as resolved and the file leaves the
  list.
- When one change keeps failing review in the same file, Forge stops the change once after the
  third review and gives the fix to simplify that file first; the agent carries on with the change
  after that fix merges.
- It works the same whether the workers and reviewers are Claude or Codex.

## Why

Today a worker that sees a bug or a mess next to its change either fixes it, which makes the
change bigger and harder to review, or says nothing, and the knowledge is lost. Reviews already
give advice about code the change didn't need to touch, but that advice disappears with the pull
request. When one file keeps breaking, every change that touches it pays again: more fix rounds,
more reviews, and the same kind of finding coming back. Nothing counts this, so nobody stops to
simplify the file that is causing it.

## Done when

1. **When a worker or a review notices a problem outside the change in hand, Forge keeps it once in one shared list in the repository, and that list merges by itself when two changes add to it.**
2. **Workers note what they spot instead of fixing it, so a change never grows because of it, except a bug that stops that change from working.**
3. **The next-step list names each file where problems keep piling up, with a ready command that starts a fix to simplify it.**
4. **Once that fix is merged, the file's noted problems count as resolved and the file leaves the next-step list.**
5. **When a change's third review still finds serious problems in a file an earlier review of the same change flagged, Forge stops the change once and gives the fix to simplify that file first; the agent carries on after that fix merges.**
6. **The Forge guide tells the agent to start those fixes without asking, and the lessons step after a story uses how often each file broke.**

## Risks

Risks: none

## For the builders

### Done-when details

1. The list is `plans/spotted.json` (`spotted.PATH`), shaped `{"items": [<entry>, ...]}`, written
   as `json.dumps(data, indent=2) + "\n"` in UTF-8 bytes with LF line endings, the way
   `sync.merge_roadmap` writes the roadmap. `spotted.write(top, items)` sorts the entries by `key`;
   a merge can leave them in another order, and nothing reads the file's order. Each entry has
   exactly these fields: `key`, `kind` (`bug`, `simplify`, `edge` or `improve`), `path`
   (repo-relative, `/`-separated), `line` (int), `text` (one sentence, whitespace collapsed to
   single spaces, trimmed), `from` (`worker`, `review` or `blocking`), `item` (the task `KEY/TASK`
   or fix name whose close recorded it), `status` (`open` or `done`) and `closed_by` (null, a fix
   name, or `"dismissed"`); every field but `line` and `closed_by` is a string. `key` is
   `"\t".join([kind, path, text])`, with `"\t" + item` added when `from` is `blocking`, so a serious
   finding counts once per change. A new entry whose key is already in the list, whatever its
   status, is not added. `spotted.read(top) -> list[dict]` reads the checkout's file (no file is
   `[]`) and raises `spotted.Unreadable(problem)` unless the file is JSON, `items` is a list, and
   every entry has exactly those fields with those types and values. One blunt rule: anything else
   is unreadable.
   Forge writes the list only in close's own commits. `spotted.record(top, item, state, base,
   result) -> bool` runs in `close.close` on every close that reaches the review step, whether the
   review is new or reused, after the dismissals are applied and before close saves; it returns
   True when it changed the file. Close saves when it does today or when `record` returned True,
   with today's message `Review of <item>: <status>`, and adds `plans/spotted.json` to that commit's
   paths only when `record` returned True. So a new `Spotted:` line is recorded on the next close
   even when the review is reused, a close that spots nothing new makes no extra commit, and no file
   is created when nothing was ever spotted. The list sits under `plans/`, which the review's
   fingerprint skips (`review.BOOKKEEPING`, src/forge/review.py:32), and `review.fingerprint` skips
   `plans/spotted.json` even when a fix's done-when names it (the
   exception at src/forge/review.py:120 doesn't apply to it), so recording never makes a review
   stale. `record` reads three sources:
   - worker: each line of each non-merge commit message in `<base>..HEAD` (`base` is
     `origin/<default>`), with trailing whitespace and `\r` stripped, that fully matches
     `Spotted: (bug|simplify|edge|improve) (\S+):([0-9]+) (\S.*)`; a `\` in the path becomes `/`
     and a leading `./` is dropped; `from` is `worker`. Commit messages are the one source, so
     Claude and Codex workers are read the same way and no worker output is parsed;
   - review: each finding of `result` with priority `P2` or `P3` whose title doesn't start with
     `Later:`; `kind` is `simplify` when the title starts with `Simpler`, else `edge` for P2 and
     `improve` for P3; `text` is the title; `path` and `line` are the ones the finding cites, as
     they are (src/forge/templates/review.md:150 pins every finding to a changed line, so the list
     records where reviews pointed); `from` is `review`;
   - blocking: each finding `review.blocking(result)` returns; `kind` is `simplify` when the title
     starts with `Simpler`, else `bug`; `text` is the title; `from` is `blocking`.
   A line or finding is skipped when its path isn't a file in HEAD's tree or holds any character
   other than ASCII letters, digits, `.`, `_`, `/` and `-`, so a recorded path never needs quoting.
   When close records a dismissal, `record` sets that finding's blocking entry for this item to
   `done` with `closed_by` `"dismissed"`.
   Close reads the file right after merging the default branch, before the review, and refuses an
   unreadable one with `spotted.REFUSALS["bad"]`: `plans/spotted.json isn't a list Forge can read:
   {problem}.` / Next: `{repair}, commit it, then forge close {item}`, running no review and
   committing nothing. `{repair}` is `git -C {path} checkout {commit} -- plans/spotted.json`, where
   `{commit}` is the newest commit in the branch's own history whose copy reads (`git log
   --format=%H HEAD -- plans/spotted.json`, newest first). That history holds the branch's earlier
   review commits and every default-branch commit merged into it, so only the broken edit itself is
   lost. Only when no commit there has a readable copy is it `git -C {path} rm -q
   plans/spotted.json`, and then there was nothing to keep.
   Merging: `forge sync` adds `plans/spotted.json merge=forge-roadmap` (`sync.SPOTTED_RULE`) to
   `.gitattributes` beside `sync.ROADMAP_RULE`, each line added only when missing, and reuses
   `sync.merge_roadmap` and its registered driver unchanged: entries are matched by `key`, every
   entry on either side stays, and when both sides changed one entry `done` (rank 2) beats `open`
   (rank 1). Close already merges the default branch with that driver before every review.
   Tests (`tests/test_spotted.py`, driving `forge close` with the stub gh and Autoreview): a fix
   whose worker commits carry two valid `Spotted:` lines, one with a CRLF ending and one with a `\`
   path, plus one with an unknown kind, one without a line number, one naming a file not in the
   tree and one whose path has a space, gives exactly the two valid entries, with every field as
   above, in close's `Review of <item>` commit, and the file changes in no other commit; a review
   with a P2 `Simpler:`, a P3 `Simpler (existing):`, a P2 other, a P3 other, a P2 `Later:`, a P1
   and a P1 `Simpler:` gives `simplify`/`review`, `simplify`/`review`, `edge`, `improve`, nothing,
   `bug`/`blocking` and `simplify`/`blocking`, each with the path and line the finding cites; the
   same `Spotted:` line in two commits, and a second close after a new commit, give one entry; a
   worker line and a review finding with the same kind, path and text give one entry; one blocking
   title in one file from two items gives two entries; `--dismiss` of a blocking finding sets its
   entry `done` with `closed_by` `"dismissed"`; after a clean review, an empty commit carrying a
   `Spotted:` line is recorded by the next close in a `Review of <item>: clean` commit with no
   Autoreview call, and a third close makes no commit; a close with nothing spotted creates no file
   and the review commit holds only the state file; a file that isn't JSON, and one entry missing
   `item`, each refuse with the `bad` refusal and no Autoreview call; with a round-1 entry that
   round 2's review no longer raises and the file then broken by a hand commit, the Next restores
   the last readable copy and that entry comes back, with no readable copy ever it is the `rm`
   repair, and running the printed repair lets the next close review; a fix whose
   done-when names `plans/spotted.json` gets a clean review that a following close's recording
   doesn't make stale (no second Autoreview call); after `forge sync`, `.gitattributes`
   holds both rules once, also when it held only the roadmap rule, and two branches that each add
   entries whose keys interleave merge with no conflict and keep every entry, two branches that
   both create the file merge with no conflict, and an entry `open` on one side and `done` on the
   other merges as `done` whichever side git calls ours.
2. `src/forge/templates/brief.md`'s `## When you finish` section gains this paragraph, so every
   brief has it, fix rounds included (a continued brief says the earlier brief still applies):
   "Note anything you spot outside your item instead of fixing it: end a commit message's body with
   one line each, `Spotted: <bug|simplify|edge|improve> <path>:<line> <one plain sentence>`. Never
   widen this change for one, and never edit `plans/spotted.json`; Forge keeps it. The one
   exception is a bug that stops your item from working: fix it and name it in your handoff."
   Tests (`tests/test_spotted.py`): `forge work` on a task with `workers = "claude"` (the brief the
   stub claude records) and on a fix with `workers = "codex"` (the brief the stub Codex app-server
   records, set up and trusted as `tests/test_codex_worker.py` does) each contain that paragraph
   exactly.
3. `spotted.hotspots(items) -> list[dict]` returns `{"path", "reason", "count", "texts"}` per
   hotspot, sorted by path. A path is a hotspot when it has three or more `open` entries whose
   `from` is `worker` or `review` (reason `open`, count those entries), or when, for one `kind`,
   its `open` `blocking` entries name two or more distinct `item`s (reason `blocking`; the count is
   the largest number of distinct items any one kind has there); a path meeting both is listed once with reason `open`. `texts` are the texts of all
   that path's `open` entries, in key order. `spotted.fix_text(path, texts) -> tuple[str, str]`
   gives the fix's why, `Simplify <path>: problems keep turning up there`, and its done-when,
   `<path> is simpler and none of these happen any more: <t1>; <t2>; ...`, using the first five
   texts with every character other than ASCII letters, digits, spaces and `.,:;/_-` turned into
   a space and whitespace collapsed, then `; and <n> more` when there are more. Recorded paths hold
   only such characters too (item 1), so the printed command reads the same in a POSIX shell,
   PowerShell and cmd: double quotes around those characters are plain text in all three.
   `_report` in `nextstep.py` puts the hotspot lines right
   after the success-check lines and before everything else; the lines for nothing in progress
   still follow when nothing is. It reads the list from `story.landed_ref(top)`, skips a path that
   isn't a file there, and prints per hotspot `<path> keeps breaking: <count> noted problems are
   open there.` (reason `open`) or `<path> keeps breaking: <count> changes had the same kind of
   serious review finding there.` (reason `blocking`), then
   `Next: forge fix start "<why>" --done "<done>"`. It omits a hotspot when a fix worktree's state
   has that exact `why` (its fix lines already show). No file gives no lines; an unreadable one
   gives the one line `plans/spotted.json on the default branch can't be read, so no hotspots are
   listed: <problem>.` and `forge next` still exits 0. Tests (`tests/test_hotspots.py`, the list
   landed on the default branch by `forge close` and a commit made with the hooks off, as
   `tests/test_fix_plans_roadmap_json_conflicts_on_almost_e.py` does): three open worker or review
   entries in one file give both lines with the exact command; two give none; three with one
   `done` give none; three open `blocking` entries from one item give none; `blocking` entries of one kind in one
   file from two items give the `blocking` line; the same kind twice from one item, and two kinds
   from two items, give none; `bug` entries from two items and `simplify` entries from three in one
   file give one `blocking` line with count 3; a path with three open review entries and `bug`
   entries from two items gives one line, reason `open`; a text holding every ASCII punctuation
   character comes out with only `.,:;/_-` left; seven texts give five and `; and 2 more`; running the printed command, split with
   `shlex.split`, starts a fix whose recorded why and done-when equal `fix_text`'s; a fix worktree
   with that why hides the hotspot; a path no longer on the default branch gives no hotspot; no
   file, and an unreadable file, give the outcomes above.
4. `spotted.names(done_when, path) -> bool` is true when `path` appears in the text not touching
   a letter, digit, `_`, `.`, `/` or `-` on either side. In `spotted.record`, for a fix (an item
   with no `/`), before adding this round's entries: every `open` entry whose `item` isn't this fix
   and whose path `names(state["done_when"], path)` becomes `done` with `closed_by` the fix's name.
   The change lands with the fix's merge, so the hotspot leaves `forge next` then; a task never
   closes entries. Tests (`tests/test_hotspots.py`): a fix whose done-when is `fix_text`'s, closed,
   sets every open entry for that path `done` with its name, and leaves open the entries for
   `other/<path>`, `<path>.bak` and the fix's own `Spotted:` lines in that path; once that branch is
   merged into the default branch, `forge next` lists no hotspot for the path; a task whose Done-when
   details name the path closes nothing.
5. Close keeps `state["flagged"]`, the sorted files that held a finding `review.blocking` returned
   in an earlier review of this item, and adds the files of a new review's blocking findings to it
   when it saves that review. A new review stops the item when all of these hold: it is blocked; it
   is the item's third `review` step or later; the item has no `state["stop"]`; and a file holding
   one of its blocking findings is in `state["flagged"]`, is a file on `origin/<default>`, and
   passes item 1's path rule (only ASCII letters, digits, `.`, `_`, `/` and `-`). Any other review
   refuses with `blocked` as today: a file only on the item's branch never stops it, since a fix
   starts from the default branch (src/forge/task.py:230). `F` is the first such file in path
   order. The stop's fix never carries the review's findings, which may describe the stopped change
   itself; it asks only to simplify `F` as it is on the default branch: why `Simplify <F> before
   <item> carries on` and done-when `<F> is simpler and behaves as it did before`. Close sets
   `state["stop"] = {"file": F, "why": <why>, "done": <done>}` and the status `hotspot`, in the
   review commit (message `Review of <item>: blocked; <F> keeps breaking`), pushes and updates the
   draft pull request as for any blocked review, then refuses with `close.REFUSALS["hotspot"]`
   (`<r>` is the item's number of `review` steps): `Review round <r> of <item> still finds serious
   problems in <F>, which an earlier round flagged too, so Forge stops sending the worker back.` /
   Next: `forge fix start "<why>" --done "<done>", then forge close <item> once that fix merges`.
   The stop is a one-time pause (see the Decided line on resuming): Forge doesn't check that the
   fix merged. The next `forge close` of an item whose status is `hotspot` prints `<item> carries on
   after the stop for <F>.` and runs a new review even when the last one still covers the change,
   whose commit sets the status from its result as any review's does.
   An item stops at most once: with `state["stop"]` set, a blocked review refuses with `blocked` as
   today. `nextstep._item` shows status `hotspot` as `Close stopped <label>: <F> keeps breaking, so
   a fix that simplifies it goes first.` with the same Next line close printed. The skill's
   `## Hotspots` section adds: when close stops an item this way, start the fix it prints without
   asking the owner, run no more `forge work` on that item, and run `forge close <item>` again only
   after that fix merges.
   Tests (`tests/test_hotspot_stop.py`, driving `forge close` and `forge next` with the stub gh and
   Autoreview): three closes whose reviews block in `F`, a file on the default branch, in rounds 1
   and 3 give, on the third, the `hotspot` refusal with the exact fix command, a non-zero exit, the
   review commit with status `hotspot` and `state["stop"]`, a draft pull request, and `forge next`'s
   stop lines; the printed done-when holds none of the findings' titles; round 3 blocking only in a
   file no earlier round flagged, round 2 blocking in the file round 1 flagged, round 3 blocking in a
   flagged file that exists only on the item's branch, and round 3 blocking in a flagged
   default-branch file named `src/$cache.py`, each give the `blocked` refusal; a round-3 finding in
   `F` carried over as dismissed gives no stop; the close after the stop, with no new commit, prints
   the carry-on line, calls Autoreview, and its review commit has status `fixing` (or `waiting for
   checks` when clean); a round-4 block in `F` after that gives `blocked`, not a second stop; the
   skill template and both synced copies hold the stop sentence.
6. `src/forge/templates/skill.md` gains a `## Hotspots` section after `## Closing`, saying: a
   worker or review notes problems outside its change as spotted items, which Forge keeps in
   `plans/spotted.json` and nobody edits by hand; a spotted item never widens the change in hand,
   except a bug that blocks it; when `forge next` names a file that keeps breaking, start its fix
   command at once, like any ready item, without asking the owner; and when `forge merge` fails
   because the pull request no longer merges cleanly, run `forge close <item>` again, which merges
   the default branch with Forge's own rule for the spotted list and the roadmap. The
   **Learn the traps** paragraph adds: count the story's items' entries per file in
   `plans/spotted.json` on the default branch, open or done; each file with three or more, or one a
   task was stopped on (its state's `stop`), gets one trap line naming the file and the kind of problem that kept coming
   back. `forge sync` writes the same text to `.claude/skills/forge/SKILL.md` and
   `.codex/skills/forge/SKILL.md`. Tests (`tests/test_hotspots.py`): the skill template and both
   synced copies hold the section's sentences and the new Learn the traps sentence.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPOT | The spotted list | The list file, its format and merge rule, close recording workers' and reviews' spotted items, and the worker brief asking for them | 1, 2 | `src/forge/spotted.py`, `src/forge/close.py`, `src/forge/review.py`, `src/forge/sync.py`, `src/forge/templates/brief.md`, `.gitattributes` | `tests/test_spotted.py` | none | no |
| HOT | Hotspots | Hotspot counting, the next-step lines and ready fix command, a merged fix closing its file's items, and the skill's Hotspots section and Learn the traps step | 3, 4, 6 | `src/forge/spotted.py`, `src/forge/nextstep.py`, `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/` | `tests/test_hotspots.py` | SPOT | yes |
| STOP | Review loop stop | Close stopping an item once when its third review still blocks in a file flagged before, the next close carrying on, its next-step lines and the skill's stop sentence | 5 | `src/forge/close.py`, `src/forge/nextstep.py`, `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/` | `tests/test_hotspot_stop.py` | HOT | yes |

New moving parts: one tracked list, `plans/spotted.json` (item 1): no record that exists today reaches the default branch for every change (an item's state keeps only its last review), and it reuses the roadmap's merge rule and driver, so it adds no service, datastore, job or driver.

## Notes

- Decided: what workers and reviews report: lines `Spotted: <bug|simplify|edge|improve> <path>:<line> <one plain sentence>` at the end of a worker's commit message, and the review's existing advice findings (`Simpler:`, `Simpler (existing):`, other P2 and P3) as spotted items too (owner, 2026-10-01).
- Decided: where they live: one tracked file written only by Forge inside its own commits, merged automatically like the roadmap, never edited by hand, with no duplicate of the same path, kind and text (owner, 2026-10-01). Forge writes it in close's review commit only, which reads the worker's commits too, so one place serves both sources.
- Decided: hotspot rule: a file with three or more open spotted items, or the same kind of blocking review finding in one file across two or more items; `forge next` gives a ready fix command, the agent starts it without asking, and a merged fix whose done-when names the file closes its items (owner, 2026-10-01).
- Decided: the review loop stop: an item's third review round still blocking in a file an earlier round of the same item flagged stops the worker rounds, records the file and prints the fix to start; the item carries on after it merges (owner, 2026-10-01).
- Decided: spotted items never widen the current change, except a bug that blocks the item itself (owner, 2026-10-01).
- Decided: the skill says how the coordinator handles hotspots and the stop, and the learn-the-traps step after a story uses the hotspot counts (owner, 2026-10-01).
- SPOT pins what HOT and STOP use: `spotted.PATH`, the entry fields, `key`, statuses and `from`
  values above, `spotted.read`, `spotted.write`, `spotted.record(top, item, state, base, result)
  -> bool`, `spotted.Unreadable`, `spotted.REFUSALS["bad"]` and `sync.SPOTTED_RULE`; its item 1 test asserts the exact
  entries close writes, and HOT's first test starts from a list that `forge close` wrote, crossing
  both sides. STOP uses no name HOT adds; it comes after HOT because both edit `nextstep.py` and
  the skill.
- GitHub doesn't run Git's merge rules, so two open pull requests that both add to the list at the
  same place can conflict there, as the roadmap can today; the next `forge close` merges the
  default branch with Forge's rule and settles it (item 6 tells the agent).
- Decided: resume after a stop: one-time pause; the agent closes again after the fix merges (owner, 2026-10-01).
- Out of scope: a hotspot fix promoted to a story closes no entries, since a task never closes
  entries (item 4); the file stays listed until a later fix names it.
- Out of scope: `forge work` doesn't refuse a stopped item, and close doesn't check that the
  stop's fix merged (the skill tells the agent to wait for it); a fix whose review is still current when entries land after it stay open for the next fix;
  rounds reviewed before this story ships flag no files, so they never count towards a stop; the
  thresholds (three items, two items, round three, five texts) are constants, not settings.
- No client repo is named anywhere in this story.
- Claude workers build all three tasks; Opus writes the skill and brief text.
- Each new test file starts with `STORY = "FORGE-SPOTTED-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
