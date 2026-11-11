# Flag a generated file that many tasks share

1 part · Risks: none one-way · New moving parts: none

## What changes for you

- When three or more parts of the plan that is being read list the same file in their scope (the list of files a part may change), the plan read names that file and those parts. Forge does not let two parts change the same file side by side. A part that shares a file with another part starts only when that part has passed its review, and then it builds on top of it; otherwise it waits until that part has merged. So these parts are built one after another. (Source: your request, 11 Nov 2026, after two stories in a client repo waited on one shared file)
- The note gives two pieces of advice. If a script can make the file when the app is built (a generated file, such as an API contract, the file that describes the app's server calls, or the types made from it), and nobody needs it stored in the repo, make it at build time and take it out of the scopes. If the repo keeps the file on purpose, put its change in one first part that the other parts wait for. (Source: your request, 11 Nov 2026)
- The note is advice. It does not stop the read or the approval, and it does not change which parts can start. You can approve a plan with the note still there. (Source: your request, 11 Nov 2026)
- The note looks only at the plan that is being read. When parts of two different stories wait on the same file, the guide tells the agent what to do; Forge does not check other stories during the read. (Source: the first plan read, 11 Nov 2026: reading every other story made each read slow and could miss or stop on other people's stories)
- The planning rules in the guide that Forge ships, and the plan template, say: keep a file that a script can make at build time out of the repo and out of every scope; when the repo keeps such a file on purpose, give its change to one part that the others wait for. (Source: your request, 11 Nov 2026)
- Forge finds the note from the plan's own table and asks no model, so the note adds no model cost and no noticeable time.
- A new client repo gets the note and the rule at once. An existing client repo gets the note when it moves to the new release, and the new guide text when it runs the usual guide update.

## Why

In a client repo with several developers, two approved stories had 14 and 12 parts. Six parts of each story listed the same two files in their scope: an API contract file that a script writes, and the type file that is made from it. Both files were kept in the repo. Forge does not let two parts change the same file side by side, so the parts of each story were built one after another, the parts of one story waited for a part of the other story, and three developers could not work at the same time. Nothing in planning or in the plan read said that many parts would queue on one file. People saw many "waits for" lines, but no line named the one cause.

## Done when

1. **When three or more parts of a plan list the same file in their scope, the plan read names the file and the parts, with the advice to make a generated file at build time or to put the shared change in one first part. The note shows with the read's result on every way the read runs, and it does not stop the read or the approval.**
2. **The planning rules in the shipped guide and in the plan template say to keep a file that a script can make at build time out of the repo and out of every scope, and to give a file the repo keeps on purpose to one part that the others wait for.**
3. **A new client repo gets the note and the rule at once; an existing client repo gets the note with the new release and the rule with its next guide update.**

## Risks

Risks: none one-way. The part reverts with its pull request. No data or migration changes.

Trade-offs, in plain words:
- The note is advice. A plan can still be approved with many parts that share one file, and those parts are still built one after another.
- The note does not see other stories. Parts of two stories that share a file still show only as wait lines in the list of next steps, and the guide says what to do then.
- The note counts a file only when parts name that exact file. A part that names a whole folder is not counted.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

The new test file starts with `STORY = "FORGE-GENFILE-1"`. Tests run the forge command and never import forge. One test per rule.

### What exists (evidence)

- Inside one plan, overlapping Scopes are already refused before approval. `src/forge/plan_scope.py::check` refuses two tasks whose Scope entries overlap (`task._overlap`: the literal prefixes up to the first wildcard, where one contains the other; a path with a `tests`, `test`, `__tests__` or `spec` segment never overlaps) unless one waits for the other through After. `src/forge/story.py::read` (about line 204) and `story.check_read` (about line 679) call it while the plan's approval hash does not match. So several parts of one plan can share a file today only when they are chained through After. That is the case in the incident (six chained parts in each story). Nothing reports it.
- When parts that share a file can start (`src/forge/task.py::can_start`, `waits_for`, `stack_base`): a part's blockers are its unmerged After parts plus every started, unmerged part whose Scope overlaps its own (`task._overlap`). With `stack = "on"` (the default in `repo.py`) and exactly one blocker, the part starts on top of that blocker once the blocker's branch is published, its review is clean and current, it uses the same Forge pin, and it is not itself stacked on an unmerged part (`stack_base` refuses `base_stacked` otherwise). With two or more blockers, or `stack = "off"`, the part waits until they merge (`REFUSALS["waiting"]` or `REFUSALS["overlap"]`, with `Scope overlap: <paths>.` appended). `tests/test_stack_start.py` (task C shares `app.py` with A and starts on top of A) proves the stacked case. So a chain of parts that share a file is built one after another: each starts after the part before it has passed review, at most one level deep before a merge.
- `forge next` prints those refusal lines once per waiting part (`nextstep._story`, about lines 725 to 737). `nextstep._overlaps` prints "<a> and <b> change the same files: ... Please merge one first." for built branches, across stories.
- Scope cells: `story.parse` reads each Scope cell with `story._cell_paths` (split on commas, strip spaces and backticks at both ends; `none`, `-` and an em dash are empty). `story._parsed(text, rel)["tasks"]` gives each task's `id` and `scope` from it; `plan_scope.check` uses exactly these lists.
- `story.read_result(top, target, result, said, ...)` finishes both ways a read runs: the kit read (`story.read` calls it at about line 345 after the Codex or Claude call returns) and the session (native) read, where `forge read` prints one JSON document from `native.offer` (`src/forge/native.py` about line 122) and `forge handback` later calls `story.read_result` (`native.py` about line 240). Its stdout ends with "Round N of the cold read ... Next: forge next" or "Wrote round N ...". Nothing may print to stdout in `story.read` before a native read, because the host parses that JSON.
- Shipped guides that commit generated files on purpose: `src/forge/templates/conventions/python.md` (about line 182: "Commit both `libs/shared/api-types/openapi.json` and `libs/shared/api-types/src/api-types.ts`") and `src/forge/templates/conventions/database.md` (about line 73: "Commit the generated SQL"). Forge's own plans also list files that `forge sync` rewrites (the synced skill copies), which are committed on purpose. The planner rule must hold for all of these.
- Guide text that holds the Scope rules: `src/forge/templates/skill.md` (the Tasks bullet, about lines 1554 to 1563), `src/forge/templates/story.md` (the comment block above the Tasks table), `docs/guide.md` (step 2, about lines 319 to 326), and the synced copies `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`. `tests/test_scope_overlap_explains_waits.py::_prepare` asserts that the adopted repo's synced copies hold "Paths with a segment named `tests`, `test`, `__tests__` or `spec`", so keep that sentence.
- Size: `src/forge/story.py` has 1187 lines, `src/forge/plan_scope.py` 45. The limit is 1200 (`tests/test_rules.py::test_5_forge_stays_small`).

### Settled (with the reason)

1. **Count exact file entries in the plan that is read; do not detect generators.** `plan_scope.shared(tasks) -> list[str]` takes the parsed tasks (the same `scope` lists that `plan_scope.check` reads, from `story._cell_paths`). It cuts each entry at its first backtick or space, so a trailing note such as "(the one call)" is ignored. An entry counts only when it is an exact file path: no `*`, `?` or `[`, and it does not end in `/`. A test path never counts (an entry for which `task._overlap(entry, entry)` is false, which is the test-segment rule). The function groups equal entries and returns one line for each path that three or more parts list. Reason: equal strings are exact and cheap. A folder or glob entry is never named, because `task._overlap` would match one folder to different files that do not share anything. Detecting generator scripts is guessing, and reading `linguist-generated` would only change the wording. Three, not two, because two chained parts that share a file is the pattern the template asks for ("put a shared production file in the first task").
2. **Only this plan.** The note does not read other stories. Reason: `nextstep._stories` reads only branches already fetched, refuses on conflicting edits to another person's plan (`story._plan`), and checks completion of every story; in a 88-story checkout the reader measured 9.4 and 13.9 seconds for that part alone. Forge holds no other-story data for the read without that scan. The incident is caught without it: each story's read would have named its own six parts. The cross-story case is one guide sentence (Settled 5) and a possible later fix (Notes).
3. **Advice, not a refusal, and where it prints.** `story.read_result` prints the lines on stdout for story reads (`is_story`), parsing the read bytes it already holds (`_parsed(text.decode("utf-8"), rel)["tasks"]`), before the `read_loop` refusal check and before its final "Round N ..." or "Wrote round N ..." line. So the note shows in `forge read`'s output for a kit read and in `forge handback`'s output for a session read; it never prints in `forge read`'s JSON offer. The lines are not written to the read notes, so they need no disposition and add no round. Line text, one per path: `Shared file: <n> parts of this plan list <path> in their Scope (<IDs>), so they are built one after another. If a script can make this file at build time, stop committing it and take it out of Scope; if it is committed on purpose, put its change in one first part that the others wait for.` Score: F 2 (multi-developer repos, weekly), H 2 (parts that could run side by side queue), C 1 (about 15 lines, no model call) gives 4 >= 2.
4. **No change at start for generated files.** A file marked `linguist-generated` still makes parts wait when two Scopes overlap on it. Two parts never change the same committed file side by side, because a generated file conflicts at merge. Advice only.
5. **Guide text.** One planner sentence in `skill.md`'s Tasks bullet, in `story.md`'s comment above the Tasks table and in `docs/guide.md` step 2: "Keep a file that a script can make at build time out of git and out of every Scope. When the repo commits such a file on purpose (as the API-types and migration conventions do), give its change to one part that the others wait for, or chain the parts that change it through After; the plan read's `Shared file:` note is the reminder." `skill.md` also gets, next to it: "The `Shared file:` note is advice: tell the person what it means, change the plan when that is easy, and do not hold the approval for it. When `forge next` shows parts of two stories waiting on the same file, merge the part that changes it first, or move that file's change into one part that both stories wait for through After." `cold-read.md` does not change: Forge prints the note itself, so the reader needs no new rule.

### Done-when details

1. Read note. `tests/test_plan_read_names_shared_files.py::test_1_the_plan_read_names_a_file_that_three_parts_share`, parameters `new repo` and `earlier adopted`.
   - Kit read, `new repo`: `test_story.setup(repo)`, `test_story.new_story(repo, "SHOP")`, a plan of three parts chained by After (`B` after `A`, `C` after `B`) that all list `src/api/openapi.json` and `tests/`, with notes after some entries (for example "`src/api/openapi.json` (regenerated)"). `forge read SHOP` exits 0, says "found nothing" (the stub reader answers "No findings."), and stdout holds exactly one `Shared file: 3 parts of this plan list src/api/openapi.json in their Scope (A, B, C)` line with both pieces of advice, before the "Round 1" line. No line names `tests/`. `plans/SHOP.read.md` holds no `Shared file` text.
   - Same setup: the plan with only two parts that list the file prints no `Shared file` line. A plan where one part lists `src/api/` and two parts list two different files under it prints no `Shared file` line.
   - Approval is not held: the plan with the note is approved through the approval hook as `test_story.ready` and `test_after_another_story_task._plans` do (`claude_plan`, `hook`), and `forge task start SHOP/A` starts.
   - Session read, `new repo`: the native host of `tests/test_tools_native_reads.py::native_host`. `forge read SHOP` prints JSON that `json.loads` reads, with no `Shared file` text outside it. `forge handback SHOP --round <n> --subagent <id> --text "No findings."` prints the `Shared file:` line before its "Round" line.
   - `earlier adopted`: the earlier-release fixture `tests/fixtures/adopted-v1.2.2/client`, its pin moved to this release and `forge sync` run, as `tests/test_scope_overlap_explains_waits.py::_prepare` builds it, with the stub reader of `test_story.setup`. The three-part kit read prints the same line.
2. Planner rule. Same test, both parameters: the synced `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` hold "a file that a script can make at build time" and "The `Shared file:` note is advice" (whitespace collapsed), and `forge story new` writes a plan whose Tasks comment holds the first phrase. In `new repo` the builder runs `forge sync` after `test_story.setup`; if sync does not run there, the case uses `forge init` as other guide tests do, and the Proof list says which.
3. New and existing repos. The two parameters above: `new repo` gets the note and the rule; `earlier adopted` gets the rule after `forge sync` and the note from the new release. This story adds no change to a client's own files, so it has no separate check for them.

### New and existing repos

- **New repos** (`forge init`): the note on every story read, the rule in the guide and in each new plan's template.
- **Existing repos** (upgrade, then `forge sync`): the note from the new release on the next read, the guide text after `forge sync`. Plans already written keep their template comment.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| NOTE | Shared-file note and planner rule | The `Shared file:` note in the plan read's result, and the planner rule in the shipped guide, the plan template and the docs guide. | 1, 2, 3 | `src/forge/plan_scope.py`, `src/forge/story.py`, `src/forge/templates/story.md`, `src/forge/templates/skill.md`, `docs/guide.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md`, `tests/test_plan_read_names_shared_files.py` | `tests/test_plan_read_names_shared_files.py::test_1_the_plan_read_names_a_file_that_three_parts_share` | | no | |

`src/forge/story.py` changes only in `read_result` (two or three lines). `skill.md` changes in the Tasks bullet. The two synced skill copies are rewritten by `forge sync`. The test file is new.

New moving parts: none

## Notes

- **Open owner questions (recommended answer first).**
  1. Forge's own Python convention tells client apps to commit the API contract file and the API types made from it, the same two kinds of file as in the incident. Should Forge stop committing them and make them at build time? Recommended: not in this story; decide it as its own change. Making them at build time changes the starter's build, its tests and every client app that imports the types. This story's rule says that a file kept on purpose goes to one first part.
  2. Should `forge next` print one line for the shared cause, such as "4 parts wait because they all list <file>"? Recommended: no, not in this story. Each wait line already names the file (`Scope overlap: <file>.`), the plan read now names the cause before approval, and `src/forge/nextstep.py` has 1197 of its 1200 allowed lines. Score: F 2, H 1, C 2 gives 2 < 4.
  3. Is three parts the right count for the note? Recommended: yes. Two parts that share a file in a chain is the pattern the plan template asks for, so a note at two would show on most plans.
  4. Should a file marked as generated stop parts from starting at all, or let them run side by side? Recommended: neither. Parts that change it keep waiting for each other, because two changes to a committed generated file conflict at merge.
- **Possible later fix: other stories.** Count the same file across planned stories at read time. It needs a cheap list of open stories' Scopes; today only `nextstep._stories` gives it, and that is slow (9.4 to 13.9 seconds measured by the reader) and can stop on another person's plan. Start it with `forge start` only if the guide sentence is not enough.
- **What already exists.** The 6 Nov 2026 rule is in place: the read and the approval refuse two parts of one plan that share a Scope path without an After link. This story adds only the note for the case that is allowed today (a chain through After) and the planner sentences.
- **Order with other work.** `src/forge/templates/skill.md`, `docs/guide.md` and the two synced skill copies are also changed by parts of other stories in flight. Forge makes overlapping parts wait (`task.can_start`), so this part may wait for one of them; the clash is a merge order only, on different paragraphs. `src/forge/story.py` may also be changed by other parts.
- **Cut.** Counting other stories (see above). Reading `.gitattributes` to change the note's wording: F 1, H 1, C 1 gives 1 < 2. Detecting generator scripts: guessing. A rule for the cold reader in `cold-read.md`: not needed, Forge prints the note without a model.
- **Model cost.** None added. The note comes from the plan's own Scope cells, which the read already parses.
- **Not verified.** That `forge sync` runs in the `test_story.setup` repo; that the native host helper of `tests/test_tools_native_reads.py` can be reused for a SHOP plan with three parts as written. The builder checks both and reports them.
- No client repo is named in this story's code, tests, texts or commits.
