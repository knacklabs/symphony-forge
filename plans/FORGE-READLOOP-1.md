# The cold read loops until the plan has no gaps

3 parts · Risks: none · New moving parts: none

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
   since the previous round. The reader stays the family recorded in the notes; a round started
   from the app that is itself the recorded reader refuses and names the app to run it from. When
   the conversation can't be continued, or the reader is Claude, the round starts fresh with the
   same text plus the reader's first-round instructions, and Forge says so. Each round's findings
   are added to the notes under `## Round <n>`, numbered after the earlier rounds' findings. A
   round that fails or is discarded because a file changed records nothing. `forge read` refuses a
   new round while a finding lacks a disposition. Tests cover a continued round, a fresh round
   after the conversation is gone, a wrong-app refusal, a discarded round and an undisposed
   finding.
2. **It passes only on "No findings".** A read passes only when its latest round's whole text is
   exactly `No findings.` about the doc as it stands. Story approval, `forge next`'s approval
   step, `forge task start`, spec confirmation and Forge's pull-request check all refuse a story
   doc or unconfirmed spec whose latest round had findings or which changed after that round,
   naming `forge read <target>` as the next step. `--amended` is removed, so a story doc edited
   after approval, including its Tasks table, gets a new round before its next task starts.
   `forge task start` reads the story doc and its notes from the story branch while that branch
   exists, and the new task branch merges the story branch, so the passing doc and notes reach
   the task's pull request. A confirmed spec stays guarded by its existing confirmed hash:
   `spec confirm` and `spec measure` keep refreshing it and need no new round, and the
   pull-request check refuses a confirmed spec whose body no longer matches it. Notes written
   before this change count as round 1: an unapproved story or unconfirmed spec with such notes
   needs a passing round, and a story approved before this change starts tasks as today until its
   doc changes, after which it needs a passing round too. Tests cover each refusal, text that
   only contains `No findings.`, a changed Tasks table stopping `forge task start` before and
   after the story's first task has merged, a confirmed spec's confirm, measure and body edit, old
   notes, and an old approved story before and after an edit. The reader's Codex conversation is
   archived when a round passes.
3. **Kept findings are settled, not argued.** The reader raises a finding the agent kept again
   only when it disagrees with the stated reason, as a new finding `Disputed keep <n>: <why>`. The
   skill tells the agent to put each disputed keep to the human as one question with options,
   record the answer in the doc's Notes as `Decided: <finding>: <answer> (owner, <date>)`, and
   give the disputed finding the disposition `keep` citing that line. The next-round prompt tells
   the reader never to raise again a finding whose disposition cites a `Decided:` line.
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
   agent, after `forge story done` opens the outcome fix, to look back at the story's review
   rounds and, for each kind of finding the plan missed that cost two or more fix rounds or hit
   two or more tasks, add one trap line to that section in the outcome fix's worktree and commit
   it before closing the fix, creating the section when it is missing. SPEC's test checks that the
   synced skill carries each of these steps, including the two thresholds.
6. **Forge nudges when a read doesn't converge.** While a read hasn't passed, `forge next` names
   its round, and from round 4 on it adds that the plan isn't converging and the human should be
   asked whether to split the story.

## Risks

Risks: none

## For the builders

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | What the reader asks | The first-round and next-round prompt text, the general traps, and the skill's steps for disputed keeps, edge cases and trap lines | 3, 4, 5 | `src/forge/templates/cold-read.md`, `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `tests/test_split_ships.py`, `tests/test_trim_skills.py` | `tests/test_readloop_prompt.py`: the round prompt's parts and variables, the edge-case questions, the general traps, the Decided rule, the skill's disputed-keep, edge-case and trap steps | none | yes |
| ROUNDS | Read again | Continued and fresh rounds, the round notes, the reader pinning, and `forge next`'s round nudge | 1, 6 | `src/forge/story.py`, `src/forge/codex.py`, `src/forge/nextstep.py` | `tests/test_readloop_rounds.py`: a continued round, a fresh round, a wrong-app refusal, a failed round, a discarded round, an undisposed finding, the round-four nudge | SPEC | yes |
| GATES | Pass before going on | The pass gate in approval, task start, spec confirmation and the pull-request check, old notes, and the removal of `--amended` | 2 | `src/forge/story.py`, `src/forge/records.py`, `src/forge/approval.py`, `src/forge/task.py`, `src/forge/nextstep.py`, `src/forge/prcheck.py`, `docs/commands.md`, `docs/guide.md`, `src/forge/templates/adapters/AGENTS.md`, `tests/test_codex_reader.py`, `tests/test_story.py`, `tests/test_approval.py`, `tests/test_split_commands.py`, and any other test that uses `--amended` | `tests/test_readloop_gates.py`: each case item 2 names |  ROUNDS | yes |

New moving parts: none

## Notes

- SPEC pins the next-round prompt as a second part of `cold-read.md`, after a
  `<!-- forge:round -->` line and before the `<!-- forge:notes -->` part, using `$round`,
  `$path`, `$doc`, `$diff`, `$findings` and `$next` (the first new finding's number). ROUNDS
  fills them and adds nothing to the wording.
- ROUNDS pins the notes contract GATES reads: the frontmatter keeps `reader`, `read_at` and
  `read_hash` for the latest round, drops `amended_hash`, and adds `round` (a number) and
  `passed` (`yes` only when that round's whole text is exactly `No findings.`, else `no`). Each
  round's text sits under `## Round <n>`; notes without `round` are round 1. The doc's diff is
  taken against the previous round's text, which `read` stores with `git hash-object -w`.
- The read conversation is recorded under the read's own folder (`threads/read/<target>`), so
  `codex.conversation` and `codex.record` take the kind instead of assuming a fix.
- Nothing here runs shell commands of its own: every item runs inside Forge's Python, which CI
  runs on Ubuntu, macOS and Windows, so no WSL or shell-specific case applies.
- Opus writes SPEC's text; Claude workers build ROUNDS and GATES. Existing tests that use
  `--amended` are updated by GATES.
- Each test file starts with `STORY = "FORGE-READLOOP-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers. The round tests run the real SDK against the stub app-server,
  as `tests/test_codex_reader.py` does.
