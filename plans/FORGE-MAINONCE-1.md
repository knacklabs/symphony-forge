# Pull requests take in main only on a real clash

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- Closing a change no longer brings main into its pull request every round. Main comes in only
  when the pull request really clashes with it, or when GitHub's settings for the repo require it
  to be up to date and it is behind. A change that touches different lines from everyone else gets
  no merges from main at all.
- Fewer pushes means fewer CI runs cancelled halfway by the next push, so checks finish sooner and
  a change reaches Ready sooner.
- When a pull request starts to clash with main while checks are running, Forge notices at its
  next look at GitHub instead of waiting for checks GitHub will never run. Land and merge then
  bring main in themselves and carry on. A close you ran by hand stops and says to run close
  again, which brings main in.
- Merging works the same: a pull request that can merge is merged as it is, and main comes in only
  when GitHub says it can't merge as it stands.
- Problems that workers and reviews spot outside their change are kept per change, so two changes
  never clash over that list. The default branch still shows every spotted problem, old and new,
  and `forge next` still names the files that keep breaking.

## Why

Measured on Forge's own repo from 8 to 11 October: close brings main in on every round, so each
pull request gets a median of 5 merges from main (up to 16). 46 of 84 pull request CI runs were
cancelled mid-run by the next push. 17 times Forge stopped because GitHub runs no checks on a
conflicting pull request, each after a median 11 minutes of waiting. A finish with a clash took a
median 92 minutes against 35 without. Nothing asks for these merges: the repo's GitHub settings
don't require branches to be up to date and there is no merge queue. Most clashes are self-made:
of 22 changes merged since 10 October, 18 edited the shared spotted-problems list. Client repos
run the same close and pay the same price.

## Done when

1. **When a pull request has no clash with main, closing it round after round never brings main into it.**
2. **When a pull request clashes with main, or GitHub requires it to be up to date and it is behind, close and merge bring main in once at that point.**
3. **A pull request that GitHub reports as clashing is caught at Forge's next look at GitHub, without waiting for checks, and land and merge then bring main in and carry on by themselves.**
4. **Two changes never clash over the spotted problems they record, and the default branch still shows every spotted problem, old and new, and the files that keep breaking.**

## New and existing repos

- **New repos** (init or adoption): from their first change, close, land and merge bring main in
  only on a clash or when GitHub says the branch is behind under an up-to-date rule. Spotted
  problems are kept per change from the start; no shared list file is created. Tested on a repo
  made by `forge init`.
- **Existing repos** (on upgrade to this release): the same close, land and merge behaviour as soon
  as they run the new release, with nothing to migrate and no setting to change. Their existing
  spotted list stays where it is and is read together with the new per-change records; an old
  entry can still be marked done, and nothing rewrites or moves the list. Repos whose GitHub
  settings require up-to-date branches still get main brought in, once, when GitHub says the
  branch is behind. Tested on the adopted earlier-release fixture moved to this release.

## Risks

Risks: none one-way. Every change here reverts with its pull request. After a revert, spotted
problems recorded per change in the meantime stay in the repo but drop out of `forge next`'s
list until the change is applied again.

