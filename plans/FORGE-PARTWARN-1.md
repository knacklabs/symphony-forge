# Warn about a large story part; never stop for it

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- A story part that changes more than about 400 lines (not counting tests, docs and plan files) no longer stops close with a question for you. Close shows one warning line with the real number and goes on to the review. There is no stop, no question for you and no extra builder round. (Source: your decision, 2 Nov 2026)
- When a part starts, Forge prints one line: keep the part to about 400 changed lines, and close only warns when it is larger. A part has changed no lines at that moment, so this line states the rule and measures nothing; the real number comes with the warning at close. The planning guide keeps its rule that the planner splits large parts, and no longer says that close stops them. (Source: your decision, 2 Nov 2026: "warn when the part starts, so the planner splits the work")
- A story that is already approved keeps working. If it has a saved size limit or a recorded size question, Forge ignores both. No migration runs. (Source: your decision, 2 Nov 2026)
- Principle 4 of the four simplicity principles ("Rules are stated, not policed") becomes three levels, in plain words: Forge does the right thing by default where it can; it refuses only when a mistake costs a lot or is hard to undo; it states a rule only when a mistake is cheap and something later catches it. People should not need to know how to use agents well for Forge to work. This text is in Forge's own `AGENTS.md` and in the review and builder instructions that Forge ships to every client repo. (Source: your decision, 2 Nov 2026)
- A new client repo gets all of this from the start: no size stop, the start line and the close warning, and the new principle text. An existing client repo gets the same after it upgrades and runs `forge sync`: the new Forge version stops asking the size question, and the synced guide and instructions carry the new text. A story approved on an earlier release keeps working with no change. (Source: the Forge review rules)

## Why

A part over 400 lines stops close and asks you, and the stop cannot be cleared. GitHub issue 960 shows that "accept" is refused for it and that the allowance command does not release it, so the only way out is a choice that says something else. Each stop costs a builder round. The size is a hint for the planner, and the review already reads the whole change. Principle 4 says "add no check or refusal only to enforce a rule". It does not say what Forge should do instead, and this story gives the answer.

## Done when

1. **A story part over 400 changed lines closes without a question for the owner and prints one warning line with its real size, and the review and pull request go on as for any other part.**
2. **A story part's start prints the size rule in one line, and the planning guide says the planner splits large parts and that close only warns.**
3. **A story approved before this change, with a saved size limit or a recorded size question, closes and shows its next step with no size question, in a new run and in a repo adopted on an earlier release.**
4. **Principle 4 reads as the three levels in Forge's own `AGENTS.md` and in the review and builder instructions that new and existing client repos receive.**

## Risks

Risks: none one-way. Each part reverts with its pull request.

Trade-offs, in plain words:
- A very large part now reaches review with only a warning. The review can be slow or shallow on a very large change, and the warning is the only signal. You chose this.
- The start line cannot say how large a part will be, because nothing has changed yet. It repeats the rule for a builder who skipped the guide. If you want no line at part start, say so and part SIZE drops it.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Each new test file starts with `STORY = "FORGE-PARTWARN-1"`. Tests run the forge command and never import forge. One test per rule. Before a round ends, run `uv run --frozen --python 3.11 pytest -q tests/test_rules.py::test_4_one_test_per_rule tests/test_rules.py::test_5_forge_stays_small`; `src/forge/close.py` is exactly 1,200 lines, so this change must leave it shorter (about 15 lines of stop code go, about 4 of warning come).

### What exists (evidence)

