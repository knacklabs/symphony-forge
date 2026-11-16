# Show the full text of the last close's findings without running close again

1 part · Risks: none one-way; three accepted limits · New moving parts: none

## What changes for you

- After a close finds problems, the agent can print the full text of every finding again with `forge close <item> --show`, in the item's own checkout, before the item merges. For each finding it prints the title, the file and line, the priority and the whole text, and whether the finding is still open, dismissed or moved to a follow-up fix.
- It shows the latest review saved in that checkout, with the current state after any later choice or dismissal. So it is not always word for word what the close printed.
- It runs no tests and no review, and it changes nothing: no fetch, no push, no new checkout, no file written.
- It shows only what this checkout has saved. If a teammate closed the item on another machine, run close here first.
- Forge gets no new command. This is a new option on close, because Forge already has the most commands it allows (25).
- The agent's guide names the new option, so the agent uses it instead of a second close.
- What each repo gets. A new repo gets the option and the guide line from the start. An existing repo gets both when it upgrades to the release with this change; the guide line comes with the upgrade's normal refresh. The option also shows findings from closes that ran before the upgrade, because close already keeps the full text of each finding. No saved record changes.
- Cost. No model call is added. Each use saves a second close: a full test run on a repo that tests on the laptop, a push, and sometimes a new model review.

Design: none. Nothing on the board or in the pull request changes.

## Why

When a close finds problems, it prints the full text of each finding once. The pull request shows only the titles. No command shows the full text again, so an agent that lost the output runs close again only to read it. That second close runs the tests again, pushes again, and can run a new review. A client repo in daily use reported this twice. Today the only workaround is to read Forge's saved record files by hand, and agents do not know where they are.

## Done when

1. **In the item's own checkout, before it merges, `forge close <item> --show` prints every finding of the latest saved review in full (title, file and line, priority, whole text) with its current state (open, dismissed or follow-up), for a part or a fix, and runs no tests, no review, no fetch and no push, and writes nothing.**

## Risks

Risks: none one-way. The part reverts with its pull request. It changes no saved record and no file in a client repo except the guide line.

Accepted limits, in plain words:
- After the item merges and Forge removes its checkout, the option has no checkout to read. Read the findings in the merged pull request, or ask for this later.
- A Forge installed from a release before this change does not know the option. That is how releases work: upgrade to get it.
- The output is not the same text that earlier releases' close printed. It shows the same facts in the new layout.
- It shows this checkout's saved review. A newer close on another machine shows here only after a close in this checkout.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Source: GitHub issues #1599 and #1026, from the client repo in daily use. Name no client in code, tests, texts or commits.

### What exists (evidence)

Checked in this worktree on 16 Nov 2026 (base `63d634eb6`, Forge v1.2.40). The builder checks each name again before it starts.

- **Where the full text is kept.** Close saves the whole review result in the item's committed state file before it prints anything: `state.update(review=result, ...)` then `_save(...)` in `close.close` (`src/forge/close.py:419-426`), then `_push` (`:429`), then the print block (`:434-451`). The file is `repo.state_path(item)` (`src/forge/repo.py:1110-1121`): `.factory/stories/<KEY>/tasks/<TASK>.json` for a part, `.factory/fixes/<name>.json` for a fix. Each entry of `review.findings` has `title`, `file`, `line`, `priority` and the full `body`, and `follow_up` after a split (`close.py:128-135`); `review.dismissals` holds `{"finding": <number>, "because": <text>}`, including the owner's accept (`close.py:138-145`). The same shape holds for parts and fixes. In this repo all 311 saved findings across `.factory/fixes/*.json` and `.factory/stories/*/tasks/*.json` carry a non-empty `body`, so items closed on earlier releases are covered with no conversion.
- **The issue's premise needs one correction.** The issue says the text lives only in `.git/forge/threads/{task|fix}/<item>.brief.md`. That file is written by `forge work`, not by close, and only for a session subagent run (`native.hand_out`, `src/forge/native.py:137-141`); it holds only the open blocking findings (`worker._fix_round`, `src/forge/worker.py:536-546`). Right after a close it still holds the previous round's brief.
- **What a second close costs.** It merges the default branch, runs the local tests on a `test_place = "local"` repo (`close.py:385-395` when the review is reused, `:350-383` otherwise), pushes and republishes the pull request. It reuses the saved review only when the change fingerprints are unchanged (`close.py:304-316`); otherwise it runs a new model review.
- **What the pull request holds.** `close._block` (`close.py:1100-1140`) writes each blocking finding as its title, `file:line` and "blocks the merge"; only advisory findings carry body text, flattened to one line and folded away.
- **What runs before close's own code.** `cli._run` (`src/forge/cli.py:139-148`) parses the arguments, then for every state-changing command runs `repo.check_pin` (`:147-148`), which can run the pinned release through uv (`src/forge/repo.py:955-980`). `close.close` then calls `_worktree` (`close.py:658-664`), whose `task.pick_up` (`src/forge/task.py:237-262`) returns a local checkout first and otherwise fetches and makes a new checkout.
- **Internal callers of close.** `forge land` (`src/forge/land.py:64-65`) and `forge merge` (`src/forge/merge.py:172-175`) call `close.close` with their own `argparse.Namespace`, which has no `show` field; close also calls itself (`close.py:482-485`, `:491-494`).
- **The ceilings.** `tests/test_rules.py::test_5_forge_stays_small` allows at most 25 top-level commands; `forge --help` lists 25 today. It refuses any module over 1,200 lines: `src/forge/close.py` is at 1,200; `src/forge/review_skip.py` is 97 and `src/forge/cli.py` is 181.
- **Helpers.** `review_skip.label` (`src/forge/review_skip.py:45-49`) gives close's `Review: <label>.` wording. `review_skip` imports `review`; `review.blocking` (`src/forge/review.py:189-195`) gives the open blocking findings, dismissed ones left out; `score.priority` comes from `src/forge/score.py`, which imports nothing from Forge, so `review_skip` can import it with no cycle. `review_skip.REFUSALS` is merged into close's (`close.py:75`).
- **Where close's options show.** The `COMMANDS` declaration at the end of `close.py` (`:1189-1200`): its `args` and its `listing` row. `forge sync` writes the listing rows into `docs/commands.md` in this repo (`src/forge/sync.py:714-718`); `tests/test_split_page.py::test_4_sync_keeps_the_command_page_current` checks that page. The coordinator guide's close rows are `src/forge/templates/skill.md:118-119`; this repo's copies `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` have the same rows today.

