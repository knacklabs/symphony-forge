# Upgrading Forge in a client repo just works

4 parts · Risks: one (deleting old untracked files, after confirmation) · New moving parts: none

## What changes for you

- A client repo's Forge upgrade merges like any other change: its pull request passes Forge's own
  check, with no need to switch that check off by hand.
- An upgrade isn't called ready while the files Forge keeps in the repo are out of date.
- While an upgrade waits for its merge, Forge keeps working on the default branch, and the approval
  step never blocks.
- Messages point at the real fix, and moving an old repo to Forge v1 clears the old files it leaves.
- A Forge installed from unreleased code says so, so a client repo is never checked with a build
  that only claims to be a release.

## Why

Upgrading a client repo from v1.0.2 to v1.1.0 showed that the upgrade pull request can never pass
Forge's check, that close called it clean while synced files were stale, and that the default
branch refused every command until the owner merged by hand. Every client's upgrade to v1.2.0 would
hit the same wall.

## Done when

1. **An upgrade pull request passes Forge's check.**
2. **An upgrade is not ready while synced files are out of date.**
3. **The default branch keeps working while an upgrade waits.**
4. **Close run from the wrong folder points at the right one.**
5. **Moving to Forge v1 clears the old untracked files.**
6. **Doctor says which Forge version it compares with.**
7. **A Forge built from unreleased code says so.**

## Risks

- Item 5 deletes untracked files, which git can't bring back. Only the four exact paths older
  Forge wrote are ever removed, they are listed first, and nothing is removed until the human
  confirms through the agent.

## For the builders

### Done-when details

1. When a pull request changes `forge.toml`'s `version`, Forge's workflow installs that pinned
   release and runs the check with it; the version must look like a release tag (`v` and three
   numbers) and is installed from Forge's own repo, never from the pull request's code; any other
   pull request is checked by the default branch's pinned Forge as today. The review record keeps,
   alongside its new fields, the fields and whole-tree fingerprint the previous release reads, for
   one release, so today's v1.1.0 clients can upgrade to v1.2.0 without the new workflow; a test
   runs the v1.1.0 release's check on a review this version records and sees it pass. Tests cover
   an upgrade pull request, a malformed version refused with a plain message, and an ordinary pull
   request.
2. `forge close` on a fix that changes `forge.toml`'s `version` refuses while the files `forge
   sync` writes differ from the repo's copies, naming them and saying to run `forge sync` in the
   fix's folder; it reuses the comparison `forge doctor` already makes, without changing
   `doctor.py`. The skill's upgrade steps run `forge sync` after changing the version. Tests cover
   a stale skill copy refusing and a synced upgrade passing.
3. The version check every changing command passes through (`repo.check_pin`, called from
   `cli._run`) accepts an installed Forge newer than the pin on the default branch when the default
   branch pins an older version and a local worktree on a `fix/` branch pins exactly the installed
   version, and names that fix (the first one found when several do); otherwise it refuses as
   today. Once the upgrade merges, the default branch pins the installed version, so a worktree
   left behind changes nothing. `forge hook` commands
   skip the version check, and the approval hook prints a warning on a mismatch but approves as
   usual. Tests run public commands: a changing command on the default branch with a pending
   upgrade fix, the same without one, the same after the upgrade merged with its worktree left, and an approval through the hook with mismatched versions.
4. When the version check refuses and a local worktree of the item the command names pins the
   installed version, the message names that worktree's folder instead of blaming the version.
   A test runs `forge close <fix>` from another fix's folder that pins an older version.
5. `forge doctor` lists the untracked files older Forge left (`.factory/briefs/`,
   `.factory/diagnostic-briefs/`, `.factory/delegations.jsonl`, `.factory/scratchpad.md`) as
   leftovers, showing every file inside them, and `forge doctor --fix` removes only the files it
   showed, after the agent has shown the list and the human confirmed; nothing outside those
   paths is touched. These files are ignored by git in repos older Forge set up, so `forge
   migrate` runs with them present and `forge doctor` finds them afterwards. A test migrates a
   repo with them ignored, then runs doctor and doctor --fix and sees a nested file listed and an
   unrelated untracked file survive.
6. `forge doctor` says which Forge version its comparison uses, and when that isn't the pinned
   version, says the comparison is against the installed version and how to check with the pinned
   one. A test runs doctor with a mismatched pin.
7. A Forge installed from anything but a release tag reports its version with its commit (for
   example `1.1.0+8f03731`); in a client repo the version check refuses such a build with a
   message naming the pinned release to install, and in Forge's own repo it is accepted. Tests
   cover a client refusing a development build and Forge's own repo accepting it.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | Upgrade check | The workflow's pinned-release install for upgrade pull requests, and the review-compatibility test | 1 | `src/forge/prcheck.py`, `src/forge/sync.py`, `src/forge/review.py`, `.github/workflows/forge.yml`, `tests/test_split_ships.py` | `tests/test_upgrade_check.py` | none | yes |
| SYNCED | Synced before ready | Close refusing a stale upgrade, and the skill's upgrade steps | 2 | `src/forge/close.py`, `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/` | `tests/test_upgrade_synced.py` | none | yes |
| PENDING | Pending upgrade | The version check's pending-upgrade exception, the warning-only approval hook, the right-folder message, and development builds naming their commit | 3, 4, 7 | `src/forge/repo.py`, `src/forge/approval.py`, `src/forge/cli.py`, `src/forge/__init__.py`, `pyproject.toml` | `tests/test_upgrade_pending.py` | none | yes |
| DOCTOR | Doctor clean-up | The leftovers list and removal, and the version doctor compares with | 5, 6 | `src/forge/doctor.py` | `tests/test_upgrade_doctor.py` | none | yes |

New moving parts: none

## Notes

- No client repo is named anywhere in this story's code, tests, texts or commits.
- Only DOCTOR changes `doctor.py`; SYNCED calls its existing comparison.
- The story comes from a bug report rather than a spec; the Why states the evidence.
- Claude workers build every part; Opus writes SYNCED's skill text.
- Each new test file starts with `STORY = "FORGE-UPGRADE-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
