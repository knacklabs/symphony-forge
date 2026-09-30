# One command lands a change

2 parts · Risks: none · New moving parts: none

## What changes for you

- The agent lands a started task or fix with one command: it builds it if nothing is built yet,
  closes it, has the worker fix what the review or the checks find, waits for the checks, and
  merges it, saying each step in one plain line.
- It gives up after three fix rounds and tells you what is left, and it never waves a review
  finding away on its own: that stays a judgement for you or the agent.
- It merges only where the repo already lets the agent merge. Everywhere else it stops at Ready and
  gives you the pull request link to merge.
- A check that fails for a reason outside the change, when the tests already passed on this
  machine, is re-run once instead of costing a worker round.
- It works the same whether Claude Code or Codex runs it, and whether the repo's workers are
  Claude or Codex.

## Why

Landing a change today takes a coordinator a hand-run loop: build, close, read the findings, run
another round, close again when the checks were still running, re-run a flaky check, then merge.
Each step waits on the coordinator noticing the last one ended, so changes sit idle and the loop
is easy to get wrong.

## Done when

1. **One command builds a change when nothing is built yet, closes it, waits out checks still running, and says each step in one plain line.**
2. **When the review finds serious problems or a check fails because of the change, it runs another worker round with them, at most three, then stops and says what is left, and it never dismisses a finding itself.**
3. **Once the change is Ready, it merges only where the repo lets the agent merge and only through Forge's own merge; otherwise it gives you the pull request link and stops.**
4. **A failed check is re-run once only when its failure names none of the change's files and the tests already passed on this machine.**
5. **It behaves the same whether Claude Code or Codex runs it, with Claude or Codex workers.**

## Risks

Risks: none

## For the builders

### Done-when details

1. `forge land <item>` takes a task (`KEY/TASK`) or a fix, from any checkout of the repo, and
   drives the existing commands in-process: `worker.work`, `close.close` and `merge.merge`, never
   a copy of their logic. It finds the item's checkout with `close._worktree` (refusing an item
   not started, as close does) and refuses anything that isn't a task or a fix with
   `repo.REFUSALS["bad_item"]`, as `forge work` does, changing nothing. It refuses the merge
   switch's own fix (`merge.ENABLE`) with `merge.REFUSALS["owner_merges"]`, changing nothing.
   Before anything else it reads the item's pull request with `close._pull_request`: when it is
   already merged, land runs `close.close` once (which says so and names `forge story done` after
   a story's last task) and exits 0, with no worker round and no merge. It builds (one
   `worker.work` call with no note) only when the item's recorded status is `started` and its
   kind is not `story-done`, `migrate` or `adopt` (Forge made those changes already); any other
   status goes straight to close. When close refuses with `checks.REFUSALS["not_green"]` (a check
   still running or not reported on the pushed head, or GitHub not answering), land runs close
   again, at most three close runs in a row for that reason, then stops with close's last
   refusal. Any refusal land doesn't handle (a merge conflict, a worker question, an unsynced
   upgrade, no checks named, a failed worker) stops land at once with that refusal's own text and
   next step and its exit code; land prints `Stopped: <item> needs you.` before it. Rerunning land
   after any stop or an interruption continues from what the records show, because each step is
   the existing command. Land prints exactly one line of its own before each step, on stdout,
   flushed: `Building <item>.`, `Closing <item>.`, `Checks are still running on the pushed head; waiting again.`,
   `Fix round <n> of 3: the worker fixes <what>.` (what: `the review's serious findings` or
   `the failing checks`), `Re-running <check> once: its failure names none of this change's files and the tests passed here.`,
   `Merging <item>.`, and `<item> is ready; a human merges its pull request: <url>`. Tests
   (`tests/test_land.py`, with the stub gh, autoreview and claude and `FORGE_CHECKS_WAIT=0`): an
   unbuilt fix built once then closed and merged, with the step lines in that order; a built fix
   with no worker call; a `story-done` fix and a `migrate` fix at `started` with no worker call;
   checks pending on every look giving three close runs, two waiting lines, then the not-green
   refusal and a non-zero exit; an already merged pull request with no worker call, no
   `gh pr merge` and exit 0; a story key and a malformed item refused with nothing committed; the
   merge switch's fix refused; a merge conflict stopping land with close's conflict refusal and no
   worker call.
2. When close refuses with `close.REFUSALS["blocked"]`, or with `checks.REFUSALS["red"]` and
   `land._rerun` returns False, land runs one worker round (`worker.work` with no note), which
   already carries the open serious findings and the failing checks in its brief, then closes
   again. The limit is `land.ROUNDS = 3` fix rounds per `forge land` run, counting both reasons;
   when close still refuses for one of them after the third, land prints
   `Stopped after 3 fix rounds: <item> still has <what>.` and stops with close's refusal, whose
   next step names `forge work` and `--dismiss`. Land never passes `--dismiss` or `--because` and
   never edits a review's dismissals; dismissals the coordinator recorded earlier still count
   because close keeps them. A worker question stops land through close's `question` refusal.
   Tests: a review blocked once then clean gives one fix round whose brief names the finding; a
   review blocked four times gives three fix rounds, the stop line, close's blocked refusal and a
   non-zero exit, with no dismissal in the item's record; a red check with `land._rerun` False
   gives a fix round whose brief names the failing check; a Codex worker ending its round with a
   question stops land with the question refusal and runs no further round.
