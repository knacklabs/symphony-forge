# Forge sorts every new idea into a fix, a plan, discovery or the idea list

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- You give Forge an idea in any words: `forge start "<idea>"`. You do not need to know if it is a
  fix, a story or something else. Forge decides.
- Forge reads the repo and picks one of four ways, then tells you in one line what it chose and why:
  - **A fix**, when the idea is small and clear. The fix starts at once and lands by itself.
  - **A plan**, when the idea is big or changes how people use the product. Forge writes the first
    plan, and it comes to you for the usual approval.
  - **Discovery**, when it is not clear what problem the idea solves. Forge asks the questions first.
  - **The idea list**, only when you say "later". Forge never parks an idea by itself: a small,
    important idea is a fix and starts at once.
- You can move an idea with one short instruction, such as "make it a story". Forge moves it and
  keeps what was already written.
- The agent never asks you to choose between a story and a fix. Every new idea goes through this
  one way in, in this repo and in client repos.
- Forge decides with a low-cost model, never one of the most expensive ones.

## Why

On 20 October 2026 the owner said that people give ideas at random and do not know what a story, a
part or a fix is, so Forge must decide, here and in client repos. Today the coordinating agent picks
the lane by a rule in the guide, so the result depends on the agent. Forge checks size only at
close, after the code exists, and a wrong pick costs a round. A light fix also gets fewer review
rounds than a story part, so a wrong pick also changes how much review the work gets.

## Done when

1. **`forge start "<idea>"` answers in one plain line with its choice (a fix, a plan, discovery or the idea list) and the reason.**
2. **A small, clear idea starts a fix with its reason and done-when written from the idea, and the fix goes on to build and land by itself.**
3. **A big idea, or one that changes how people use the product, starts a story with a first plan that comes to the owner for the usual approval.**
4. **An idea with no clear problem starts discovery; an idea goes to the repo's idea list only when the owner says it is for later, and Forge never parks one by itself.**
5. **The owner moves an idea to another lane with one short instruction, and Forge moves it without losing what was written.**
6. **The guide that Forge ships tells the agent to send every new idea through this command and never to ask the human to choose a lane.**

## New and existing repos

- **New repos** (init or adoption): `forge start` works from their first idea, and the guide
  arrives with setup.
- **Existing repos** (on upgrade to this release): the same command works after the upgrade, with
  nothing to set. The guide arrives through `forge sync`. An existing `plans/ideas.md` is kept and
  used as the idea list. `forge fix start` and `forge story new` still work as before. Tested on the
  adopted earlier-release fixture moved to this release.

## Risks

Risks: none one-way. Each part reverts with its pull request. A wrong choice costs one short
instruction to move the idea, and the fix-size check at close still catches a fix that grew too big.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Every Done-when item has exactly one test function, `test_<n>_...`, in one new file,
`tests/test_start_sorts_ideas.py`, which starts with `STORY = "FORGE-INTAKE-1"`. Each test runs the
forge command and never imports forge. Each runs on a repo made by `forge init` (`_fresh_client` in
`tests/test_setup.py`) and on `tests/fixtures/adopted-v1.2.2` moved to this release: copy the
fixture, set its `forge.toml` version to this release and run `forge sync`, as the first half of
`client_item` in `tests/test_close_holds_after_three_blocked_reviews.py` does (test_5 can call
`client_item` itself, since it needs a fix). The sorting model is stubbed the way native reads are
stubbed today: the coordinating session is `native_host` from `tests/test_tools_native_reads.py`
(the `Session` of `tests/test_tools_session_hold.py`), and the model's reply is the `--text` given
to `forge handback`. No other stub is added.

**Words this story pins.**
- The new module is `src/forge/intake.py`. It declares `COMMANDS` with one entry, `start`, and
  `cli.ROUTES` gains `"start": "intake"`. The command takes one argument, the idea in any words, on
  one line (the same `_one_line` rule as `fix start`).
