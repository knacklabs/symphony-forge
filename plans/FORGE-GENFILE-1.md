# Flag a generated file that many tasks share

1 part · Risks: none one-way · New moving parts: none

## What changes for you

- When three or more parts list the same file in their scope (the list of files a part may change), the plan read names that file and those parts. The parts can be in the plan that is being read or in other stories that are planned or in progress. Forge does not start two parts that change the same file, so these parts run one after another. (Source: your request, 11 Nov 2026, after two stories in a client repo waited on one shared file)
- The note gives two pieces of advice. If a script makes the file (a generated file, such as an API contract, the file that describes the app's server calls, or the types made from it), make it when the app is built and stop keeping it in the repo. If not, do the shared change first, as its own part that the other parts wait for. (Source: your request, 11 Nov 2026)
- The note is advice. It does not stop the read or the approval, and it does not change which parts can start. Two parts still never change the same stored file at the same time, because changes to a generated file from two parts clash when they merge. The fix is to stop keeping that file in the repo. (Source: your request, 11 Nov 2026)
- The planning rules in the guide that Forge ships, and the plan template, say that a part's scope names no generated file. When a repo still keeps such a file, the plan starts with a small fix that stops that, or the parts that change the file keep it in their scope and wait for each other. (Source: your request, 11 Nov 2026)
- Forge finds the note from the plans alone and asks no model, so the note adds no model cost. It adds a few reads of the repo to each plan read; the time is not measured yet.
- A new client repo gets the note and the rule at once. An existing client repo gets the note when it moves to the new release, and the new guide text when it runs the usual guide update. Forge changes none of the repo's own files and no plan that is already approved.

## Why

In a client repo with several developers, two approved stories had 14 and 12 parts. Six parts of each story listed the same two files in their scope: an API contract file that a script writes, and the type file that is made from it. Both files were kept in the repo. Forge does not start two parts that change the same file, so the parts of one story waited for a part of the other story, and three developers could not work at the same time. Nothing in planning or in the plan read said that a scope should not name a file that a script makes. People saw many "waits for" lines, but no line named the one cause.

## Done when

1. **When three or more parts, in the plan or in other open stories, list the same file in their scope, the plan read names the file and the parts. It says to make a generated file when the app is built and stop keeping it in the repo, or else to do the shared change first as its own part. The note does not stop the read.**
2. **The planning rules in the shipped guide and in the plan template say that a part's scope names no generated file, and what to do when the repo still keeps one.**
3. **A new client repo gets the note and the rule at once; an existing client repo gets the note with the new release and the rule with its next guide update, and no file of its own changes.**

## Risks

Risks: none one-way. The part reverts with its pull request. No data or migration changes.

Trade-offs, in plain words:
- The note is advice. A plan can still be approved with many parts that share one file, and those parts still run one after another.
- The note counts parts in other stories only when those stories are on this computer or published. A story that only exists on another person's computer is not counted.
- The list of next steps keeps one wait line for each waiting part. It does not add one summary line for the shared cause (see Notes).

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

The new test file starts with `STORY = "FORGE-GENFILE-1"`. Tests run the forge command and never import forge. One test per rule.

### What exists (evidence)

- Inside one plan, overlapping Scopes are already refused before approval. `src/forge/plan_scope.py::check` refuses two tasks whose Scope entries overlap (`task._overlap`: literal prefix up to the first wildcard; a path with a `tests`, `test`, `__tests__` or `spec` segment never overlaps) unless one waits for the other through After. `src/forge/story.py::read` (about line 204) and `story.check_read` (about line 679) call it while the plan's approval hash does not match. So several parts of one plan can share a file today only when they are chained through After. That is the case the incident hit: six parts in a chain. Nothing reports it.
- Across stories nothing is checked at plan time. Waits happen only at start: `task.can_start` refuses with `REFUSALS["overlap"]` ("{item} would change {paths}, which {other} is changing and hasn't merged yet.") and appends `Scope overlap: <paths>.` (`src/forge/task.py` about lines 511 to 545). The started, unmerged parts of every story come from `task._started(main, top)`.
- `forge next` prints those refusal lines once per waiting part: `nextstep._story` builds `waiting` from each `can_start` error (`src/forge/nextstep.py` about lines 725 to 737). `nextstep._overlaps` separately prints "<a> and <b> change the same files: ... Please merge one first." for built branches.
- Every planned, approved or in-progress story with its plan text comes from `nextstep._stories(top)` (about line 578): stories on the default branch, in local worktrees and on published `origin/story/*` branches, without `done` and `dropped` ones. A part is merged when `task._merged(main, item, top)` is true; `main` is `story.landed_ref(top)`.
- Task rows of any plan text: `task.rows(task.sections(text))` and `task.cell_list(row["Scope"])`. The plan being read: `story._parsed(text, rel)["tasks"]`, each with `id` and `scope`.
- `story.read_result(top, target, result, said, ...)` finishes both the Codex/Claude kit reads and the session (native) reads after `forge handback`; its last statement prints "Round N of the cold read ... Next: forge next" or the "Wrote round N ..." line. `story.read` itself must not print to stdout before a native read, because `native.offer` prints one JSON document on stdout for the host.
- Generated files: `repo.generated_files(top, paths)` reads `linguist-generated` from `.gitattributes`. `src/forge/templates/skill.md` (about line 1985) already tells agents to mark generated files `linguist-generated`, so reviews show them only as line counts and size limits skip them. Nothing uses the mark for Scope.
- Guide text that holds the Scope rules: `src/forge/templates/skill.md` (the Tasks bullet, about lines 1554 to 1563), `src/forge/templates/story.md` (the comment block above the Tasks table), `docs/guide.md` (step 2, about lines 319 to 326), and the synced copies `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`. `tests/test_scope_overlap_explains_waits.py::_prepare` asserts that the adopted repo's synced copies hold "Paths with a segment named `tests`, `test`, `__tests__` or `spec`", so keep that sentence.
- Size: `src/forge/story.py` has 1187 lines, `src/forge/nextstep.py` 1197, `src/forge/task.py` 947, `src/forge/plan_scope.py` 45. The limit is 1200 (`tests/test_rules.py::test_5_forge_stays_small`).

### Settled (with the reason)

1. **How Forge knows: count, do not detect.** A Scope entry of the plan that is read gets a note when three or more parts list a matching entry, counting the plan's own parts and the unmerged parts of every other story from `nextstep._stories(top)`. "Matching" is `task._overlap`, the same rule that makes parts wait, so test paths never count. The note names this plan's entry as written. Reason: the count is exact and cheap, and the advice covers both causes (a generated file, or shared work). Detecting generators (package.json scripts, known tools) is guessing; the `linguist-generated` mark is not set in many repos and would only change the wording. Three, not two, because two chained parts sharing a file is the normal pattern the template asks for ("put a shared production file in the first task").
2. **Advice, not a refusal.** Inside one plan, unlinked overlaps are already refused; the new note covers the case that is allowed today (a chain through After) and the case across stories. Principle 4: a default or a note where a mistake is cheap. Score: F 2 (multi-developer repos, weekly), H 2 (parts that could run side by side wait), C 1 (about 25 lines, no model call) gives 4 >= 2.
3. **Where it prints.** `plan_scope.shared(top, key, tasks) -> list[str]` returns the note lines. `story.read_result` prints them on stdout just before its final "Round N ..." or "Wrote round N ..." line, for story reads only (`is_story`), and also before a `read_loop` refusal can end the run. The lines are not written to the read notes, so they need no disposition and add no round. Line text, one line per entry: `Shared file: <n> parts list <entry> in their Scope (<parts>), so they run one after another. If a script makes this file, make it at build time and stop committing it; otherwise put the shared change in one first part that the others wait for.` Parts of this plan are named by their ID, parts of other stories as `KEY/ID`.
4. **Other stories.** Use `nextstep._stories(top)` (imported inside the function, as `plan_scope.check` already imports `task._overlap`, to avoid a circular import). Skip the story being read, and skip each part for which `task._merged(story.landed_ref(top), "KEY/ID", top)` is true. Reason: the owner asked for planned stories, not only started parts; `task._started` would see started parts only. The builder times one `forge read` in this repo before and after and writes both numbers in the Proof list. If the added time is over about two seconds, the builder reports it in the handoff and does not change the source.
5. **No stop for generated files at start.** A file marked `linguist-generated` still makes parts wait when two Scopes name it. Two parts must never change the same committed generated file at once, because the merge conflicts. The advice is to stop committing the file.
6. **Guide text, one sentence each.** The planner rule in `skill.md`'s Tasks bullet, in `story.md`'s comment above the Tasks table and in `docs/guide.md` step 2: "A Scope names no generated file (a file a script writes, such as an API contract or the types made from it): it is made at build time and not committed. When the repo still commits it, plan a fix first that stops committing it; until that merges, the parts that change it keep it in Scope and wait for each other." `skill.md` also gets one sentence for the coordinator: "When `forge read` prints `Shared file:`, follow its advice before you ask for approval: start a fix that stops committing a generated file, or move the shared change into one first part." `cold-read.md` does not change: Forge prints the note itself, so the reader needs no new rule.

### Done-when details

1. Read note. `tests/test_plan_read_names_shared_files.py::test_1_the_plan_read_names_a_file_that_three_parts_share`, parameters `new repo` and `earlier adopted`.
   - `new repo`: `test_story.setup(repo, keys=("SHOP", "TURN-1"))`, then `test_story.new_story(repo, "SHOP")` with a plan of three parts chained by After (`B` after `A`, `C` after `B`) that all list `src/api/openapi.json`, and all list `tests/`. `forge read SHOP` exits 0, says "found nothing" (the stub reader answers "No findings."), and stdout holds one `Shared file: 3 parts list src/api/openapi.json in their Scope (A, B, C)` line with both pieces of advice. No line names `tests/`. `plans/SHOP.read.md` holds no `Shared file` text.
   - The same plan with only two parts sharing the file: no `Shared file` line.
   - Across stories: `test_story.ready(repo, "TURN-1", <a plan whose part T4 lists src/api/openapi.json>)`, then the SHOP plan with two chained parts that list it. `forge read SHOP` prints the note with 3 parts and names `TURN-1/T4`.
   - After T4's state reaches the default branch (merged by hand, as `tests/test_after_another_story_task.py::test_1` does), the same SHOP read prints no `Shared file` line.
   - `earlier adopted`: the earlier-release fixture `tests/fixtures/adopted-v1.2.2/client`, its pin moved to this release and `forge sync` run, as `tests/test_scope_overlap_explains_waits.py::_prepare` builds it, with the stub reader of `test_story.setup`. The three-part plan prints the same note.
2. Planner rule. Same test, both parameters: after `forge sync`, `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` hold "A Scope names no generated file" (whitespace collapsed), and `forge story new` writes a plan whose Tasks comment holds the same sentence. The builder checks that `forge sync` runs in the `new repo` setup; if it does not, the new-repo case uses `forge init` as other guide tests do and says which in the Proof list.
3. New and existing repos. Covered by the two parameters above. The `earlier adopted` case also asserts that `forge sync` leaves its existing approved plans unchanged (`git diff --quiet -- plans/` after sync).

### New and existing repos

- **New repos** (`forge init`): the note on every story read, the rule in the guide and in each new plan's template.
- **Existing repos** (upgrade, then `forge sync`): the note from the new release on the next read, the guide text after `forge sync`. Plans already written keep their template comment; approved plans and all app files stay unchanged.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| NOTE | Shared-file note and planner rule | The `Shared file:` note in the plan read, and the planner rule in the shipped guide, the plan template and the docs guide. | 1, 2, 3 | `src/forge/plan_scope.py`, `src/forge/story.py` (`read_result`, two or three lines), `src/forge/templates/story.md`, `src/forge/templates/skill.md` (Tasks bullet, one coordinator sentence), `docs/guide.md` (step 2), `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_plan_read_names_shared_files.py` (new) | `tests/test_plan_read_names_shared_files.py::test_1_the_plan_read_names_a_file_that_three_parts_share` | | no | |

New moving parts: none

## Notes

- **Open owner questions (recommended answer first).**
  1. Should `forge next` print one line for the shared cause, such as "4 parts wait because they all list <file>"? Recommended: no, not in this story. Each wait line already names the file (`Scope overlap: <file>.`), the plan read now names the cause before approval, and the file that prints these lines has 1197 of its 1200 allowed lines. Score: F 2, H 1, C 2 gives 2 < 4. It can be a fix later if people still miss the cause.
  2. Is three parts the right count for the note? Recommended: yes. Two parts that share a file in a chain is the pattern the plan template asks for, so a note at two would show on most plans.
  3. Should the note count planned stories that are not started yet, or only started parts? Recommended: planned stories too, as you asked. It costs a few extra reads of the repo per plan read; the builder measures it (Settled 4).
  4. Should a file marked as generated stop parts from starting at all, or let them run side by side? Recommended: neither. Parts that change it keep waiting for each other, because two changes to a committed generated file clash at merge. The advice is to stop committing the file.
- **What already exists.** The 6 Nov 2026 rule is in place: the read and the approval refuse two parts of one plan that share a Scope path without an After link. This story adds only the note for the cases that are allowed today (a chain through After, and other stories) and the planner sentence.
- **Order with other work.** `src/forge/templates/skill.md`, `docs/guide.md` and the two synced skill copies are also changed by parts of other stories in flight. Forge makes overlapping parts wait (`task.can_start`), so this part may wait for one of them to merge; the clash is a merge order only, on different paragraphs. `src/forge/story.py` may also be changed by other parts; this part adds only two or three lines in `read_result`.
- **Cut.** Reading `.gitattributes` to change the note's wording for files marked generated: F 1, H 1, C 1 gives 1 < 2. Detecting generator scripts: guessing, cut. A rule for the cold reader in `cold-read.md`: not needed, Forge prints the note without a model.
- **Model cost.** None added. The note comes from the Scope cells of the plans. Time per plan read: not measured; estimate a few seconds or less in a repo with many story branches.
- **Not verified.** That `nextstep._stories(top)` runs without errors from a story worktree when called during `forge read` (it is written for `forge next`); that `forge sync` works in the `test_story.setup` repo; the exact time `_stories` adds in this repo. The builder checks each and reports it.
- No client repo is named in this story's code, tests, texts or commits.