3. After close returns Ready, land decides with `close.merger(top, state)`, the one place close
   also uses for its Ready line: `"human"` for a `migrate` or `adopt` item and for the merge
   switch's fix, else `repo.merge_setting(top)` (agent for a client prototype before sign-off).
   On `"agent"` it prints `Merging <item>.` and calls `merge.merge`, which re-checks the ready
   record, the pull request head, the checks and the `forge.toml` merge line before its own
   `gh pr merge --match-head-commit`; a refusal there stops land with it. On `"human"` it reads the
   pull request's URL (`gh pr view <branch> --json url`), prints the hand-off line and exits 0.
   Land itself never calls `gh pr merge`. Tests: `merge = "agent"` gives exactly one `gh pr merge`
   call with `--match-head-commit` equal to the pushed head, and exit 0; `merge = "human"` gives no
   `gh pr merge` call, the hand-off line with the stub's URL, and exit 0; a client prototype before
   sign-off merges; a head moved after Ready stops land with `forge merge`'s `changed` refusal.
4. `land._rerun(top, item, branch) -> bool` re-runs only when every failing check on the pull
   request (`gh pr checks <branch> --json name,bucket,link`, as `worker._failing` reads it) meets
   all of: its link names a run and a job (`/runs/<run>/job/<job>`); that run's
   `gh run view <run> --json attempt` is 1, so each pushed head gets one re-run at most, even across
   land runs; its whole failed log (`gh run view --job <job> --log-failed`) names none of the
   item's changed files (`git diff --name-only origin/<default>...HEAD` in the item's checkout),
   each looked for with `/` and with `\`; and `review.passed_record(top, <test command>)` exists,
   meaning this machine's tests passed on the pushed head's committed files. Then it prints the
   re-run line per check, runs `gh run rerun --job <job>` for each, waits (up to
   `FORGE_CHECKS_WAIT`) until each run reports an attempt above 1, and returns True; land then
   closes again without counting a fix round. A run that never shows its new attempt stops land
   with `land.REFUSALS["rerun"]`: `GitHub has not started the re-run of <check>.` / Next:
   `forge land <item>`. Anything else returns False, which leads to a fix round. Tests
   (`tests/test_land_checks.py`): an unrelated failure with a passed record is re-run once, then
   green, merged, no worker call; a log naming a changed file with `/`, and one naming it with
   `\`, gives a fix round and no `gh run rerun`; no test command, and no passed record, give a fix
   round; a run already at attempt 2 gives a fix round; two failing checks where one names a
   changed file give no re-run; a failing commit status with no job link gives no re-run; a
   re-run that fails again gives a fix round, not a second re-run; a re-run whose attempt never
   rises stops with the re-run refusal.
5. Nothing in land reads which host runs it (`CLAUDECODE`, `CODEX_THREAD_ID`) or branches on
   `workers`: the family is chosen inside `worker.work`, exactly as for `forge work`. Tests run
   `forge land` as a subprocess, the command's real path, four times: with `CLAUDECODE=1` and with
   `CODEX_THREAD_ID` set (the other unset), each with `workers = "claude"` (the stub claude) and
   `workers = "codex"` (the stub Codex app-server, set up and trusted as
   `tests/test_codex_worker.py` does); only the model at the edge is faked. Each run has a review
   blocked once then clean and green checks with `merge = "agent"`, and must print the same step
   lines, run one fix round whose brief, read from that stub's record, names the finding, and make
   one `gh pr merge`.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| LAND | Land loop | The `forge land` command: build, close, fix rounds, waits, stops, merge or hand-off, its step lines, and the skill and command list naming it | 1, 2, 3 | `src/forge/land.py`, `src/forge/repo.py`, `src/forge/close.py`, `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `docs/commands.md` | `tests/test_land.py` | none | yes |
| CHECKS | Flaky checks and hosts | The one re-run of an unrelated failed check, and the same run under both hosts and both worker families | 4, 5 | `src/forge/land.py` | `tests/test_land_checks.py` | LAND | no |

New moving parts: none

## Notes

- LAND pins what CHECKS uses: `repo.Refused.entry` (the `REFUSALS` tuple `repo.refuse` raised
  with, `None` for a `Refused` built directly; land matches it by identity, for example
  `error.entry is close.REFUSALS["blocked"]`), `close.merger(top, state) -> str` (close's Ready line
  uses it too), `land.ROUNDS = 3`, `land.REFUSALS`, the step-line texts above, and
  `land._rerun(top, item, branch) -> bool` as a stub returning False, with the item 2 test of a red
  check leading to a fix round crossing both sides.
- Land's `COMMANDS` entry: words `land`, `changes_state` True, one `item` argument, position 165,
  and a listing row whose command cell is `forge land <item>` and whose text is "Builds, closes,
  runs fix rounds and merges a task or fix where the repo allows agent merges; run it in the
  background"; `docs/commands.md` gets the same row.
  The skill's command table gets a row "Land it" → `forge land <item>`, run in the background and
  watched like `forge work`, and its paragraph on close's findings says that when land stops on
  findings the coordinator judges them as it does today: dismiss with evidence, or `forge work`.
- This assumes three fixes being built separately land first and does not repeat them: close
  judges only its own pushed head and retries a failed push; close skips tests on an already-green
  tree with one test run per machine (it adds `review.passed_record`, which item 4 reads); and a
  Codex turn at capacity is retried. If `review.passed_record` lands under another name, CHECKS
  uses that name.
- Out of scope: `forge next` still names `forge work`, `forge close` and `forge merge`, and the
  AGENTS.md block keeps its flow; land does not tidy up after a pull request a human merged
  (`forge next` already says `forge merge <item>` for that); the round limit is a constant, not a
  setting.
- No client repo is named anywhere in this story.
- Claude workers build both tasks; Opus writes the skill text.
- Each new test file starts with `STORY = "FORGE-LAND-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
