# Show the full text of the last close's findings without running close again

1 part · Risks: none one-way · New moving parts: none

## What changes for you

- After a close finds problems, the agent can print the full text of those findings again with `forge close <item> --show`. It prints the same findings that the close printed, word for word, for a part of a story or for a fix.
- This runs no tests and no review, and it changes nothing: no commit, no push, no change to the pull request.
- Forge gets no new command. This is a new option on close, because Forge already has the most commands it allows (25).
- The agent's guide names the new option, so the agent uses it instead of a second close.
- What each repo gets. A new repo gets the option and the guide line from the start. An existing repo gets both when it upgrades to the release with this change; the guide line comes with the upgrade's normal refresh. The option also works for findings from closes that ran before the upgrade, because close already keeps the full text of each finding. No saved record changes.
- Cost. No model call is added. Each use saves a second close: a full test run on a repo that tests on the laptop, a push, and sometimes a new model review.

Design: none. Nothing on the board or in the pull request changes.

## Why

When a close finds problems, it prints the full text of each finding once. The pull request shows only the titles. No command shows the full text again, so an agent that lost the output runs close again only to read it. That second close runs the tests again, pushes again, and can run a new review. A client repo in daily use reported this twice. Today the only workaround is to read Forge's saved record files by hand, and agents do not know where they are.

## Done when

1. **`forge close <item> --show` prints the last close's review result with the full text of every finding that close printed, for a part or a fix, and runs no tests, no review, and changes nothing.**

## Risks

Risks: none one-way. The part reverts with its pull request. It changes no saved record and no file in a client repo except the guide line.

Trade-off, in plain words: the option shows the last saved result. If the agent changed the code after that close, the findings can be out of date. That is the same as reading the earlier close's output.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Source: GitHub issues #1599 and #1026, from the client repo in daily use. Name no client in code, tests, texts or commits.

### What exists (evidence)

Checked in this worktree on 16 Nov 2026 (base `63d634eb6`, Forge v1.2.40). The builder checks each name again before it starts.

- **Where the full text is kept.** Close saves the whole review result in the item's committed state file before it prints anything: `state.update(review=result, ...)` then `_save(...)` in `close.close` (`src/forge/close.py:419-426`), then `_push` (`:429`), then the print block (`:434-451`). The file is `repo.state_path(item)` (`src/forge/repo.py:1110-1121`): `.factory/stories/<KEY>/tasks/<TASK>.json` for a part, `.factory/fixes/<name>.json` for a fix. Each entry of `review.findings` has `title`, `file`, `line`, `priority` and the full `body`; `review.dismissals` lists dismissed finding numbers. The same shape holds for parts and fixes. In this repo all 311 saved findings across `.factory/fixes/*.json` and `.factory/stories/*/tasks/*.json` carry a non-empty `body`, so items closed on earlier releases are covered with no conversion.
- **The issue's premise needs one correction.** The issue says the text lives only in `.git/forge/threads/{task|fix}/<item>.brief.md`. That file is written by `forge work`, not by close, and only for a session subagent run (`native.hand_out`, `src/forge/native.py:137-141`); it holds only the open blocking findings (`worker._fix_round`, `src/forge/worker.py:536-546`, and `:643-649`, `:694-696`). Right after a close it still holds the previous round's brief. The committed state file is the one current home of the full text.
- **What a second close costs.** It merges the default branch, runs the local tests on a `test_place = "local"` repo (`close.py:385-395` when the review is reused, `:350-383` otherwise), pushes and republishes the pull request. It reuses the saved review only when the change fingerprints are unchanged (`close.py:304-316`); otherwise it runs a new model review.
- **What the pull request holds.** `close._block` (`close.py:1100-1140`) writes each blocking finding as its title, `file:line` and "blocks the merge"; only advisory findings carry body text, flattened to one line and folded away.
- **What `forge next` shows.** For a `fixing` item, only the titles of blocking findings (`src/forge/nextstep.py:1131-1137`). `forge next` takes no arguments.
- **The ceilings.** `tests/test_rules.py::test_5_forge_stays_small` allows at most 25 top-level commands; `forge --help` lists 25 today. It also refuses any module over 1,200 lines: `src/forge/close.py` is at 1,200, `review.py` 1,199, `board.py` 1,197, `nextstep.py` 1,193; `src/forge/review_skip.py` is 97.
- **The print block's helpers.** `review_skip.label` (`src/forge/review_skip.py:45-49`) already gives close's `Review: <label>.` line. `review_skip` imports `review`; `review.blocking` (`src/forge/review.py:189-195`) gives the open blocking findings; `score.priority`, `score.holds` and `score.RARE` come from `src/forge/score.py`, which imports nothing from Forge, so `review_skip` can import it with no cycle.
- **Where close's options show.** The `COMMANDS` declaration at the end of `close.py` (`:1189-1200`): its `args` and its `listing` row. `forge sync` writes the listing rows into `docs/commands.md` in this repo (`src/forge/sync.py:714-718`); `tests/test_split_page.py::test_4_sync_keeps_the_command_page_current` checks that page. The coordinator guide's close rows are `src/forge/templates/skill.md:118-119`; this repo's copies `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` have the same rows today.

### Options weighed

