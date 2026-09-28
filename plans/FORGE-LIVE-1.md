# A live app joins Forge in one pull request

7 parts · Risks: none · New moving parts: none

## What changes for you

- An app that is already in production can adopt Forge: the agent first writes a short report on
  the codebase (how it runs, its tests and the gaps, its CI and required checks, how it deploys,
  its branch rules, where secrets and personal data live), gathers the team's past decisions and
  the rules its reviewers keep enforcing in pull requests, marks the fragile parts of the code, lists
  work already in flight, asks you who approves, who merges and what must never be touched, and then
  opens one pull request that you merge.
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
2. **Every prototype rule asks the same question.** The story gate, story approval and
   `forge next`'s approval step, the prototype fix allowance, the agent merge before sign-off, the
   light prototype review and the design routing for prototype fixes all use one
   `repo.is_prototype(top)` check, and a test shows that in a live repo a story can be created and
   approved and none of the prototype rules applies.
3. **Other branches pass with a note.** Forge's pull-request check passes a pull request whose
   branch name doesn't start with one of Forge's prefixes (`task/`, `fix/`, `story/`, `forge/`),
   saying in its output that Forge didn't start it; a branch with a Forge prefix is checked as
   today, even if its Forge state is missing.
4. **A repo with history adopts Forge.** `forge init` in a repo that already has commits works on
   a fix branch instead of the default branch: it writes `forge.toml` with `stage = "live"`,
   `merge = "human"`, the test command and required checks the human confirmed, and interface
   patterns for the repo's real route and migration folders, adds the AGENTS.md block, skills and
   hooks without changing the team's own lines, records the approver, the merger and the paths
   never to touch in a "House rules" section of AGENTS.md outside Forge's block, and stops with a
   list, changing nothing, when a file it would write already exists and wasn't written by Forge;
   the adoption fix closes like a migration's (Forge's own check is skipped until Forge is on the
   default branch) and branch protection switches on only after its pull request merges, keeping
   the team's existing rules.
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
7. **The app's history comes along.** The skill's adoption steps also have the agent link or import
   the repo's existing decision records and design docs as Forge decisions marked imported, without
   rewriting them; read the review comments of recent merged pull requests and turn rules reviewers
   enforce repeatedly into House rules in AGENTS.md, each citing the pull requests it came from; mark
   the most-changed, most-reverted and most-hotfixed files as danger zones in the codebase report,
   which a story touching them names under Risks; and list open pull requests and branches in the
   report so a story's plan can avoid colliding with a teammate's work.

## Risks

Risks: none

## For the builders

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | Adopt a live app | The skill's adopt-a-live-app steps including the app's history, and the house-rules sentence in the standards and worker brief | 6, 7 | `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `src/forge/standards.md`, `src/forge/templates/brief.md`, `tests/test_trim_skills.py`, `tests/test_split_ships.py` | `tests/test_live_skill.py` | none | yes |
| STAGE | Live or prototype | The stage setting, `repo.is_prototype`, and every prototype rule on the default branch switched to it | 1, 2 | `src/forge/repo.py`, `src/forge/init.py`, `src/forge/story.py`, `src/forge/records.py`, `src/forge/task.py`, `src/forge/worker.py`, `src/forge/approval.py`, `src/forge/nextstep.py`, `src/forge/review.py`, `src/forge/close.py`, `src/forge/merge.py` | `tests/test_live_stage.py` | none | yes |
| CHECK | Other branches pass | The pull-request check's pass-with-a-note for branches Forge didn't start, and the tests job only when named | 3, 5 | `src/forge/prcheck.py`, `src/forge/doctor.py` | `tests/test_live_check.py` | none | yes |
| ADOPT | Join in one pull request | `forge init` on a repo with history, through a fix, with protection after merge | 4 | `src/forge/init.py`, `src/forge/githooks.py`, `src/forge/close.py` | `tests/test_live_adopt.py` | STAGE | yes |

New moving parts: none

## Notes

- STAGE pins `repo.is_prototype(top) -> bool`: true only when the repo is a client repo, its
  `forge.toml` says `stage = "prototype"`, and it has no accepted sign-off. STAGE switches every
  prototype rule already on the default branch when it starts (story gate and approval, fix
  allowance, design routing, and FORGE-SALES-1's merge setting and FORGE-AHA-1's light review if
  they merged first). A FORGE-SALES-1 or FORGE-AHA-1 task that lands after STAGE uses
  `repo.is_prototype` itself; its story is amended to say so when STAGE merges first.
- ADOPT records its fix state with kind `adopt`, handled wherever close handles kind `migrate`.
- ADOPT asks the human through the agent for the test command, required checks and interface
  folders; `forge init` takes them as options (`--test`, `--checks`, `--interfaces`) so the agent
  can pass the confirmed answers. Protection after merge reuses how `forge migrate` does it.
- CHECK's note reads: "Forge didn't start this branch, so it checks nothing here; the repo's own CI
  and review apply."
- Opus writes SPEC's text; Codex workers build STAGE, CHECK and ADOPT.
- Each test file starts with `STORY = "FORGE-LIVE-1"`, and its `test_<n>_` names cite the Done-when
  items its task covers.
