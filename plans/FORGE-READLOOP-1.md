# The cold read loops until the plan has no gaps

5 parts · Risks: none · New moving parts: none

## What changes for you

- After the agent answers the cold reader's findings and fixes the plan, the same reader reads
  the whole plan again, with its earlier findings and the answers to them, and this repeats until
  it finds nothing. Only then can you approve. The reader is the other app, or the same app when
  only one is installed; if its app is uninstalled mid-way, the next read says so and switches.
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

1. **The same reader reads again.** The reader is the other app when it is installed; when only
   Codex or only Claude Code is installed, it is a separate read-only conversation of that same
   app, and the notes say so. `forge read <KEY or spec>` run again, once every finding in the
   notes has a disposition, continues the previous round's recorded reader conversation (a Codex
   conversation, or a Claude Code session started with a known session id) and sends it only what
   changed: the doc's diff since the previous round, the previous round's findings with their
   dispositions plus any older finding whose disposition changed since, and the number to start
   new findings from, telling it to re-read the whole doc from its path. For a story it also sends
   the confirmed spec's diff since the previous round, found the way the first round finds the
   spec (empty when unchanged), and tells the reader to re-read `docs/product/BRIEF.md` from the
   story checkout. It never resends the first-round instructions, the whole doc or older rounds'
   findings, which the conversation already has. The reader stays the one recorded in the notes; a round started from the app that is
   itself the recorded reader, while the other app is installed, refuses and names the app to run
   it from. When the recorded reader's app is no longer installed, the round starts fresh on the
   reader Forge would pick now, and Forge says so and records the new reader in the notes. When
   the conversation can't be continued, the round starts fresh with the first-round
   instructions, the whole doc and every earlier finding with its disposition, and Forge says so. When the previous round's text
   can't be found (notes written before this change), the round starts fresh without a diff. A
   round that fails or is discarded because a file changed records nothing and drops its
   conversation, so the retry starts fresh. Each round's findings are added to the notes under
   `## Round <n>`, numbered after the earlier rounds' findings. `forge read` refuses a new round
   while a finding lacks a disposition. A reply that isn't exactly `No findings.` and has no
   numbered finding becomes one numbered finding, as today, so it needs a disposition too. Every
   round's prompt, the first included, carries the `## Known traps` section of the repo's
   AGENTS.md, outside Forge's block, as the default branch has it, so a story branch made before a
   trap was learned still gets it. Tests cover a continued Codex round and a continued Claude round each sending only the diff,
   the previous round's dispositions, a changed older disposition and the next number, a third
   round after the human settles a dispute, a spec found only on a promoted task branch changing between rounds, an answers change
   between rounds, unchanged older findings left out,
   a Codex-only and a Claude-only reader, a fresh round after a Codex conversation or a Claude
   session is gone, a recorded reader that is no longer installed, a fresh
   round from old notes whose text is gone, a wrong-app refusal, a retry after a failed round and
   after a discarded round for each app, an undisposed finding, an unnumbered reply, an older story branch
   getting a trap learned after it was made, and the round-four nudge.
