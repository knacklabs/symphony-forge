# Forge sorts every new idea into a fix, a plan, discovery or the idea list

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- You give Forge an idea in any words: `forge start "<idea>"`. You do not need to know if it is a
  fix, a story or something else. Forge decides.
- Forge reads the repo and picks one of four ways, then tells you in one line what it chose and why:
  - **A fix**, when the idea is small and clear. The fix starts at once and is built, tested and
    reviewed by itself. It merges by itself where the repo lets the agent merge, and otherwise
    waits for your merge as usual.
  - **A plan**, when the idea is big or changes how people use the product. Forge writes the first
    plan, and it comes to you for the usual approval.
  - **Discovery**, only when Forge cannot guess what problem the idea solves. Discovery asks you
    one question. When Forge can guess, it picks a fix or a plan and says its guess in the reason,
    and you correct it with one instruction.
  - **The idea list**, only when you say "later". Forge never parks an idea by itself: a small,
    important idea is a fix and starts at once.
- You can move an idea with one short instruction, such as "make it a story". Forge moves it and
  keeps what was already written. The old item leaves the board, so one idea is one item.
- The agent never asks you to choose between a story and a fix. Every new idea goes through this
  one way in, in this repo and in client repos.
- Forge decides with the repo's explore model, which is a low-cost model unless the repo's
  settings choose another. It reads the repo's recorded decisions and review rules first, so it does
  not ask again what is already settled.

## Why

On 20 October 2026 the owner said that people give ideas at random and do not know what a story, a
part or a fix is, so Forge must decide, here and in client repos. Today the coordinating agent picks
the lane by a rule in the guide, so the result depends on the agent. Forge checks size only at
close, after the code exists, and a wrong pick costs a round. A light fix also gets fewer review
rounds than a story part, so a wrong pick also changes how much review the work gets.

## Done when

1. **`forge start "<idea>"` answers in one plain line with its choice (a fix, a plan, discovery or the idea list) and the reason.**
2. **A small, clear idea starts a fix with its reason and done-when written from the idea, and the fix goes on to build, test and review by itself, then merges as the repo's merge setting allows.**
3. **A big idea, or one that changes how people use the product, starts a story with a first plan that comes to the owner for the usual approval.**
4. **An idea with no clear problem starts discovery; an idea goes to the repo's idea list only when the owner says it is for later, and Forge never parks one by itself.**
5. **The owner moves an idea to another lane with one short instruction, and Forge moves it without losing what was written and leaves one item on the board.**
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
`tests/test_setup.py`) and on `tests/fixtures/adopted-v1.2.2` moved to this release. To move the
fixture, copy it, set its `forge.toml` version to this release and run `forge sync`, as the first
half of `client_item` in `tests/test_close_holds_after_three_blocked_reviews.py` does. test_5 can
call `client_item` itself, since it needs a fix. The adopted fixture is `stage = "live"` with
`merge = "human"`. A repo fresh from `forge init` is a client prototype before sign-off: it takes
no stories, and its agent merges. Where a test needs stories on the new repo, it first records the
sign-off with `_signed_off` from `tests/test_proto_gate.py`. The sorting model is stubbed the way
native reads are stubbed today. The coordinating session is `native_host` from
`tests/test_tools_native_reads.py` (the `Session` of `tests/test_tools_session_hold.py`), and the
model's reply is the `--text` given to `forge handback`. `forge land` uses the stubs of
`tests/test_land.py`. No other stub is added.

**Words this story pins.**
- The new module is `src/forge/intake.py`. Its `COMMANDS` declares `start` (SORT) and
  `story drop` (MOVE). `cli.ROUTES` gains `"start": "intake"` and `"story drop": "intake"`.
  `story drop` sits under the existing `story` group, so the top-level count is 25 (Notes).
  `start` takes one argument: the idea in any words, on one line (the `_one_line` rule of
  `fix start`).
- The sort runs as the session's `explorer` subagent, through the path every session read uses:
  `native.offer` hands it out and `forge handback` brings the reply back.
  - `native.offer` gains `role: str = "reader"`, used in its JSON `role` and in its instruction
    ("Start an explorer as a background subagent ...").
  - The handout's target is the idea cut to a name, the way `fix_start` cuts its slug (`task.py`
    line 523). It is round 1.
  - Its model and effort are `repo.worker_models(cfg, "explore", <the session's tool>)`: the same
    settings `forge sync` gives the explorer role.
  - `pending["result"]` carries `"sort": {"idea": <idea>, "asked_again": False}`.
  - In `native.handback`, a pending result with `sort` goes to
    `intake.act(Path(pending["checkout"]), path, pending, said)`, in place of `story.read_result`.
    It acts in the saved checkout, as reads do, so a sort handed out from a fix's worktree starts
    its fix there. `act` returns True only when it asks once more (below). Handback then keeps the
    place, as it does for the worker's commit nudge. Otherwise handback's existing `finally` frees
    it.