Trade-off, accepted by the owner on 2026-10-11: a pull request is no longer retested each time
main moves. CI still tests each push merged with main as it was at that push (GitHub's pull
request check), so two changes that only break each other in combination can still both pass if
main moves after the last push. This is what the repo's own GitHub settings already allow.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Every new test file starts with `STORY = "FORGE-MAINONCE-1"`; each Done-when item has exactly one
test function, `test_<n>_...`, that runs the forge command (never imports forge), on a repo made by
`forge init` and on `tests/fixtures/adopted-v1.2.2` moved to this release (the `client` fixture in
`tests/test_conflicting_pull_requests_stop_check_waits.py` shows the pattern). Only the existing
`env` stubs (GitHub's `gh`, Autoreview and Codex, as in `tests/test_close.py`) and elapsed time
are faked, so review outcomes are set by the test; git merges are real.

### Done-when details

1. Today `close.close` calls `_merge_default(top, item, branch, default)` unconditionally
   (`src/forge/close.py` line 139), which runs `git merge origin/<default>` every round. Keep the
   fetch and the stacked follow-up replay branch exactly as they are (their own condition, run
   first). The owner's merge-setting fix (`switch` in `close.close`) follows the same rule; its
   mechanical check (close.py lines 154-163) compares against the merge base instead of
   `origin/<default>` itself (`origin/<default>...HEAD` for the file list and the forge.toml
   summary, and the merge base's forge.toml as the original), so an unrelated file added on main
   is not counted as an extra change. Merge only when there is a clash, else return:
   - HEAD already contains `origin/<default>`: no merge (as today, git would no-op).
   - a trial merge conflicts: `git merge-tree --write-tree --no-messages HEAD origin/<default>`
     exits 1 (writes nothing; Git 2.38+, already relied on in `githooks.fix_base` and the replay
     path); or
   - the open pull request is reported `mergeable == "CONFLICTING"` or
     `mergeStateStatus == "BEHIND"` by GitHub. Read both from the existing `_pull_request` call by
     adding the two fields to its `gh pr list --json` list (no new gh call) and pass `pr` into
     `_merge_default`. A missing field or `UNKNOWN` counts as no clash.
   When a clash is found, the existing merge step runs unchanged: generated files auto-resolve,
   the roadmap merge rule applies locally, a real conflict refuses with today's `conflict` entry.
   Nothing else in close assumes main was merged: the review fingerprint, the part line limit and
   the test base all use the merge base already (`review.fingerprint`, `origin/<default>...HEAD`).
   Test (one): a fix whose main moves on an unrelated file, closed through two rounds (a blocked
   review, then a clean one) and to Ready: `git log --merges origin/<default>..HEAD` is empty on
   the pushed branch, and the review covered only the fix's files.
2. Clash cases, each bringing main in exactly once (one merge commit) in the round that finds it:
   (a) main changed the same lines, found by the trial merge before any pull request exists;
   (b) the `gh` stub reports the pull request `CONFLICTING` while the trial merge is clean (a
   roadmap clash the local merge rule resolves but GitHub can't): close merges, and a second close
   with the stub now `MERGEABLE` adds no further merge, so land never loops; (c) the stub reports
   `BEHIND` (a repo with the up-to-date rule): close merges. What close does after bringing main in
   (tests, a new review or a reused one) stays as today's rules decide; this story promises no
   review reuse.
   `forge merge`'s existing path on a `BEHIND`/`DIRTY` refusal (close, then merge again) now relies
   on rule (b)/(c) to bring main in. `tests/test_merge_refreshes_behind_base.py`'s `gh` stub gains
   the two fields on its `pr list` answer (`BEHIND` or `CONFLICTING`, matching what its `pr view`
   reports), and its rule still holds: a merge refused as behind or conflicting brings main in
   through close and merges. Existing tests that expected a merge commit from a non-clashing main move change their
   expectation, not their rule. Test (one) covers (a), (b) and (c).
3. `checks._wait` reads `gh pr view <branch> --json mergeable,headRefOid` only when a named check
   is pending. Read it on every look, before judging the checks, so a pull request that is green
   but now `CONFLICTING` for this head refuses instead of reaching Ready. `UNKNOWN` keeps waiting.
   New text for `checks.REFUSALS["conflict"]`: "GitHub reports this pull request clashes with the
   default branch, so it runs no checks on it." with next action "forge close {item}, which brings
   the default branch in". `forge land` already retries close once on this refusal; keep it.
   `forge merge` calls `checks.wait` before `gh pr merge`: on this refusal take the same path as a
   `DIRTY` merge failure (close, then merge again), once. Test (one): the stub reports the head
   `CONFLICTING` with every check green; `forge close` stops at the first look with the new
   message (no `FORGE_CHECKS_WAIT` timeout), and `forge merge` on a Ready item whose pull request
   turns `CONFLICTING` brings main in through close and merges. With every check green, the stub
   answering `UNKNOWN` then `MERGEABLE` makes close reach Ready only after the second look, and
   answering `UNKNOWN` throughout with `FORGE_CHECKS_WAIT=0` stops with "not green yet", never
   Ready. The 11-minute median wait in the
   evidence was not traced to one cause; the every-look read is the guarantee this item makes.
4. Spotted records move from the one shared `plans/spotted.json` to one flat file per item,
   `plans/spotted/<item>.json`, with a task's `/` written as `.` (`plans/spotted/KEY.TASK.json`;
   fix names never hold a dot), so there are no subfolders. Same entry format and checks
   (`spotted._parse`).
   - `spotted.record` writes only the item's own file, never another file. New entries go there.
     A closure (a fix whose Done-when names an open entry's path, or a dismissal) goes there too,
     as a copy of that entry with `status: done` and `closed_by` set, under the same key. Two
     changes closing the same entry each write their own file, so they never clash. `record`
     returns whether the own file changed; close commits that path (`close.py` lines 280-291 pass
     it to `_save` in place of `spotted.PATH`).
   - `spotted.read(top, ref)` reads the old file and every per-item file, on a checkout or a ref
     (`git ls-tree` of `plans/spotted/` for a ref), and returns one entry per key: a done copy wins
     over an open one, and among done copies the first by file path. `nextstep` and the hotspot
     count need no change beyond that.
   - `spotted.check` refuses when `plans/`, `plans/spotted` or the item's own file is a link, as it
     does for the old file today, and refuses an unreadable per-item file by its own path.
     `review.fingerprint` drops the folder as it drops the old file (line 144).
   - Nothing writes the old `plans/spotted.json` any more. Its `.gitattributes` merge rule stays
     for existing repos; new files need none.
   - Wording: `src/forge/templates/brief.md` (never edit the spotted records) and the guide's two
     mentions (Learn the traps, Hotspots) name the spotted records, not the one file.
   Test (one): two fixes started from the same main each record spotted lines on neighbouring keys;
   each pull request changes only its own spotted file, and merging both into main in a fresh clone
   without Forge's merge rule (as GitHub merges) has no conflict; `forge next` on that main counts
   entries from both and from an existing old list toward a hotspot. Then two more fixes whose
   Done-when both name the path of three open entries in the old list each close them; both pull
   requests leave the old list untouched and merge in the fresh clone with no conflict. The old
   list's three open entries on that path made `forge next` name it as a hotspot before; after
   both merge it no longer does. A linked `plans/spotted` refuses.

**Owner's merge-setting fix after main moves.** ONCLASH also proves the changed mechanical check: extend `tests/test_merge_enable_mechanical_review.py` with a case that advances main by an unrelated file after the first close, re-runs `forge close` on the owner's merge-setting fix, and expects the mechanical check to pass by comparing against the merge base, with no merge from main.

## Tasks

Every part may add its paragraph to `src/forge/templates/skill.md` and regenerate
`.claude/skills/forge/` and `.codex/skills/forge/` with `forge sync`; those are left out of the
Scope column so the two parts run in parallel. If they clash on the guide, the part closed second
brings main in, keeps both paragraphs and regenerates the copies.

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| ONCLASH | Main only on a clash | Close brings main in only on a trial-merge conflict or when GitHub reports the pull request conflicting or behind; the check wait reads GitHub's clash state on every look; merge brings main in through close when the wait finds a clash; the guide's close and merge paragraphs say so | 1, 2, 3 | `src/forge/close.py` (`_pull_request`, the call at line 139, `_merge_default`), `src/forge/checks.py`, `src/forge/merge.py`, `docs/guide.md`, the existing tests that expect a merge from a non-clashing main | `tests/test_mainonce_clash.py`, `tests/test_conflicting_pull_requests_stop_check_waits.py` | | no | |
| SPOTTED | Spotted per change | Spotted records kept in one flat file per item, closures recorded in the closing item's own file, read together with the old list, close committing the item's file, the brief's and guide's wording | 4 | `src/forge/spotted.py`, `src/forge/close.py` (the spotted lines 280-291 only), `src/forge/review.py` (the fingerprint's spotted line), `src/forge/nextstep.py` (only if `spotted.read` cannot keep its signature), `src/forge/templates/brief.md` | `tests/test_mainonce_spotted.py`, `tests/test_spotted.py`, `tests/test_hotspots.py` | | no | |

New moving parts: none

## Notes

- The two parts share only `src/forge/close.py`, in hunks far apart (the merge call near line 139
  and `_merge_default` for ONCLASH; the spotted lines near 280 for SPOTTED), so they build in
  parallel; the second to close brings main in only if git finds them clashing.
- Considered and left out: stopping the committed host guide copies (`.claude/skills/forge/SKILL.md`,
  `.codex/skills/forge/SKILL.md`). In Forge's repo they are byte-identical to
  `src/forge/templates/skill.md` (same git blob), so they clash exactly when the guide itself
  clashes, and close's merge step already resolves them by regenerating. Removing them adds no
  fewer clashes; in client repos they change only on upgrade. The guide's own clashes are real
  edits and are now caught by item 2 instead of costing a merge every round.
- Considered and left out: recording spotted problems on main at merge time. Forge never commits
  to the default branch, and repos where a human merges have no Forge step at merge time.
- `close.py` is at 729 lines; ONCLASH adds a few lines and stays far under 1,200. No new command.
- No client repo is named anywhere in this story's code, tests, texts or commits.