2. **A story passes only on "No findings".** A round passes only when its whole text, trimmed,
   is exactly `No findings.`; anything else, including `No findings.` followed by a finding, is
   a round with findings. A passing round commits the doc and its notes on the branch it was
   read on. Story approval, `forge next`'s approval step, `forge task start` and Forge's
   pull-request check refuse a story whose latest round had findings or whose doc changed after
   that round, naming `forge read <KEY>` as the next step, so a story doc edited after approval,
   including its Tasks table, gets a new round before its next task starts. Before the story's
   first task merges, tasks start from the story branch as today, carrying everything on it,
   the roadmap entry included. After that, for a story whose notes have rounds, `forge task
   start` reads the doc and notes from the story branch while it exists, and the new task branch
   starts from the default branch with the story branch's copy of the doc, its notes and the
   story's state file (which holds the approval) as its first commit, so they reach the task's
   pull request without merging branches that don't share history after a squash merge. Notes
   written before this change count as round 1: an unapproved story with such notes needs a
   passing round, and a story approved before this change keeps today's rules entirely: no read
   gate after approval and today's task start, reading the default branch after its first merge.
   When a story is approved, Forge merges the story branch into the branch of a task promoted from
   a fix, so the doc, its notes, the state file and the roadmap entry reach that task's pull
   request. The approval is recorded first; if that merge fails for any reason (a conflict, or
   uncommitted edits in the task's folder in its way), Forge aborts any merge in progress, leaves
   the task branch and its folder as they were, and names the one merge for the agent to finish
   before closing. Tests cover each refusal, a task pull
   request that changes only the Tasks table, the exact-text rule and its near misses, the
   commit, `forge next` naming the read and its round for an approved story whose doc changed, a
   first task starting from the story branch with its roadmap entry, a later task starting from
   the default branch with the passing doc, notes and a renewed approval after a squash-merged
   first task, a changed Tasks table stopping `forge task start`, a promoted task's pull request carrying the
   passing doc, notes, state and roadmap entry after approval, that merge conflicting, that merge blocked by an uncommitted edit, and an old
   approved story whose Tasks table changed on the default branch passing `forge next`, the
   pull-request check and `forge task start` without a read. The reader's Codex
   conversation is archived only when a round passes; a round with findings leaves it for the
   next round, and a failed archive only prints a note. A passing round archives only its own
   conversation; an earlier one left by an app that is no longer installed is left as it is,
   with a note naming it. Tests cover all three.
3. **Kept findings are settled, not argued.** The reader raises a finding the agent kept again
   only when it disagrees with the stated reason, as a new finding `Disputed keep <n>: <why>`. The
   skill tells the agent to put each disputed keep to the human as one question with options,
   record the answer in the doc's Notes as `Decided: <finding>: <answer> (owner, <date>)`, and
   give both the original kept finding and the disputed one the disposition `keep` citing that
   line. The next-round prompt tells
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
   load, and values a frontend build fixes at build time. Every round also checks the plan against the
   `## Known traps` section of the repo's AGENTS.md (item 1). The skill tells the
   agent, after `forge story done` opens the outcome fix, to look back at the story's review
   rounds and, for each kind of finding the plan missed that cost two or more fix rounds or hit
   two or more tasks, add one trap line to that section in the outcome fix's worktree and commit
   it before closing the fix, creating the section when it is missing. This is an instruction to the
   agent: SPEC's test checks that the synced skill carries each step and both thresholds.
6. **Forge nudges when a read doesn't converge.** While a read hasn't passed, `forge next` names
   its round, and from round 4 on it adds that the plan isn't converging and the human should be
   asked whether to split the story.
7. **Specs pass the same way.** `spec confirm` and Forge's pull-request check refuse an
   unconfirmed spec whose latest round had findings or which changed after that round; a passing
   round commits the spec and its notes, so an unconfirmed spec that passed also passes the
   pull-request check. A confirmed
   spec keeps today's rules. Tests cover an unconfirmed spec's refusals, the committed pull-request head of one that passed,
   and its confirmation after a passing round.
8. **The one-time amendment goes.** `forge read --amended` is removed from the command, its help,
   its refusal messages, the guide, the command table, the AGENTS.md block, the skill (its
   amendment line and "No second cold read"), the specs README new repositories get, and the
   cold-read prompt's "no second read" line, and every read
   check uses the latest round's pass instead of the amendment record. Tests that used
   `--amended` run rounds instead, and a test checks a new repository's generated skill and specs
   README no longer promise one read.

## Risks

Risks: none

## For the builders

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | What the reader asks | The first-round and next-round prompt text, the general traps, and the skill's steps for disputed keeps, edge cases and trap lines | 3, 4, 5 | `src/forge/templates/cold-read.md`, `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `tests/test_split_ships.py`, `tests/test_trim_skills.py` | `tests/test_readloop_prompt.py`, `tests/test_split_ships.py`, `tests/test_trim_skills.py` | none | yes |
| ROUNDS | Read again | Continued and fresh rounds, the round notes, the reader pinning, and `forge next`'s round nudge | 1, 6 | `src/forge/story.py`, `src/forge/codex.py`, `src/forge/worker.py`, `src/forge/nextstep.py` | `tests/test_readloop_rounds.py` | SPEC | yes |
| CUT | No more amendment | `--amended` removed everywhere, and every read check on the latest round's pass | 8 | `src/forge/story.py`, `src/forge/records.py`, `src/forge/prcheck.py`, `docs/commands.md`, `docs/guide.md`, `src/forge/templates/adapters/AGENTS.md`, `AGENTS.md`, `src/forge/templates/skill.md`, `src/forge/templates/cold-read.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `src/forge/templates/skeleton/docs/specs/README.md`, `tests/test_split_ships.py`, `tests/test_approval.py`, `tests/test_codex_reader.py`, `tests/test_prcheck.py`, `tests/test_records.py`, `tests/test_split_commands.py`, `tests/test_story.py` | `tests/test_readloop_cut.py`, `tests/test_split_ships.py`, `tests/test_approval.py`, `tests/test_codex_reader.py`, `tests/test_prcheck.py`, `tests/test_records.py`, `tests/test_split_commands.py`, `tests/test_story.py` | ROUNDS | yes |
| GATES | Stories pass first | The story pass gate in approval, `forge next` and task start, the passing round's commit, reading from the story branch, and old stories | 2 | `src/forge/story.py`, `src/forge/approval.py`, `src/forge/task.py`, `src/forge/nextstep.py`, `tests/test_task.py` | `tests/test_readloop_gates.py`, `tests/test_task.py` | CUT | yes |
| SPECS | Specs pass first | The spec pass gate in `spec confirm` and the pull-request check | 7 | `src/forge/records.py`, `src/forge/prcheck.py` | `tests/test_readloop_specs.py` | GATES | yes |

New moving parts: none

## Notes

- SPEC pins the next-round prompt as a second part of `cold-read.md`, after a
  `<!-- forge:round -->` line and before the `<!-- forge:notes -->` part, using `$round`,
  `$path`, `$diff`, `$dispositions` (the previous round's findings with their dispositions, plus
  any older finding whose disposition changed since), `$spec_diff` (the confirmed spec's diff since
  the previous round, or empty),
  `$next` (the first new finding's number) and `$traps` (the default branch's `## Known traps`
  section, also added to the first-round prompt); it has no `$doc` or `$findings`. ROUNDS
  fills them and adds nothing to the wording.
- ROUNDS pins the notes contract CUT, GATES and SPECS read: the frontmatter keeps `reader`,
  `read_at` and `read_hash` for the latest round and adds `round` (a number) and `passed` (`yes`
  only when that round's whole text, trimmed, is exactly `No findings.`, else `no`). Each round's
  text sits under `## Round <n>`; notes without `round` are round 1. Each round `read` stores, with `git hash-object -w`,
  the doc, the confirmed spec and the notes as that round's reader saw them, and records their
  object ids in the frontmatter (`doc_seen`, `spec_seen`, `notes_seen`); the next round's diffs
  and changed older dispositions are taken against those, and when one can't be found the round
  starts fresh. ROUNDS leaves `amended_hash`, `--amended` and today's read gate working
  as they are; CUT drops them and moves every read check to the latest round's pass.
- GATES makes a passing round commit its doc and notes for specs as well as story docs; SPECS
  relies on that commit.
- ROUNDS continues a Claude reader's session the way Claude workers continue theirs once the fix
  that makes Claude workers resume has merged; ROUNDS starts after it.
- The read conversation is recorded under the read's own folder (`threads/read/<target>`), so
  `codex.conversation` and `codex.record` take the kind instead of assuming a fix.
- Nothing here runs shell commands of its own: every item runs inside Forge's Python, which CI
  runs on Ubuntu, macOS and Windows, so no WSL or shell-specific case applies.
- Opus writes SPEC's text; Claude workers build ROUNDS, CUT, GATES and SPECS.
- Each new test file starts with `STORY = "FORGE-READLOOP-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers; existing test files keep their own story and only change the
  cases this story breaks. The round tests run the real SDK against the stub app-server,
  as `tests/test_codex_reader.py` does, and a fake `claude` on PATH for Claude readers, as
  `tests/test_worker.py` does.