1. **A new command, `forge findings <item>`.** Rejected: Forge is at its 25-command ceiling, so `test_5_forge_stays_small` fails, and principle 6 asks for no growth there.
2. **Close prints the saved file's path.** One line, but the path prints in the same output that the agent lost, the file is JSON in which the agent must work out which findings are open from the dismissal numbers, and the file may sit in another worktree. The brief file is wrong for this (see the premise correction). Rejected.
3. **`forge next` or `forge board --json` carries the full text.** `forge next` takes no item and covers every item, also in the hook that adds context to each agent turn, so full bodies would make every turn longer; `nextstep.py` has 7 free lines. The board's machine view is built for the board page and is not where an agent looks for a finding; `board.py` has 3 free lines. Rejected.
4. **`forge close <item> --show` (chosen).** It reads the item's saved review and prints it through the same code close uses, so the output is the same, word for word. No new command, no new file, no new record, no model call. It sits where the agent already is when it needs the text: right after a close.

Score (F x H >= 2 x C): F 3 (a client repo in daily use reruns close for this), H 2 (a slow, wasted step), C 1 (under 20 product lines, no model call, no user step): 6 >= 2, kept.

### Decisions

- **One printing function.** Move the print block `close.py:434-451` (the `Review:` line, the numbered blocking findings with body, and the advisory findings with their "Does not block" reason and body) unchanged into `review_skip.show(result)`, which computes `review.blocking(result)` itself. Close calls it at the same place. Close's output does not change; `tests/test_close_explains_findings_and_requires_done_when.py` stays green unchanged.
- **The option.** Add `(('--show',), {"action": "store_true", "help": "Print the last close's review result again; runs no tests and no review"})` to close's `args`. In `close.close`, right after `top = _worktree(item)` and the state read (`close.py:86-87`), and before `review_skip.requested`, backfill, migration warnings or anything that writes: when `args.show`, call `review_skip.show(state["review"])` and return 0. When the item has no saved review, print `<item> has no review yet.` and `Next: forge close <item>`, and return 0. `_worktree` stays the way to find the item's checkout, as for close itself.
- **Not added.** No refusal when `--show` comes with other close options; no reprint of the last close's failed test output; no new record; no change to `forge next`, the board or the pull request body. See the owner questions in Notes.
- **Line budget.** `close.py` goes down by about 13 lines (18 moved out, about 5 added), so it ends below 1,200. `review_skip.py` grows by about 20.
- **Guide and command page.** Add a row after `skill.md:118`: `| "Show the last close's findings again" | \`forge close <item> --show\`; it prints the last close's findings in full and runs no tests and no review; never run close again only to read them |`. Add the same row in `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` by hand, in the same place, and change nothing else there. Add `` `--show` reprints the last close's findings without running anything; `` to close's `listing` text, and regenerate `docs/commands.md` with this checkout's `forge sync`; commit only the close row's change in that page. No `brief.md` change: workers get their findings in the brief.
- **New and existing repos.** One test on a new repo only. No upgrade test change: no record is converted, and saved reviews from earlier releases already have the full text.

### Done-when details

1. Close shows its last result again.
   - Test: `tests/test_close_shows_last_result.py::test_1_close_show_prints_the_last_findings_and_runs_nothing`, `STORY = "FORGE-FINDINGS-1"`, parametrized `kind` = `task`, `fix` (new repo only), on the `env` fixture from `tests/test_close.py`, with `test_place = "local"` and a `test` command that appends one line to a file in `tmp` (as `tests/test_close_always_tests.py::set_up` does).
   - Steps: start the item (`env.start_task()` or `env.start_fix()`). `forge close <item> --show` exits 0 and prints `<item> has no review yet.` Then `env.reviews(blocked(finding("P1", ...), finding("P2", ...)))` with a distinct multi-line `body` on each; `forge close <item>` exits 1. Record the review stub's call count (`env.review_calls()`), the test marker's line count, every stub `gh` call so far, the item checkout's `HEAD` and `git status --porcelain`. Then `forge close <item> --show`.
   - Asserts: it exits 0; its stdout equals the first close's stdout from `Review:` to the end, so both full bodies appear; no new review call; the test marker still has one line; no new `gh` call; the checkout's `HEAD` and status are unchanged.
   - Edge cases: a dismissed finding is not printed, as in close; an item with no review prints the "no review yet" line; a part and a fix behave the same. Before the round ends, run the two cheap checks from AGENTS.md (`test_4_one_test_per_rule`, `test_5_forge_stays_small`).

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| SHOW | Close shows its last result | `review_skip.show` with close's moved print block, close's `--show` option and its listing text, the guide row in the template and both repo copies, the regenerated command page | 1 | `src/forge/close.py`, `src/forge/review_skip.py`, `src/forge/templates/skill.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md`, `docs/commands.md`, `tests/test_close_shows_last_result.py` (new) | `tests/test_close_shows_last_result.py::test_1_close_show_prints_the_last_findings_and_runs_nothing`; existing, stay green: `tests/test_close_explains_findings_and_requires_done_when.py`, `tests/test_split_page.py::test_4_sync_keeps_the_command_page_current`, `tests/test_rules.py::test_5_forge_stays_small` | | no | |

New moving parts: none

## Notes

- **Principle 6.** Adds one option on an existing command and no command; removes a second close from the agent's flow. Product code: about +7 lines net (`close.py` about -13, `review_skip.py` about +20).
- **Model cost.** None added. Each use saves a close rerun: its test run, push and pull request update, and a model review whenever the change differs from the reviewed one.
- **Owner questions (recommended answer first).**
  1. The option's name: `--show` (recommended; "show the last result") or `--findings`.
  2. Also reprint the last close's failed test output: no (recommended; not asked for, and the worker already gets it in its next brief) or yes, in this part.
  3. Refuse `--show` when it comes with another close option such as `--dismiss`: no (recommended; an unlikely mix, and the refusal would add a message and a test) or yes.
- **Not verified.** That an agent in the client repo will use the option instead of a second close; the guide row is the only nudge.
