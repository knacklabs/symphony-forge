# A live app joins Forge in one pull request

6 parts · Risks: none · New moving parts: none

## What changes for you

- An app that is already in production can adopt Forge: the agent first writes a short report on
  the codebase (how it runs, its tests and the gaps, its CI and required checks, how it deploys,
  its branch rules, where secrets and personal data live), asks you who approves, who merges and
  what must never be touched, and then opens one pull request that you merge.
- A live app is marked live and never gets prototype rules: no auto-merge, no light review, no
  oversized fixes, and stories are allowed from the start. You merge its pull requests unless you
  later choose otherwise.
- The team's own conventions, kept in the repo's AGENTS.md, win over Forge's default-stack
  conventions wherever they differ.
- Forge waits for the team's real CI checks, not a copy of its own, and the team's own pull
  requests, dependency updates, hotfixes and GitHub edits pass Forge's check with a note.

## Why

Forge can't tell a live production app from a prototype: in code, "no sign-off yet" means
"prototype", so a live app onboarded without a sign-off record would get prototype rules. There is
also no route to adopt a repo that already has history, and Forge's pull-request check blocks every
branch Forge didn't start. The owner wants this fixed before v1.2.0 ships the prototype flow.

## Done when

1. **Live or prototype is one setting.** `forge.toml` accepts `stage = "live"` or
   `stage = "prototype"`; a client repo's prototype rules apply only when its stage is prototype and
   it has no accepted sign-off; a live repo, a signed-off repo and Forge's own repo never get them;
   a client repo without the setting counts as live; `forge init` in an empty repo writes
   `stage = "prototype"`.
2. **Every prototype rule asks the same question.** The story gate, the prototype fix allowance,
   the agent merge before sign-off, the light prototype review and the design routing for prototype
   fixes all use one `repo.is_prototype(top)` check, and a test shows none of them applies in a
   live repo.
3. **Other branches pass with a note.** Forge's pull-request check passes a branch Forge didn't
   start, saying in its output that Forge didn't start it; branches Forge started are checked as
   today.
4. **A repo with history adopts Forge.** `forge init` in a repo that already has commits works on
   a fix branch instead of the default branch: it writes `forge.toml` with `stage = "live"`,
   `merge = "human"`, the test command and required checks the human confirmed, and interface
   patterns for the repo's real route and migration folders, adds the AGENTS.md block, skills and
   hooks without changing the team's own lines, and ends with that fix ready to close; branch
   protection switches on only after that fix's pull request merges, keeping the team's existing
   rules.
5. **CI waits for the team's checks.** Forge's own `tests` job ships in the workflow only when
   `forge.toml`'s `checks` names it; `forge doctor` reports when `checks` differs from what branch
   protection requires, and asks for UI skills only in a repo with a frontend.
6. **The skill adopts a live app.** The Forge skill carries the "adopt a live app" steps: the
   codebase report in `docs/context/codebase.md` (secret names only, never values), the three
   questions, house rules in AGENTS.md outside Forge's block, a test that pins today's behaviour
   before changing untested code, add-only migrations that work with the previous version, the
   team's own feature flags for changes users would notice, and no production credentials on the
   machine; the standards and the worker brief say the repo's own rules win where they differ from
   the default-stack conventions.

## Risks

Risks: none

## For the builders

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | Adopt a live app | The skill's adopt-a-live-app steps, and the house-rules sentence in the standards and worker brief | 6 | `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `src/forge/standards.md`, `src/forge/templates/brief.md`, `tests/test_trim_skills.py`, `tests/test_split_ships.py` | `tests/test_live_skill.py` | none | yes |
| STAGE | Live or prototype | The stage setting, `repo.is_prototype`, and every prototype rule switched to it | 1, 2 | `src/forge/repo.py`, `src/forge/init.py`, `src/forge/story.py`, `src/forge/records.py`, `src/forge/task.py`, `src/forge/worker.py` | `tests/test_live_stage.py` | none | yes |
| CHECK | Other branches pass | The pull-request check's pass-with-a-note for branches Forge didn't start, and the tests job only when named | 3, 5 | `src/forge/prcheck.py`, `src/forge/doctor.py` | `tests/test_live_check.py` | none | yes |
| ADOPT | Join in one pull request | `forge init` on a repo with history, through a fix, with protection after merge | 4 | `src/forge/init.py`, `src/forge/githooks.py` | `tests/test_live_adopt.py` | STAGE | yes |

New moving parts: none

## Notes

- STAGE pins `repo.is_prototype(top) -> bool`: true only when the repo is a client repo, its
  `forge.toml` says `stage = "prototype"`, and it has no accepted sign-off. STAGE switches the story
  gate, the fix allowance and the design routing (already merged) to it; FORGE-SALES-1's
  `repo.merge_setting` and FORGE-AHA-1's REVIEW task use it too: whichever lands later calls it, and
  the coordinator checks that on close.
- ADOPT asks the human through the agent for the test command, required checks and interface
  folders; `forge init` takes them as options (`--test`, `--checks`, `--interfaces`) so the agent
  can pass the confirmed answers. Protection after merge reuses how `forge migrate` does it.
- CHECK's note reads: "Forge didn't start this branch, so it checks nothing here; the repo's own CI
  and review apply."
- Opus writes SPEC's text; Codex workers build STAGE, CHECK and ADOPT.
- Each test file starts with `STORY = "FORGE-LIVE-1"`, and its `test_<n>_` names cite the Done-when
  items its task covers.