- The prompt is a new template, `src/forge/templates/start.md`. It holds the following:
  - The idea.
  - The fix rule, read at run time from `brief.md`'s "A fix stays small" paragraph, with
    `$interfaces` filled from `forge.toml`. The rule keeps one home.
  - The plan rule: bigger than a fix, or it changes how people use the product. A repo where
    `repo.is_prototype(top)` is true gets no plan lane. Its prompt says that before sign-off every
    idea is a prototype fix, which is how the guide's Prototype section works.
  - Discovery: only when no reasonable problem can be guessed. Otherwise the model picks a fix or
    a plan and states its guess in the Reason. Discovery asks exactly one question.
  - The idea list: only when the person clearly asks to put the idea off ("later", "not now", "park
    it"). A "later" that describes what the product does, as in "Shoppers can save a basket and
    come back to it later", is not deferral. "Never judge how important an idea is: a small idea is
    a fix even when it matters."
  - "Read the repo read-only first: the recorded decisions in `docs/decisions/` (where
    `forge decision new` writes them), the `## Review rules` section of `AGENTS.md`, and the code
    the idea touches. Change no files."
  - The reply lines below.
- The reply Forge reads is lines of the form `Name: value`. Forge ignores other lines.
  - Every reply has `Lane: fix|plan|discovery|later` and `Reason: <one plain sentence>`.
  - fix: `Why: <one line>`, `Done: <one line>`, `Kind: ui|backend|mechanical`.
  - plan: `Key: <KEY>`, `Title: <title>`, `Problem: <one line>`, one or more `Change: <line>`, and
    one to six `Done: <line>`.
  - discovery: `Ask: <the one question>`.
  - later: nothing more. Forge writes the idea in the person's own words.
  Forge does no keyword matching on the idea.
- A reply is malformed in these cases: it is empty; it has no `Lane` line; it names a lane not
  offered (`plan` in a prototype repo, or any other value); or it lacks a line its lane needs. The
  first malformed reply is not refused. `act` records `asked_again: True` in the pending record and
  prints `Send this to subagent <id>, then hand back again: Reply again in the exact form: <problem>.`
  If the second reply is malformed too, Forge refuses with `bad_reply`:
  `The sorting reply {problem}, so Forge started nothing.` The next step is
  `forge start "<idea>"`. An empty reply covers a model that did not answer. Outside a coordinating
  session, `native.session()`'s existing refusal applies.
- The one plain line is the first line `act` prints. Nothing starts before it: no branch, no fix
  and no file write. It is `Forge chose a fix: <Reason>`, `Forge chose a plan: <Reason>`,
  `Forge chose discovery: <Reason>` or `Forge put it on the idea list: <Reason>`.

### Done-when details

1. One plain line (SORT).
   - `forge start "<idea>"` hands the sort out. Handback prints the line, then the lane's own lines
     (items 2-4).
   - Normal-use cases:
     - each of the four lanes;
     - one malformed reply followed by a good one;
     - two malformed replies;
     - an empty reply;
     - a new `forge start` of the same idea after a refusal, which hands it out again.
   - Test: `test_1_start_answers_in_one_plain_line_with_its_choice_and_reason`, on both repos.
     - The handout JSON has the role `explorer` and round 1.
     - Its prompt has the five-code-files sentence, the `docs/decisions/` and `## Review rules`
       sentence, and the reply lines.
     - Its model and effort are the explorer's: `claude-haiku-5-5` at `high` on the new repo, and
       on the adopted fixture the pair that test_4 of `tests/test_read_only_model_selection.py`
       asserts.
     - For a fix reply, a plan reply (on the signed-off new repo and on the adopted fixture) and a
       discovery reply, the first line of the handback's output matches
       `^Forge chose (a fix|a plan|discovery): `, followed by the Reason, with no backtick and no
       `--`.
     - A fix reply with no `Done:` line gets the "send this to subagent" line and exit 0. No
       `fix/` branch exists after it. A good reply on the same round then starts the fix.
     - Two malformed replies, and an empty reply followed by a malformed one, each end with exit
       1, the `bad_reply` text and `Next: forge start "<idea>"`. No `fix/` or `story/` branch
       exists afterwards, and the same `forge start` hands the idea out again.
