# The cold read loops until the plan has no gaps

2 parts · Risks: none · New moving parts: none

## What changes for you

- After the agent answers the cold reader's findings and fixes the plan, the same reader reads
  the whole plan again, with its earlier findings and the answers to them, and this repeats until
  it finds nothing. Only then can you approve.
- The reader hunts edge cases item by item: the inputs and states each item must handle, Windows,
  WSL, macOS and CI, the failure paths, and the test that proves each case. Those cases go into
  the plan's "Done when" items with their tests, so workers build them and reviewers check them.
- When the reader still disagrees with a finding the agent kept, you get one question with
  options; your answer is recorded and the reader accepts it.
- Each repo keeps a list of known traps that the agent grows after each story from the review
  problems the plan missed, and every cold read checks the plan against it.
- From the fourth round, Forge suggests splitting the story instead of reading on.

## Why

Gaps a plan never pins down come back as many review rounds, because the cold read runs once and
nobody checks the amended plan. On one day in this repo, the prototype sign-off took seven fix
rounds and the install scripts five, Windows line endings broke three tasks and three
documentation tasks skipped their required tests; each was cheap to write into the plan and
expensive to find in review.

## Done when

1. **The same reader reads again.** `forge read <KEY or spec>` run again, once every finding in
   the notes has a disposition, continues the previous round's recorded Codex conversation and
   sends it the whole current doc, every earlier finding with its disposition, and the doc's diff
   since the previous round. When that conversation can't be continued, or the reader is Claude,
   the round starts fresh with the same text plus the reader's first-round instructions, and
   Forge says so. Each round's findings are added to the notes under `## Round <n>`, numbered
   after the earlier rounds' findings. `forge read` refuses a new round while a finding lacks a
   disposition.
2. **It passes only on "No findings".** A read passes only when its latest round wrote
   `No findings.` about the doc exactly as it stands. Story approval, `forge next`'s approval
   step, spec confirmation and Forge's pull-request check all refuse a story doc or spec whose
   latest round had findings or which changed after that round, naming `forge read <target>` as
   the next step. `--amended` is removed, and a doc edited after approval, including its Tasks
   table, gets a new round. A story approved before this change keeps its approval. The reader's
   Codex conversation is archived when a round passes.
3. **Kept findings are settled, not argued.** The reader raises a finding the agent kept again
   only when it disagrees with the stated reason, as `Disputed keep <n>: <why>`. The skill tells
   the agent to put each disputed keep to the human as one question with options, and to record
   the answer in the doc's Notes as `Decided: <finding>: <answer> (owner, <date>)`, which the next
   round accepts.
4. **The reader hunts edge cases.** For every Done-when item the cold-read prompt asks which
   inputs and states it must handle, which platforms and shells (Windows PowerShell and cmd, WSL,
   macOS, Linux CI), which failure and refusal paths, and which test in which task's Tests cell
   proves each case. A missing proof is reported as `Unproven: item <n>: <case>`, and a known trap
   an item hits as `Trap: <trap>: item <n>`. The skill tells the agent to resolve these by adding
   the case to the Done-when item and its test to the owning task's Tests cell, never only to
   Notes.
5. **Known traps are shipped and learned.** The cold-read prompt carries Forge's general traps:
   Windows line endings and shells, no network in CI, a new settings key the installed Forge
   rejects, documentation tasks skipping their required tests, tests that fail only under machine
   load, and values a frontend build fixes at build time. The reader also checks the plan against
   a `## Known traps` section in the repo's AGENTS.md, outside Forge's block. The skill tells the
   agent to add a trap line there, in the same pull request that records a story's outcome, for
   each kind of review finding the plan missed that cost two or more fix rounds or hit two or more
   tasks.
6. **Forge nudges when a read doesn't converge.** While a read hasn't passed, `forge next` names
   its round, and from round 4 on it adds that the plan isn't converging and the human should be
   asked whether to split the story.

## Risks

Risks: none

## For the builders

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | What the reader asks | The first-round and next-round prompt text, the general traps, and the skill's steps for disputed keeps, edge cases and trap lines | 3, 4, 5 | `src/forge/templates/cold-read.md`, `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `tests/test_split_ships.py`, `tests/test_trim_skills.py` | `tests/test_readloop_prompt.py` | none | yes |
| LOOP | Read until it passes | The resumed rounds, the pass gate everywhere a read is checked, the removal of `--amended`, and `forge next`'s round nudge | 1, 2, 6 | `src/forge/story.py`, `src/forge/records.py`, `src/forge/codex.py`, `src/forge/approval.py`, `src/forge/nextstep.py`, `src/forge/prcheck.py`, `docs/commands.md`, `docs/guide.md`, `src/forge/templates/adapters/AGENTS.md` | `tests/test_readloop.py` | SPEC | yes |

New moving parts: none

## Notes

- SPEC pins the next-round prompt as a second part of `cold-read.md`, after a
  `<!-- forge:round -->` line and before the `<!-- forge:notes -->` part, using `$round`,
  `$path`, `$doc`, `$diff`, `$findings` and `$next` (the first new finding's number). LOOP fills
  them and adds nothing to the wording.
- The notes frontmatter keeps `reader`, `read_at` and `read_hash` for the latest round, drops
  `amended_hash`, and adds `round` and `passed` (`yes` or `no`). The doc's diff is taken against
  the previous round's text, which `read` stores with `git hash-object -w`.
- The read conversation is recorded under the read's own folder (`threads/read/<target>`), so
  `codex.conversation` and `codex.record` take the kind instead of assuming a fix.
- Opus writes SPEC's text; a Claude worker builds LOOP. Existing tests that use `--amended` are
  updated to the new rounds.
- Each test file starts with `STORY = "FORGE-READLOOP-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers. LOOP's tests run the real SDK against the stub app-server, as
  `tests/test_codex_reader.py` does.