- The sort runs as the session's `explorer` subagent, through the path every session read uses
  today: `native.offer` hands it out and `forge handback` brings the reply back. `native.offer`
  gains `role: str = "reader"`, used in its JSON `role` and its instruction ("Start an explorer as
  a background subagent ..."). The handout's target is the idea cut to a name the way `fix_start`
  cuts its slug (`task.py` line 523), round 1. Its model and effort are
  `repo.worker_models(cfg, "explore", <the session's tool>)`, the same settings `forge sync` gives
  the explorer role: Claude Haiku 5.5 at high effort and the Codex lite model on new repos, and
  lite (Claude's built-in worker default on Claude) on an adopted repo with no explore entry. No
  Forge default names a Fable or Astra model, and this story adds none.
- `pending["result"]` carries `"sort": {"idea": <idea>}`. In `native.handback`, a pending result
  with `sort` goes to `intake.act(top, sort, said)` in place of `story.read_result`. The lock and
  machine place are freed in handback's existing `finally`.
- The prompt is a new template, `src/forge/templates/start.md`. It holds the idea; the fix rule,
  read at run time from `brief.md`'s "A fix stays small" paragraph with `$interfaces` filled from
  `forge.toml` (one home for the rule); the story rule (bigger than a fix, or changes how people use
  the product); the discovery rule (the idea does not say what problem it solves or for whom); and
  "Never park an idea and never judge how important it is: a small idea is a fix even when it
  matters." It tells the model to read the repo read-only to judge the size and to change no files.
- The reply Forge reads: lines `Name: value`, other lines ignored.
  - Every reply: `Lane: fix|story|discovery` and `Reason: <one plain sentence>`.
  - fix: `Why: <one line>`, `Done: <one line>`, `Kind: ui|backend|mechanical`.
  - story: `Key: <KEY>`, `Title: <title>`, `Problem: <one line>`, one or more `Change: <line>`, and
    one to six `Done: <line>`.
  - discovery: `Ask: <the first question>`.
  There is no idea-list lane in the reply: `Lane: later` (or any other value) is a malformed reply.
- The one plain line is the first line printed when the sort finishes:
  `Forge chose a fix: <Reason>`, `Forge chose a plan: <Reason>`, `Forge chose discovery: <Reason>`,
  or `Forge put it on the idea list: you said it is for later.` In a session, the sort finishes at
  the handback, as a session read does.
- Refusal `bad_reply`: `The sorting reply {problem}, so Forge started nothing.` with the next step
  `forge start "<idea>"`. `{problem}` is one of "was empty", "had no Lane line", "named the lane
  <value>", "had no <Name> line". An empty reply covers a model that did not answer. Outside a
  coordinating session, `native.session()`'s existing refusal applies.
- The idea-list words: Forge, not the model, checks the idea for `later`, `not now`, `park` or
  `someday` (whole words, any case). A match goes to the idea list at once, with no model call.

### Done-when details

1. One plain line (SORT).
   - `forge start "<idea>"` with no idea-list word hands the sort out as above. Handback prints the
     line, then the lane's own lines (items 2-4).
   - Normal-use cases: each of the four lanes; a malformed reply; an empty reply; a second
     `forge start` of the same idea after a refusal, which hands out again.
   - Test: `test_1_start_answers_in_one_plain_line_with_its_choice_and_reason`, on both repos. The
     handout JSON has role `explorer`, round 1, a prompt with the five-code-files sentence and the
     reply lines, and the explore model: `claude-haiku-5-5` at `high` on the new repo, and the
     explorer's adopted settings on the adopted fixture (the pair test_4 of
     `tests/test_read_only_model_selection.py` asserts). The model name matches neither `fable`
     nor `astra`. For a fix, a plan and a discovery reply, the handback's first line matches
     `^Forge chose (a fix|a plan|discovery): ` followed by the Reason, with no backtick and no
     `--`. A reply with no `Done:` line and an empty reply each exit 1 with the `bad_reply` text and
     `Next: forge start "<idea>"`; no `fix/` or `story/` branch exists after them, and the same
     `forge start` hands out again.
2. Fix (SORT).
   - `intake.act` runs `task.fix_start` with `why`, `done` and `kind` from the reply and
     `slug=None`. `fix_start` prints `Next: forge {next} {name}`, with `next` from
     `getattr(args, "next", "work")`; intake passes `"land"`. So the coordinator is told to land
     the fix, and the guide (item 6) says to run land in the background and watch it, as today.
     `forge start` itself does not wait for the build.
   - Normal-use cases: a backend fix and a ui fix; a fix name already taken (fix_start's existing
     suffix line).
   - Test: `test_2_a_small_clear_idea_starts_a_fix_that_lands`, on both repos. Reply lane fix. The
     fix's state has the reply's `why`, `done_when` and `fix_kind`, `fix/<name>` exists, and the
     last line is `Next: forge land <name>`. Then `forge next` names that fix.
3. Plan (SORT).
   - `intake.act` runs `story.new` with the reply's `Key` and `Title` and no `--from-fix`. Then, in
     the story's worktree, it writes the reply into the owner half: the `Change:` lines as bullets
     under `## What changes for you`, the `Problem:` line as `## Why`, and the `Done:` lines as the
     numbered bold Done-when items. It commits that with `repo.commit_state`. `story.new`'s own
     `Next: write plans/<KEY>.md there, then forge read <KEY>` stays the next step: the coordinator
     fills the builders' half, then the usual cold read and approval follow.
   - `story.py` is at the 1,200-line ceiling, so all new story code goes in `intake.py`.
   - Normal-use cases: a new key; a key already taken (`story.new`'s existing refusal).
   - Test: `test_3_a_big_idea_starts_a_story_with_a_first_plan`, on both repos. `plans/<KEY>.md`
     on `story/<KEY>` has the title, each Change line, the Problem and each Done line, and none of
     the template's `<What the people who use this will notice` placeholder. Its state is
     `planning`. The output ends with the `forge read <KEY>` step, and `forge next` names the read.
4. Discovery and the idea list (MOVE).
   - Discovery: `intake.act` writes nothing. It prints the line, `Ask the human: <Ask>`, and
     `Next: run Discovery from the guide, then forge start "<the problem in their words>"`.
   - Idea list: an idea with an idea-list word appends `- <YYYY-MM-DD>: <idea>` to `plans/ideas.md`
     in the main checkout (`machine.main_checkout`), creating the file on first use and keeping
     existing lines. Nothing is committed then, since the default branch takes no commits. The
     next fix or story that `forge start` starts carries the lines not yet in the default branch's
     file into its own first commit, and the main checkout's file goes back to the default
     branch's version. This is the guide's "batch into the next fix", done by the command.
   - Forge never parks an idea itself: with no idea-list word, the model is asked, its lanes are
     only fix, story and discovery, and a `Lane: later` reply is refused (item 1).
   - Normal-use cases: "Later: add dark mode"; "not now" in the middle of the idea; an adopted repo
     with an existing `plans/ideas.md`; a small, important idea with no idea-list word.
   - Test: `test_4_unclear_ideas_start_discovery_and_only_later_ideas_go_to_the_list`, on both
     repos.
     - A discovery reply prints the question; `git status` and the branch list are unchanged.
     - `forge start "Later: add dark mode"` makes no handout, prints the idea-list line and adds
       the dated line; on the adopted fixture an earlier line in `plans/ideas.md` stays.
     - `forge start "Fix the login typo, this matters a lot"` hands out (no idea-list line), and
       `plans/ideas.md` is unchanged. A fix reply starts the fix, whose first commit holds the
       dark-mode line, and the main checkout's `plans/ideas.md` is back to the default branch's.
     - A `Lane: later` reply to that idea is refused as `bad_reply`.
5. Moves (MOVE). No new command or option. The guide maps the owner's words to existing commands:
   - "Make it a story" (a fix): add the key to the fix's roadmap and commit it, then
     `forge story new <KEY> --from-fix <fix>`, which keeps the fix's why, done-when and changed
     files, as today.
   - "Do it later" (a fix): `forge fix drop <fix> --because "The owner wants it later"`, then
     `forge start "Later: <its why> (kept on fix <fix>)"`. The fix's branch keeps the work, and
     `forge fix drop <fix> --undo` brings it back.
   - "Just fix it" (a plan not yet approved): `forge fix start "<its Why>" --done "<its first
     Done-when>"`. The plan stays on its story branch. Forge has no command that removes a story,
     and this story adds none.
   - "Do it now" (an idea-list entry): `forge start "<the entry without the later word>"`, and
     remove the entry in that item's branch, as the guide already says.
   - Normal-use cases: each of the four, on a fix or plan that `forge start` made.
   - Test: `test_5_one_short_instruction_moves_an_idea_and_keeps_what_was_written`, with the
     parameter `move` in ("story", "later", "fix"), the new repo for all and the adopted fixture
     for "story" (`client_item(env, tmp_path, previous=True)` gives the fix there).
     - story: after `forge start` made a fix, the commands above give `plans/<KEY>.md` whose Why and
       Done-when 1 are the fix's why and done-when.
     - later: the drop and `forge start` leave `origin/fix/<fix>` in place and add the dated line.
     - fix: after `forge start` made a plan, `forge fix start` with its Problem and first Done line
       starts the fix, and `plans/<KEY>.md` on `story/<KEY>` is unchanged.
6. The shipped guide (MOVE).
   - `skill.md`'s command table: the rows "Plan a new story" and "Fix this small thing" become one
     row, `"I have an idea", "Fix this" or "Plan this"` -> `forge start "<their words>"`, and the
     four move rows of item 5 are added next to "This fix is too big" (which stays). One short
     paragraph says: send every new idea through `forge start`; never ask the human whether it is
     a story or a fix; when the answer is a fix, run its `forge land` in the background and watch
     it. "Save decisions and ideas" says that `forge start` keeps `plans/ideas.md`.
   - The AGENTS template (`src/forge/templates/adapters/AGENTS.md`): flow step 1 and "The lanes"
     say that every idea starts with `forge start "<idea>"` and Forge picks the lane, with the same
     five-file rule. `brief.md` does not change: workers don't take new ideas.
   - `forge sync` writes `.claude/skills/forge/`, `.codex/skills/forge/`, the AGENTS block and
     `docs/commands.md` (the `start` listing). Existing repos get it on upgrade plus sync.
   - Test: `test_6_the_shipped_guide_sends_every_idea_through_start`. On the new repo after init,
     and on the adopted fixture after its sync, both hosts' `SKILL.md` and `AGENTS.md` have
     `forge start "<`, the never-ask sentence and the four move rows, and the old "Plan a new
     story" and "Fix this small thing" rows are gone. `docs/commands.md` lists `forge start`.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| SORT | One way in | `forge start` hands the idea to the session's explorer on the explore model, reads the strict reply, prints the one line, and starts a fix (next step: land) or a story with a first owner-half draft. Malformed and empty replies refuse. The command ceiling moves to 25. | 1, 2, 3 | `src/forge/intake.py` (new), `src/forge/cli.py`, `src/forge/native.py`, `src/forge/task.py`, `src/forge/templates/start.md` (new), `tests/test_rules.py`, `docs/commands.md` (regenerated by `forge sync`) | `tests/test_start_sorts_ideas.py` (`test_1`, `test_2`, `test_3`); `tests/test_rules.py` test_5 ceiling to 25 | | no | |
| MOVE | Discovery, later and the guide | The discovery lane, the idea list from the person's words with its carry into the next item, the move mapping, and the shipped guide and AGENTS block. | 4, 5, 6 | `src/forge/intake.py`, `src/forge/templates/start.md`, `src/forge/templates/skill.md`, `src/forge/templates/adapters/AGENTS.md`, `AGENTS.md`, `README.md`, `docs/commands.md`, `.claude/skills/forge/`, `.codex/skills/forge/` (the last four regenerated by `forge sync`) | `tests/test_start_sorts_ideas.py` (`test_4`, `test_5`, `test_6`); guide tests that quote the removed rows (search the tests for "Plan a new story" and "Fix this small thing") | SORT | no | |

New moving parts: none

## Notes

- **Command ceiling.** `test_5_forge_stays_small` in `tests/test_rules.py` reads the `{...}` list
  from `forge --help` and asserts `len(commands) <= 24`. Today there are exactly 24, so `start` makes
  25. This story raises the ceiling to 25 with the comment "FORGE-INTAKE-1 adds start", as
  FORGE-MOD-1 (lanes) and FORGE-BOARD-3 (assign) did, because approved Done-when item 1 names the
  command. It removes process in return: the coordinator's lane choice and two guide rows go.
  The fold that would keep 24 is `forge task start <KEY>/<TASK>` into `forge start <KEY>/<TASK>`.
  It is not taken here: it changes a command that about 60 files use, and the approved text does
  not name it.
- **Reused, not rebuilt.** The session handout and handback (`native.offer`, `native.handback`),
  the explorer's model choice (`repo.worker_models(cfg, "explore", ...)`), `task.fix_start`,
  `story.new`, `story new --from-fix`, `fix drop` and `--undo`, the `brief.md` fix-size rule, and
  `forge sync` for the generated files. There is no Codex app-server or Claude SDK call: the sort
  always runs in the coordinating session, the way session reads run.
- **Line ceilings.** `story.py` and `close.py` are at 1,200 lines; this story changes neither.
- **A builder must not:**
  - add a `forge start` option, a `forge.toml` setting, a stored lane record or a lane check at
    close;
  - let the model choose the idea list, or let Forge park an idea by size or importance;
  - commit on the default branch (the idea list waits uncommitted until the next start);
  - add a Fable or Astra model, or any new default model;
  - add a command that removes a story;
  - change `brief.md`, `story.py` or `close.py`.
- `README.md`'s command table lists `forge ask`, which does not exist. MOVE adds the `forge start`
  row. It leaves the `forge ask` row as it is and reports it.
- No client repo is named anywhere in this story's code, tests, texts or commits.
