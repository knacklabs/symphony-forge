# Upgrading Forge in a client repo just works

4 parts · Risks: none · New moving parts: none

## What changes for you

- A client repo's Forge upgrade merges like any other change: its pull request passes Forge's own
  check, with no need to switch that check off by hand.
- An upgrade isn't called ready while the files Forge keeps in the repo are out of date.
- While an upgrade waits for its merge, Forge keeps working on the default branch, and the approval
  step never blocks.
- Messages point at the real fix, and moving an old repo to Forge v1 clears the old files it leaves.

## Why

Upgrading a client repo from v1.0.2 to v1.1.0 showed that the upgrade pull request can never pass
Forge's check, that close called it clean while synced files were stale, and that the default
branch refused every command until the owner merged by hand. Every client's upgrade to v1.2.0 would
hit the same wall.

## Done when

1. **An upgrade pull request passes Forge's check.**
2. **An upgrade is not ready while synced files are out of date.**
3. **The default branch keeps working while an upgrade waits.**
4. **Messages point at the real fix.**
5. **Moving to Forge v1 clears the old untracked files.**

## Risks

Risks: none

## For the builders

### Done-when details

1. When a pull request changes `forge.toml`'s `version`, Forge's workflow installs that pinned
   release and runs the check with it; the version must look like a release tag (`v` and three
   numbers) and is installed from Forge's own repo, never from the pull request's code; any other
   pull request is checked by the default branch's pinned Forge as today. A test proves a review
   recorded by this version still passes the check of the previous release's rules on the same
   commits, so today's v1.1.0 clients can upgrade to v1.2.0 without the new workflow. Tests cover
   an upgrade pull request, a malformed version refused with a plain message, and an ordinary pull
   request.
2. `forge close` on a fix that changes `forge.toml`'s `version` refuses while `forge doctor` would
   report files that differ from what `forge sync` writes, naming them and saying to run
   `forge sync` in the fix's folder; the skill's upgrade steps run `forge sync` after changing the
   version. Tests cover a stale skill copy refusing and a synced upgrade passing.
3. On the default branch, a changing command accepts an installed Forge newer than the pin when an
   open fix pins exactly the installed version (found in a local worktree), and names that fix;
   otherwise the version check refuses as today. The approval hook never fails on a version
   mismatch: it approves as usual and prints a warning. Tests cover a command on the default
   branch with a pending upgrade fix, the same without one, and an approval with mismatched
   versions.
4. `forge close <fix>` run from another checkout names the fix's own folder when the version
   there matches the installed Forge, instead of blaming the version; `forge doctor` says which
   Forge version its comparison uses, and when that isn't the pinned one, says the comparison is
   against the installed version and how to check the pinned one. Tests cover both messages.
5. `forge migrate` lists the untracked files an older Forge left (`.factory/briefs/`,
   `.factory/diagnostic-briefs/`, `.factory/delegations.jsonl`, `.factory/scratchpad.md`) and
   removes them after the human confirms through the agent, as the migration's other cleanups do.
   A test runs `forge migrate` on a repo with those files untracked.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | Upgrade check | The workflow's pinned-release install for upgrade pull requests, and the review-compatibility test | 1 | `src/forge/prcheck.py`, `src/forge/sync.py`, `.github/workflows/forge.yml`, `tests/test_split_ships.py` | `tests/test_upgrade_check.py` | none | yes |
| SYNCED | Synced before ready | Close refusing a stale upgrade, and the skill's upgrade steps | 2 | `src/forge/close.py`, `src/forge/doctor.py`, `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/` | `tests/test_upgrade_synced.py` | none | yes |
| PENDING | Pending upgrade | The version check's pending-upgrade exception, the warning-only approval hook, and the two messages | 3, 4 | `src/forge/repo.py`, `src/forge/approval.py`, `src/forge/cli.py`, `src/forge/doctor.py` | `tests/test_upgrade_pending.py` | SYNCED | yes |
| LEFTOVERS | Old files cleared | The migration's untracked leftovers list and cleanup | 5 | `src/forge/migrate.py` | `tests/test_upgrade_leftovers.py` | none | yes |

New moving parts: none

## Notes

- No client repo is named anywhere in this story's code, tests, texts or commits.
- PENDING waits for SYNCED because both change `doctor.py`.
- Claude workers build every part; Opus writes SYNCED's skill text.
- Each new test file starts with `STORY = "FORGE-UPGRADE-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