### Options weighed

1. **A new command, `forge findings <item>`.** Rejected: Forge is at its 25-command ceiling, so `test_5_forge_stays_small` fails, and principle 6 asks for no growth there.
2. **Close prints the saved file's path.** The path prints in the same output that the agent lost, and the file is JSON in which the agent must work out each finding's state. The brief file is wrong for this (see the premise correction). Rejected.
3. **`forge next` or `forge board --json` carries the full text.** `forge next` takes no item and covers every item, also in the hook that adds context to each agent turn, so full bodies would make every turn longer. The board's machine view is not where an agent looks for a finding. Rejected.
4. **`forge close <item> --show` (chosen).** It reads the saved review in the current checkout and prints it. No new command, no new file, no new record, no model call.

Score (F x H >= 2 x C): F 3 (a client repo in daily use reruns close for this), H 2 (a slow, wasted step), C 1 (under 30 product lines, no model call, no user step): 6 >= 2, kept.

### Decisions

- **The branch runs first, in `cli._run`.** Right before the pin check (`cli.py:147`) and after argument parsing, add: when `args.words == "close"` and `args.show`, import `review_skip` and return `review_skip.show(args.item)`. So `--show` runs no pin check and no run of another release, no `_worktree` lookup, no fetch, no new checkout, no backfill, no migration warning and no write. `close.close` never reads `show`, so `forge land`, `forge merge` and close's own reruns, which call `close.close` directly with their own arguments, can neither pass nor receive it.
- **The option.** In close's `COMMANDS` `args`, add `(('--show',), {"action": "store_true", "help": "Print the latest saved review's findings in full; runs nothing and writes nothing"})` on an existing line of the list, so `close.py` stays at 1,200 lines. Close's print block does not change.
- **`review_skip.show(item)`.** Read `repo.read_state(item)` in the current checkout only. When it has no `review`, refuse with a new `review_skip.REFUSALS["no_saved_review"]`: `("This checkout has no saved review of {item}.", "forge close {item}, or forge close {item} --show in {item}'s own checkout")`. Otherwise print `Review: <review_skip.label(result)>.`, then for each finding in `result["findings"]`, numbered from 1, in this order:
  - `<n>. <score.priority(f)> <title> (<file>:<line>)`
  - one state line, the first that holds: `Dismissed: <because>.` when a dismissal names `n` (this includes the owner's accept, whose `because` says so); `Follow-up: <follow_up>.` when the finding has `follow_up`; `Open: blocks the merge.` when `n` is in `review.blocking(result)`; else `Open: does not block the merge.`
  - the whole `body`, unchanged, then a blank line.
  - Return 0. About 20 lines. Dismissed findings are printed, with their reason; that settles the wording.
- **Not added.** No reprint of the last close's failed test output; no refusal when `--show` comes with other close options (they are ignored); no change to `forge next`, the board or the pull request body; nothing for a merged item or another machine's newer close (the accepted limits in Risks).
- **Guide and command page.** Add a row after `skill.md:118`: `| "Show the last close's findings again" | In the item's checkout, \`forge close <item> --show\`; it prints each finding of the saved review in full and runs no tests, no review and no push; never run close again only to read findings |`. Add the same row in `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` by hand, in the same place, and change nothing else there. Add `` `--show` prints the saved review's findings in full without running anything; `` to close's `listing` text, and regenerate `docs/commands.md` with this checkout's `forge sync`; commit only the close row's change in that page. No `brief.md` change: workers get their findings in the brief.
- **New and existing repos.** One test on a new repo only. No upgrade test change: no record is converted, and saved reviews from earlier releases already have the full text.

### Done-when details

1. Close shows the saved review.
   - Test: `tests/test_close_shows_last_result.py::test_1_close_show_prints_saved_findings_in_full_and_runs_nothing`, `STORY = "FORGE-FINDINGS-1"`, parametrized `kind` = `task`, `fix` (new repo only), on the `env` fixture from `tests/test_close.py`, with `test_place = "local"` and a `test` command that appends one line to a file in `tmp` (as `tests/test_close_always_tests.py::set_up` does). Every `--show` runs with `cwd` set to the item's checkout (`where` from `env.start_task()` or `env.start_fix()`).
   - Steps and asserts:
     - Before any close, `--show` exits non-zero, and stderr has `This checkout has no saved review of <item>.` and its `Next:` line.
     - `env.reviews(blocked(p1, p2))`, where `p1` is a P1 finding whose `body` is long: 40 or more lines and more than 4,000 characters, with blank lines inside; `p2` is a P2 finding with a short body. `forge close <item>` exits 1.
     - Record the review stub's call count (`env.review_calls()`), the test marker's line count, the stub `gh` calls, the checkout's `HEAD`, `git status --porcelain`, and whether the common git folder's `FETCH_HEAD` exists and its modified time.
     - `--show` exits 0. Its stdout holds `Review: blocked.`, `1. P1 <p1 title> (app.py:1)`, `Open: blocks the merge.`, the whole `p1` body as one exact substring, `2. P2 <p2 title> (app.py:1)` and `Open: does not block the merge.`. All recorded facts are unchanged: no new review call, no new marker line, no new `gh` call, the same `HEAD`, status and `FETCH_HEAD`.
     - `forge close <item> --dismiss 1 --because "app.py:1 <reason>"` with the stub returning the same findings (as `tests/test_close_dismiss_open_findings.py` does). Then `--show` prints `Dismissed: app.py:1 <reason>.` under finding 1, and still prints the whole `p1` body.
   - Before the round ends, run the two cheap checks from AGENTS.md (`test_4_one_test_per_rule`, `test_5_forge_stays_small`).

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| SHOW | Close shows the saved review | `review_skip.show` and its refusal, the early branch in the command entry, close's `--show` option and listing text, the guide row in the template and both repo copies, the regenerated command page | 1 | `src/forge/cli.py`, `src/forge/close.py` (the `COMMANDS` declaration only), `src/forge/review_skip.py`, `src/forge/templates/skill.md`, `.claude/skills/forge/SKILL.md`, `.codex/skills/forge/SKILL.md`, `docs/commands.md`, `tests/test_close_shows_last_result.py` (new) | `tests/test_close_shows_last_result.py::test_1_close_show_prints_saved_findings_in_full_and_runs_nothing`; existing, stay green: `tests/test_split_page.py::test_4_sync_keeps_the_command_page_current`, `tests/test_rules.py::test_5_forge_stays_small` | | no | |

New moving parts: none

## Notes

- **Principle 6.** Adds one option on an existing command and no command; removes a second close from the agent's flow. Product code: about +25 lines (`review_skip.py` about +22, `cli.py` +3, `close.py` 0).
- **Model cost.** None added. Each use saves a close rerun: its test run, push and pull request update, and a model review whenever the change differs from the reviewed one.
- **Changed after cold read round 1.** The promise is narrower: the item's own checkout, before merge, the latest saved review with each finding's current state, not the close's exact output. The branch moved to the command entry before the pin check, so it never reaches close's checkout lookup or its internal callers. A new printer replaces the reuse of close's print block. Dismissed findings are printed with their reason. The test checks one long body in full. Risks names four accepted limits.
- **Owner questions (recommended answer first).**
  1. The option's name: `--show` (recommended; "show the saved review") or `--findings`.
  2. Also reprint the last close's failed test output: no (recommended; not asked for, and the worker already gets it in its next brief) or yes, in this part.
- **Not verified.** That an agent in the client repo will use the option instead of a second close; the guide row is the only nudge.