- The stop: `src/forge/close.py` lines 233-250. For an item with `/` whose state has `part_line_limit` and no `allow_large`, it sums `git diff --numstat` against the review ref, excluding `review.DOC_EXCLUDES` and `repo.TEST_PATHS`; over the limit it calls `stuck_stop(..., size=True)` or refuses with `REFUSALS["stuck"]` or `["chosen"]`. Line 249 pops a size stop when the part fits again.
- `check_stop` (`close.py:563`) releases a size stop only when `allow_large` is set. That is issue 960: a size stop recorded before the allowance stays. `stuck_stop` (`close.py:608`) has the `size` parameter and writes `"size": True` into the stop; both only serve this stop.
- The limit is written in two places: `src/forge/approval.py:142` (`"part_line_limit": 400` in the approval) and `src/forge/task.py:475` (copies it into each part's state at `forge task start`). Nothing else reads it (`grep part_line_limit src`).
- Other readers of `state["stop"]` that would show a recorded size stop: `nextstep.py:984,1033-1038,1106`, `worker.py:249` (`close.stuck_round`, which calls `check_stop`), `land.py:61,311` (also through `check_stop`), `close.py:106-171` (`--resolve`). `repo.read_state` (`src/forge/repo.py:1095`) is the one reader they share.
- `forge task start` prints `Started {item}{on} on {branch} in {path}` and `Next: forge work {item}` (`task.py:480-481`).
- Guide text: `src/forge/templates/skill.md` lines 1110-1114 ("about 400 changed lines each ... Close stops a part over 400 lines before review; split it, or record an allowance ... Stories approved before this limit keep working.") and line 1931 ("Close also stops a story part that grows past its line limit."). The generated copies `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` carry the same lines. `src/forge/templates/cold-read.md:167` (`Split: <task> → <two tasks>` for about 400 lines) is the planner's rule and stays.
- `forge fix allow-large` keeps working and still feeds the review prompt's "Recorded allowance" line; only its use as a size-stop release goes. No change to `task.allow_large`.
- Principle 4 text: `AGENTS.md:141` (outside the forge:begin and forge:end lines), `src/forge/templates/brief.md:457`, `review.md:202`, `cold-read.md:117`. `skill.md:831` is the line a client app's own constitution copies ("Rules are stated, not policed."); an approved constitution is never edited, so this story leaves that line.
- Existing tests: `tests/test_story_part_size.py` (stop cases and the guide case), `tests/test_allowed_part_closes_after_size_stop.py` (the stop and its release), `tests/test_part_code_size.py` (what counts), `tests/test_stack_close.py::_set_part_limit` (writes the limit; no case needs it after this change), `tests/test_four_principles.py` (asserts "Rules are stated, not policed" in the brief and review prompts).

### Settled (with the reason)

1. **The warning goes to stderr at close and does not stop.** Text: `This part changes {n} lines outside tests, over about 400. Split large parts when you plan them.` The count reuses the numstat code of close.py:234-239. Reason: only close has a real number; start has none (nothing changed yet).
2. **The limit is the constant 400, not a saved value.** One constant `PART_LINES = 400`, used by the close warning and the start line. The builder picks where it lives so that no import cycle appears (`worker.py:251` shows close imports story, which imports worker). Reason: the saved value is ignored by decision, so nothing reads it.
3. **`approval.py` stops writing `part_line_limit` and `task.py:475` stops copying it.** A saved value in an old approval or part is never read, so it stays in old files and is harmless. No migration (decision 2).
4. **A recorded size stop is ignored in `repo.read_state`:** it drops `stop` in memory when the stop has `"size": True`. The next state write removes it from the file. Reason: one line covers close, work, land, `forge next` and the board; the item's next close then has no stop to answer. Delete `stuck_stop`'s `size` parameter, `close.py:241-250` and the size line of `check_stop`.
5. **The start line is printed only for a story part** (an item with `/`), after the `Started ...` line and before `Next:`: `Keep this part to about 400 changed lines outside tests; close warns when it is larger.`
6. **Principle 4 new wording** (the same text in AGENTS.md and the three templates, each in the list's own numbering): `4. Forge does the right thing by default where it can. It refuses only when a mistake costs a lot or is hard to undo. It states a rule only when a mistake is cheap and something later catches it.` The builder may reword but keeps those three levels and the phrases "costs a lot or is hard to undo" and "something later catches it".
7. **No test that the four copies of the wording match each other.** The review reads them; a cheap mistake here is caught later.

### Done-when details

1. Close warns and goes on (SIZE).
   - `tests/test_story_part_size.py::test_1_close_warns_about_a_large_part_and_goes_on`, parameters `400 lines` (no warning), `401 lines` (warning with the count, close returns 0, one review call, one pull request create, no `stop` in the saved state), `deleted lines`, `tests and docs excluded` (counts only code, as `test_part_code_size.py` does now). Setup as the current file: `env.start_approved_task(STORY_DOC, changes=...)`. Delete `tests/test_allowed_part_closes_after_size_stop.py` (its rule is gone). Rewrite `tests/test_part_code_size.py` to assert that no warning line appears when the code is 300 lines and the rest is design, Markdown, plans and tests.
   - The steps of issue 960 (stop, allow-large, close again) no longer exist; the first close passes.
2. Start line and guide (SIZE).
   - `test_2_a_part_start_prints_the_size_rule`: `forge task start SHOP/T1` prints the line between `Started` and `Next:`; `forge fix start` prints none.
   - `test_3_the_guide_says_close_only_warns`, parameters `new init` and `previous release upgrade and sync`, with the setup of the current `test_2` in the same file: the synced `.codex` and `.claude` guides keep "Keep each part's builder notes to its goal, files and one test per rule." and "about 400 changed lines", and say that close warns; neither guide contains "Close stops a part over 400 lines" or "Stories approved before this limit keep working".
   - `skill.md` lines 1110-1114 become: "Keep tasks small: at most three Done-when items and about 400 changed lines each, counting additions and removals outside tests, Markdown files, docs/, plans/ and .factory/. Forge prints the rule when a part starts and close warns when a part is larger; split large parts when you plan them." Line 1931 loses its second sentence. Regenerate `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` with `forge sync`, not by hand.
3. Old approvals keep working (SIZE).
   - `test_4_an_approval_with_a_saved_limit_or_size_stop_still_closes`, parameters `new init` and `previous release`. Setup: approve the story, then commit the old fields as the current `test_1` "already approved" case does (`part_line_limit: 400` in the approval and the part; a part state with `stop: {"question": "...", "size": true}` and `status: "hotspot"`). A 401-line part: `forge next` shows no question for the owner and no `forge close ... --resolve` step; `forge close` returns 0 with the warning. `previous release` starts from `_repo_adopted_on_the_previous_release` (`tests/test_upgrade_command.py`).
   - `tests/test_stack_close.py`: remove `_set_part_limit` and its call at line 80; keep the stack cases.
4. Principle 4 (PRINCIPLE).
   - `tests/test_four_principles.py::test_1` and the case at line 126: replace "Rules are stated, not policed" with "costs a lot or is hard to undo" and "something later catches it" in the brief and review prompts; check the same phrases in the cold-read prompt where the test already checks "Four principles govern every change.". Parameters stay `new init` and `previous release`.
   - `AGENTS.md:141` changes by hand (it is outside the forge block). The three templates change in `src/forge/templates`; clients get them through `forge sync` and the prompt files Forge builds at run time.
   - Forge's 13 principles (principle 3, "Gates check outcomes, never rituals") stay as they are.

### New and existing repos

- **New repos** (`forge init`): the new Forge version, so a new approval has no `part_line_limit`; the start line, the close warning and the new principle text from the first story.
- **Existing repos** (on upgrade, after `forge sync`): the new version's behaviour (no size question), and the new guide and instruction text. A story approved earlier keeps its saved limit and any recorded size question in its files; Forge ignores both and writes nothing new for them (case `previous release` of tests 3 and 4).

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| SIZE | A large part warns and never stops | Close prints the warning and goes on; the start line; the approval and part no longer carry the limit; a recorded size stop is ignored; the guide text and its generated copies. | 1, 2, 3 | `src/forge/close.py`, `src/forge/task.py`, `src/forge/approval.py`, `src/forge/repo.py` (`read_state` only), `src/forge/templates/skill.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md`, `tests/test_story_part_size.py`, `tests/test_allowed_part_closes_after_size_stop.py` (delete), `tests/test_part_code_size.py`, `tests/test_stack_close.py` | `test_1` to `test_4` of `tests/test_story_part_size.py`; `tests/test_part_code_size.py::test_1` | | no | |
| PRINCIPLE | Principle 4 becomes three levels | The new wording in `AGENTS.md` and the three shipped instruction files. | 4 | `AGENTS.md` (outside the forge block), `src/forge/templates/brief.md`, `src/forge/templates/review.md`, `src/forge/templates/cold-read.md`, `tests/test_four_principles.py` | `tests/test_four_principles.py::test_1` and the cold-read case | | no | |

The two parts share no file, so they can build at the same time. SIZE is one part because the close change, the start line, the ignored old state and the guide text all prove the same behaviour: a large part goes on without a stop. It is about 40 changed code lines and about 60 test lines, under the 400-line rule.

New moving parts: none

## Notes

- **Scores (F x H >= 2 x C).**
  - Warn at close with the real size: F 3 (every large part), H 1 (a hint), C 1 gives 3 >= 2. Kept.
  - The start line: F 3, H 1, C 1 gives 3 >= 2. Kept, but it measures nothing; see Risks.
  - Ignore an old size stop in `read_state`: F 1 (only stories approved on earlier releases with a recorded size stop), H 2 (an item stuck on a question that no longer exists), C 1 gives 2 >= 2. Kept.
  - A migration that removes saved limits and stops: F 1, H 1, C 3 gives 1 < 6. Cut (decision 2).
  - A warning at the first commit over the limit (a git hook): F 3, H 1, C 3 gives 3 < 6. Cut.
- **Planner choices the owner did not make.**
  1. The warning is at close, with the count, and the start line is a fixed sentence, because a part has changed nothing when it starts. Other options: read the plan's scope paths (they give files, not lines); warn at the first commit over the limit (needs a hook).
  2. The limit is the constant 400; the saved value is never read.
  3. The principle text also changes in the three shipped instruction files, not only `AGENTS.md`, because Forge's own review rule says a process rule that is only in this repo's files is P1. The client-app constitution line (`skill.md:831`) stays.
  4. `forge fix allow-large` stays as it is; only its use as a size-stop release goes.
- **Lane.** This could be a fix: the code touches four files (`close.py`, `task.py`, `approval.py`, `repo.py`), under the five-file limit, and no command, option or setting changes. It is a story only because the shipped principle text and the guide change in more than one place and you asked for a plan. The owner may turn it into a fix with `forge fix start`, then drop this story.
- **Closes** GitHub issue 960.
- No client repo is named in this story's code, tests, texts or commits.