2. Fix (SORT).
   - `intake.act` prints the line, then runs `task.fix_start` with `why`, `done` and `kind` from
     the reply and `slug=None`. `fix_start` prints `Next: forge {next} {name}`, with `next` taken
     from `getattr(args, "next", "work")`, and intake passes `"land"`. That tells the coordinator to
     land the fix, and the guide (item 6) says to run land in the background and watch it.
     `forge start` itself does not wait for the build. Land builds, tests, reviews and then merges
     only where `close.merger` says the agent merges. Otherwise it stops at "ready; a human merges
     its pull request", as it does today.
   - Normal-use cases:
     - a backend fix and a ui fix;
     - a fix name already taken (fix_start's existing suffix line);
     - a prototype repo, where a big idea is a prototype fix and fix_start records the prototype
       allowance.
   - Test: `test_2_a_small_clear_idea_starts_a_fix_that_lands_as_the_merge_setting_allows`, on both
     repos.
     - Reply lane fix. The fix's state has the reply's `why`, `done_when` and `fix_kind`. `fix/<name>`
       exists, and the last line is `Next: forge land <name>`.
     - With the stubs of `tests/test_land.py`, `forge land <name>` merges on the new repo (an
       unsigned prototype, so the agent merges).
     - On the adopted fixture (`merge = "human"`), land ends with
       `<name> is ready; a human merges its pull request:`, and the pull request is not merged.
3. Plan (SORT).
   - `intake.act` prints the line, then runs `story.new` with the reply's `Key` and `Title` and no
     `--from-fix`. Then, in the story's worktree, it writes the reply into the owner half:
     - the `Change:` lines as bullets under `## What changes for you`;
     - the `Problem:` line as `## Why`;
     - the `Done:` lines as the numbered bold Done-when items.
     It commits that with `repo.commit_state`. `story.new`'s own
     `Next: write plans/<KEY>.md there, then forge read <KEY>` stays the next step: the coordinator
     fills the builders' half, and the usual cold read and approval follow.
   - In a prototype repo the plan lane is not offered (Words). `story.py` does not change.
   - Normal-use cases: a new key; a key already taken (`story.new`'s existing refusal); a prototype
     repo.
   - Test: `test_3_a_big_idea_starts_a_story_with_a_first_plan`, on the signed-off new repo and on
     the adopted fixture.
     - `plans/<KEY>.md` on `story/<KEY>` has the title, each Change line, the Problem and each Done
       line. It has none of the template's `<What the people who use this will notice`
       placeholder.
     - Its state is `planning`. The output ends with the `forge read <KEY>` step, and `forge next`
       names the read.
     - On the unsigned new repo, the prompt has no plan lane, and a `Lane: plan` reply gets the
       "send this to subagent" line.
4. Discovery and the idea list (MOVE).
   - Discovery: `intake.act` writes nothing. It prints the line, then `Ask the human: <Ask>`, then
     `Next: forge start "<the idea with the human's answer>"`.
   - Idea list (lane `later`): `intake.act` appends `- <YYYY-MM-DD>: <idea>` to `plans/ideas.md` in
     the main checkout (`machine.main_checkout`). It creates the file on first use and keeps
     existing lines. Nothing is committed then, because the default branch takes no commits.
   - The carry: the next fix or story that `forge start` starts takes the waiting lines with it.
     - `act` compares `story.worktrees(top)` before and after `fix_start` or `story.new`, to find
       the new worktree.
     - It appends to that worktree's `plans/ideas.md` the main checkout's lines that the file does
       not already have. It commits them there with `repo.commit_state("Add ideas for later",
       "plans/ideas.md", top=<worktree>)`, a follow-up commit after the start commit.
     - It then puts the main checkout's file back to the default branch's version, or deletes it
       when the default branch has none.
     - Only `intake.py` changes for this.
   - Forge never parks an idea itself: it does no keyword matching, and the prompt asks for the
     idea list only when the person asks to put the idea off.
   - Normal-use cases:
     - "Do this later: add dark mode";
     - "Shoppers can save a basket and come back to it later", which is product behaviour and not
       deferral;
     - an adopted repo with an existing `plans/ideas.md`;
     - a small, important idea;
     - an idea that a guess makes clear enough for a fix, whose Reason states the guess.
   - Test: `test_4_unclear_ideas_start_discovery_and_only_ideas_put_off_go_to_the_list`, on both
     repos.
     - A discovery reply prints one question. `git status` and the branch list do not change.
     - `forge start "Do this later: add dark mode"` with a later reply prints the idea-list line
       and adds the dated line. On the adopted fixture, an earlier line in `plans/ideas.md` stays.
     - `forge start "Shoppers can save a basket and come back to it later"` hands out a prompt that
       has the not-deferral sentence. A plan reply then starts the story (on the signed-off new
       repo and on the adopted fixture). The story's branch has a follow-up commit holding the
       dark-mode line, and the main checkout's `plans/ideas.md` is back to the default branch's
       version.
5. Moves (MOVE).
   - New: `forge story drop <KEY> --because "<reason>"`, in `intake.py`, in the shape of
     `fix drop`.
     - It drops only a story still in planning: no approval in its state and no started task.
       Otherwise it refuses with
       `<KEY> is approved or has started parts, so it can't be dropped.` and the next step
       `forge next`.
     - It sets `status: dropped` and `drop: {because, by, at}` (the same fields as fix drop) in the
       story's state on its branch, commits, and pushes.
     - It closes the branch's open pull request, if there is one, with the reason. It removes the
       clean worktree and local branch, and its remote branch keeps the doc.
     - It has no `--undo`.
   - `nextstep.py` skips a story whose state is `dropped`, both in the story worktrees and on
     remote story branches (the loops at lines 482 and 488). `board.py` already leaves out every
     dropped state (line 289); test_5 proves that it does.
   - The guide maps the owner's words to commands:
     - "Make it a story" (a fix): add the key to the fix's roadmap and commit it, run
       `forge story new <KEY> --from-fix <fix>`, then run
       `forge fix drop <fix> --because "Moved to the plan <KEY>"`. The last step stops the
       pushed fix branch from showing as a second item.
     - "Make it a fix" or "Just fix it" (a plan in planning): run
       `forge fix start "<its Problem>" --done "<its first Done-when>"`, then
       `forge story drop <KEY> --because "Moved to the fix <fix>"`.
     - "Do it later" (a fix): run `forge fix drop <fix> --because "The owner wants it later"`, then
       `forge start "Do this later: <its why> (kept on fix <fix>)"`. `fix drop --undo` brings the
       fix back.
     - "Do it now" (an idea-list entry): run `forge start "<the entry>"`, and remove the entry in
       the new item's branch, as the guide already says.
   - Normal-use cases: each of the four moves, on an item that `forge start` made.
   - Test: `test_5_one_short_instruction_moves_an_idea_and_leaves_one_item`, with the parameter
     `move` in ("story", "fix", "later"). It runs on the new repo for every move (signed off for
     "story" and "fix"), and on the adopted fixture for "fix" (`client_item` does not apply there,
     since the move starts from a plan).
     - story: the commands above give a `plans/<KEY>.md` whose Why and Done-when 1 are the fix's.
       `forge next` and `forge board --json` show the story and not the fix.
     - fix: the fix has the plan's Problem and first Done line. `plans/<KEY>.md` stays on
       `origin/story/<KEY>`. `forge next` and `forge board --json` show the fix and not the story.
       `forge story drop` on an approved story refuses with the text above.
     - later: `origin/fix/<fix>` stays, the dated line is added, and the fix is gone from
       `forge next` and the board.
6. The shipped guide (MOVE).
   - `skill.md`'s command table:
     - The rows "Plan a new story" and "Fix this small thing" become one row: `"I have an idea",
       "Fix this" or "Plan this"` maps to `forge start "<their words>"`.
     - The four move rows of item 5 go next to "This fix is too big", which stays.
     - One short paragraph says: send every new idea through `forge start`; never ask the human
       whether it is a story or a fix; when the answer is a fix, run its `forge land` in the
       background and watch it.
   - "Planning a story" starts from `forge start` in place of `forge story new`.
   - "Save decisions and ideas" says that `forge start` keeps `plans/ideas.md`.
   - `nextstep._idle`'s two separate `forge story new` and `forge fix start` steps become one
     `Next: forge start "<idea>"`.
   - The AGENTS template (`src/forge/templates/adapters/AGENTS.md`): flow step 1 and "The lanes" say
     that every idea starts with `forge start "<idea>"` and that Forge picks the lane, with the
     same five-file rule.
   - `brief.md` does not change, because workers do not take new ideas.
   - `forge sync` writes `.claude/skills/forge/`, `.codex/skills/forge/` and the AGENTS block.
     Existing repos get them on upgrade plus sync.
   - Test: `test_6_the_shipped_guide_sends_every_idea_through_start`.
     - On the new repo after init, and on the adopted fixture after its sync, both hosts'
       `SKILL.md` and the repo's `AGENTS.md` have `forge start "<`, the never-ask sentence and the
       four move rows.
     - The "Plan a new story" and "Fix this small thing" rows are gone.
     - `forge next` on the new repo with nothing in progress names `forge start`.
     - `docs/commands.md` is not checked: only Forge's own repo gets it.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| SORT | One way in | `forge start` hands the idea to the session's explorer on the explore model and reads the strict reply. It asks once more on a malformed reply, then refuses. It prints the one line, then starts a fix (next step: land) or, where stories are allowed, a story with a first owner-half draft. The command ceiling moves to 25. | 1, 2, 3 | `src/forge/intake.py` (new), `src/forge/cli.py`, `src/forge/native.py`, `src/forge/task.py`, `src/forge/templates/start.md` (new), `tests/test_rules.py`, `docs/commands.md` (regenerated by `forge sync`) | `tests/test_start_sorts_ideas.py` (`test_1`, `test_2`, `test_3`); `tests/test_rules.py` test_5 ceiling to 25 | | no | |
| MOVE | Discovery, later, moves and the guide | The discovery and idea-list lanes, the carry of waiting ideas into the next item, `forge story drop`, the move mapping, the single idle step in `forge next`, and the shipped guide and AGENTS block. | 4, 5, 6 | `src/forge/intake.py`, `src/forge/cli.py`, `src/forge/nextstep.py`, `src/forge/templates/start.md`, `src/forge/templates/skill.md`, `src/forge/templates/adapters/AGENTS.md`, `AGENTS.md`, `README.md`, `docs/commands.md`, `.claude/skills/forge/`, `.codex/skills/forge/` (the last four regenerated by `forge sync`) | `tests/test_start_sorts_ideas.py` (`test_4`, `test_5`, `test_6`); guide and next tests that quote the replaced rows or the idle steps (search the tests for "Plan a new story", "Fix this small thing" and "No story or fix is in progress") | SORT | no | |

New moving parts: none

## Notes

- **Command ceiling (decided 20 October 2026).** `test_5_forge_stays_small` in
  `tests/test_rules.py` reads the `{...}` list from `forge --help` and asserts
  `len(commands) <= 24`. There are 24 today. SORT raises the ceiling to 25 with the comment
  "FORGE-INTAKE-1 adds start", as FORGE-MOD-1 (lanes) and FORGE-BOARD-3 (assign) did. `task start`
  is not folded into `start`. `story drop` is a subcommand of `story`, so it does not count toward
  the ceiling.
- **Reused, not rebuilt.**
  - the session handout and handback (`native.offer`, `native.handback`, the commit nudge's
    keep-the-place shape);
  - the explorer's model choice (`repo.worker_models(cfg, "explore", ...)`);
  - `task.fix_start`, `story.new`, `story new --from-fix`, `fix drop` and `--undo`, and
    `fix drop`'s record fields for `story drop`;
  - the `brief.md` fix-size rule and `repo.is_prototype`;
  - `close.merger` and land's existing stop for a human merge;
  - `forge sync` for the generated files.
  - There is no Codex app-server or Claude SDK call: the sort always runs in the coordinating
    session, the way session reads run.
- **Line ceilings.** `story.py` and `close.py` are at 1,200 lines, and this story changes neither.
  All new story code is in `intake.py`.
- **A builder must not:**
  - add a `forge start` option, a `forge.toml` setting, a stored lane record or a lane check at
    close;
  - match words in the idea, or let Forge park an idea by size or importance;
  - commit on the default branch (waiting ideas stay uncommitted until the next start);
  - add a model restriction or a new default model;
  - add `--undo` to `story drop`;
  - change `brief.md`, `story.py` or `close.py`.
- `README.md`'s command table lists `forge ask`, which does not exist. MOVE adds the `forge start`
  row, leaves the `forge ask` row as it is, and reports it.
- No client repo is named anywhere in this story's code, tests, texts or commits.
