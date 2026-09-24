# The new upgrade flow

## What and why

`forge upgrade` today converts half-finished work between versions and fails on every real client
version we rebuilt. This task builds the replacement: one short, git-protected upgrade step in its own
module, plus a test helper that builds real old clients from this repository's own history so the
step is proven against the versions clients actually run.

The new step is built and tested here but not yet connected: `forge upgrade` keeps running the old
code until CLEANUP switches it over together with the ticket-check and harness-health changes, so
nothing half-works in between. This task also names the harness tag that very old clients use first.

When the new step runs against a client, it:

- refuses, before writing anything, any client that is not safe to upgrade, and says why and what to
  do;
- works on its own new branch, copies the current Forge machinery from the harness's committed tree,
  moves only the old per-lens review files current Forge cannot read into an archive folder, keeps
  everything the client owns, and commits with an upgrade trailer;
- checks the result in a throwaway checkout, and on any failure or interruption returns the client
  exactly as it was.

## What changes

1. A test helper builds a client from any older commit of this repository by checking out that commit
   and running its own `forge init`, including a client from before the machinery moved to
   `factory/`.
2. The new step checks first, under upgrade's existing lock, and refuses with a named reason when:
   - the harness has uncommitted changes;
   - the client has no vendored-commit marker (pointed to `forge adopt`), or its vendored commit is
     unknown, unrelated or newer than the harness;
   - the client still keeps its machinery under `.agents/`: the message names the
     `forge-legacy-upgrade` tag and gives the exact commands for the older step;
   - the client has any tracked or untracked change, or is on a detached HEAD;
   - an earlier upgrade was killed and left its `forge-upgrade/...` branch: the message gives the
     exact recovery commands;
   - a checkout of the repo that git lists cannot be read (named, with `git worktree prune`
     suggested);
   - any checkout has a story, task, plan or Lite/quickfix/degraded window in progress: each checkout
     and story is named, with "finish it on your current version or park it";
   - a client file sits in Forge's machinery folders that Forge never shipped ("move it out of
     `<folder>` and re-run"); a Forge-owned file was changed by the client (with the command that
     restores Forge's shipped bytes); an ignored file sits where upgrade must write; or an archive
     destination already exists.
3. Ownership is by bytes: a file belongs to Forge when it is exactly what Forge shipped at the client's
   vendored commit. Only those are refreshed or retired. Doc contracts and agent profiles the client
   edited are kept and named in the report. Client skills, custom profiles, docs/memory, grill records,
   unknown `.factory` files and the sign-off are never touched. A client signed off before the
   `harness.yaml` sign-off pin keeps its sign-off.
4. The step runs on `forge-upgrade/<old>-<time>`, commits with a `Forge-Upgrade: <old>..<new>`
   trailer, and prints the next steps: review the commit and open a PR. Running it again with the same
   harness changes nothing; a newer harness upgrades the same way.
5. The dual-runtime, scaffold and vendor-integrity checks, `forge next`, `forge audit`,
   `forge doctor --fast` and the board data run in a throwaway checkout of the upgrade commit. Any
   failure, any tracked change they make, Ctrl-C or a termination signal undoes the upgrade, including
   new files it wrote that git ignores.
6. The tag `forge-legacy-upgrade` points at the last merged harness commit that still carries the
   `.agents/` migration. The coordinator creates and pushes it when this task merges.

## Manual Verification

1. Build clients from the July, September and Lean-era harness versions and from a version before the
   machinery rename with the test helper; each has that version's layout and vendored-commit marker.
2. Run the new step (not `forge upgrade`, which is unchanged) on each of the three idle clients: exit
   0 on a new `forge-upgrade/...` branch, original branch untouched, one commit carrying the
   `Forge-Upgrade` trailer, vendored marker at the new harness commit, clean tree; then `forge next`,
   `forge audit`, `forge doctor --fast` (missing machine tools reported, never a crash) and the board
   data run without errors.
3. Run it again with the same harness: nothing changes (no new branch, no commit). Add a harness commit
   and run it again: it succeeds. A client whose vendored commit is unknown or newer than the harness
   is refused (no downgrades); a client without the marker is sent to `forge adopt`.
4. In a second checkout, separately leave a task pointer not yet shipped with an active stage, an
   approved plan with no pointer, a saved plan awaiting approval, and an open Lite window: each is
   refused naming that checkout and story, and nothing in the repository changes apart from upgrade's
   own lock file.
5. A modified or untracked client file, a detached HEAD, a harness with uncommitted changes, a deleted
   listed checkout, a client file added under `factory/`, a changed Forge-owned file, an ignored file
   where upgrade must write and an existing archive destination: each is refused with its reason and
   advice, and nothing changes apart from upgrade's own lock file.
6. The pre-rename client is refused with a message naming `forge-legacy-upgrade` and the exact
   commands for the older step, and nothing changes apart from upgrade's own lock file.
7. The legacy tag's commit is on main, is an ancestor of the harness, and still carries the `.agents/`
   migration; after merge `git rev-parse forge-legacy-upgrade` gives that commit.
8. Make a check fail after vendoring, and separately press Ctrl-C and send a termination signal at
   that point: the client is back on its original branch, tracked files and git-local Forge state are
   exactly as before, new files upgrade wrote (including an ignored new `.envrc`) are gone, and no
   upgrade branch or throwaway checkout remains.
9. Leave a `forge-upgrade/...` branch behind as a killed run would: the next run refuses and prints
   recovery commands; running them returns the client to its original branch and a new run succeeds.
10. A client with its own skill, custom and edited agent profiles, an edited doc contract,
    docs/memory, grill records and an unknown `.factory` file upgrades with all of them unchanged and
    the edited doc contract named; exactly the old per-lens review files and the three root `.factory`
    files move, unchanged, under `.factory/archive/pre-<old>/` at their original paths, and nothing
    else moves.
11. A client signed off before the `harness.yaml` pin (sign-off only in its local run state) upgrades
    with the pin set to its sign-off record.
12. A file present in the harness checkout but not committed (ignored) is never copied into the
    client.

## Risks

- `forge doctor --fast` checks the machine, not the repo, and exits 1 when tools such as the Codex
  plugin are missing. Treating that as a failed upgrade would block every machine and CI run without
  them, so the check accepts its "required tool(s) missing" exit and fails only on a crash.
- Clients whose earlier upgrades copied a dirty harness, or who edited Forge files such as
  `.claude/settings.json`, are refused with the file named and the command that restores Forge's
  shipped bytes. That is stricter than today's silent overwrite and may stop some real checkouts until
  they tidy up.
- Old harness versions' own `forge init` must still run on today's Python. If the pre-rename version
  cannot, the helper uses the newest pre-rename commit whose init runs and records which one.
- A hard kill cannot run the rollback; the leftover branch is caught by the next run, and its recovery
  asks the developer to review leftover untracked files with `git status` before removing them.
- This is one session at its upper edge (about 1,300 changed lines, half of them tests). If it
  overruns, the smallest split is the helper plus the refusals (nothing written) first, then the write
  path and rollback.

---

## Technical notes

- New `factory/scripts/forge_cli/upgrade_flow.py` (target 450-550 lines).
  `cmd_upgrade(args: argparse.Namespace)` (`args.target`) resolves the harness with `repo_root()`
  (`factory_lib.py:36`, today's run-from-the-harness contract) and calls
  `run_upgrade(harness, target)`. CLEANUP later points `forge.py:199` at `upgrade_flow.cmd_upgrade`;
  `forge.py` is outside this task's write scope, and `forge upgrade` keeps running
  `upgrade.cmd_upgrade` (`upgrade.py:4593`) meanwhile, so no old test changes. Tests reach the new
  flow from the temp harness with
  `[sys.executable, "-c", "import sys, argparse; sys.path.insert(0, 'factory/scripts'); from forge_cli import upgrade_flow; upgrade_flow.cmd_upgrade(argparse.Namespace(target=sys.argv[1]))", <target>]`
  run with `cwd=<temp harness>`, and call `run_upgrade` in process only for the injected-failure
  cases.
- Shape: small functions for preflight (read-only, returns a plan or calls `fail`), the vendoring
  plan, apply, checks, commit and a rollback guard; `cmd_upgrade` stays thin. Constants for
  `BRANCH_PREFIX = "forge-upgrade/"`, the archive regexes, the trailer name,
  `LEGACY_TAG = "forge-legacy-upgrade"`, `LEGACY_COMMIT = "1a08c7bcc39dd9ce9f110b09b1291c71d0ff91b0"`
  and `ENSURE_PATHS` (`.envrc`, `.gitattributes`, `.gitignore`, `README.md`, `harness.yaml`,
  `*PROJECT_STARTERS` from `scaffold.py:55`). Every git call uses `clean_git_env()`
  (`factory_lib.py:212`), so the commit uses the client's configured identity.
- Order, reads only: refuse a non-git target or one without `constitution/VENDORED_FROM` ("use
  `forge adopt`"); refuse a tracked `.agents/scripts/forge.py` (pre-rename) with:
  `git -C <harness> fetch --tags origin`,
  `git -C <harness> worktree add --detach <dir> forge-legacy-upgrade`,
  `(cd <dir> && ./forge upgrade --target <target>)`, `git -C <target> add -A`,
  `git -C <target> commit -m "chore: legacy Forge upgrade"`, then run this upgrade again and remove
  `<dir>` with `git -C <harness> worktree remove <dir>`. Refuse a detached HEAD. Then take the lock
  `delegation_exclusion(target, "lean-upgrade", kind="review-selection", namespace="state")`
  (`delegate.py:613-627`; file `<git-dir>/forge/locks/state/lean-upgrade.lock` per
  `delegate.py:123-129`; same call as `upgrade.py:4615`) and run every other check under it. The lock
  file stays afterwards; every "nothing changed" comparison excludes exactly that file.
- Leftover run: any local branch `forge-upgrade/*` with `git config branch.<branch>.forgeOriginal`
  set is refused with: `git -C <target> reset --hard`, `git -C <target> checkout <original>`,
  `git -C <target> branch -D <branch>`, `git -C <target> worktree prune`, then review
  `git -C <target> status --ignored` for files the killed run left. The flow sets that config right
  after creating the branch and unsets it after a successful commit; `git branch -D` on rollback
  removes it.
- Harness: `git status --porcelain --untracked-files=all` empty; the vendored commit must pass
  `git merge-base --is-ancestor <old> HEAD` in the harness (an unknown object fails the same way). The
  new commit is harness `HEAD`. The snapshot is `git archive HEAD` extracted to a temp dir with
  stdlib `tarfile`; the old commit's `.codex` is archived the same way for classification only.
- Target: the same clean check. Worktrees from `git worktree list --porcelain -z`: a `prunable`
  entry, a missing folder or a failing `git -C <wt> rev-parse --absolute-git-dir` is refused by name.
- Work in progress, for EVERY listed worktree, with raw JSON reads that fail closed on unreadable
  files: pointer `<wt git-dir>/forge/run.json`, else `<wt>/.factory/run.json`, naming a story
  (`issue_key` or `story`) with `phase` other than `shipped`; any stage with `status == "active"` in
  `<wt git-dir>/forge/stages.json` (`stages.py:163`) or legacy `<wt>/.factory/stages.json`
  (`stages.py:159`); a non-empty `<wt>/.factory/quickfix.json` (`quickfix.py:27`, which covers
  quickfix, Lite and degraded); every `<wt>/plans/active/*.md` whose story
  (`read_plan_metadata(wt, path)`, `plans.py:96`) has no item with `status == "done"` in that
  worktree's roadmap (`load_items(wt)`, `roadmap.py:45`). One message lists every worktree and story.
- Vendored set: a path P is in Forge's area when `_is_harness_owned(P, new_snapshot)` or
  `_is_harness_owned(P, old_codex_snapshot)` (`upgrade.py:3827`, built on `UPGRADE_TREES`,
  `UPGRADE_FILES`, `CLAUDE_HARNESS_OWNED`, `COPY_WORKFLOWS`, `COPY_CODEX`, `DOC_CONTRACTS`:
  `upgrade.py:35-48`, `scaffold.py:29-50`), minus `constitution/VENDORED_FROM`,
  `constitution/VENDOR_MANIFEST.json` and client skills (`_is_client_owned_upgrade_skill_path`,
  `upgrade.py:4484`).
- Ownership from three `git ls-tree -r` maps (path to mode and blob id): target `HEAD`, harness
  `<old>` and harness `HEAD`. Comparing blob ids is the byte comparison against
  `git show <old>:<path>` and is immune to line-ending conversion. Per path, the target being absent,
  equal to old or equal to new means Forge-owned: write the new bytes, delete when new is absent
  (retire), or do nothing when already new. Otherwise it is client-owned:
  - under `DOC_CONTRACTS` or `.codex/agents/`: kept and named;
  - in `factory/`, `constitution/` or `harness/`, where Forge shipped the path at neither commit:
    refused with "move it out of `<folder>` and re-run";
  - anywhere else in Forge's area: refused with `git -C <harness> show <old>:<path> > <path>` as the
    restore hint.

  An ignored file (`git ls-files --others --ignored --exclude-standard`) at a path upgrade writes is
  refused, and so is any archive destination that already exists. Every destination passes
  `assert_target_destination` / `assert_target_file_destination` (`scaffold.py:288`, `:332`) in
  preflight, before the first write.
- Apply: record the original branch; copy `<git-dir>/forge/` (`git_control_dir`,
  `factory_lib.py:738`) aside minus the held lock; record which of the planned write paths (vendor
  writes, `ENSURE_PATHS`, archive destinations) exist now; then
  `git switch -c forge-upgrade/<old[:8]>-<UTC %Y%m%d%H%M%S>` and set
  `branch.<branch>.forgeOriginal`.
  1. `git mv` every tracked path matching
     `^\.factory/(stories|history)/[^/]+/(tasks/[^/]+/)?reviews/(quality|performance|security)\.json$`
     or `^\.factory/(decomposition|tests|verify)\.json$` to `.factory/archive/pre-<old[:8]>/<path>`;
     `.factory/archive/` is never matched.
  2. Write and retire per the ownership plan from the snapshot (`shutil.copy2`, modes kept).
  3. `ensure_missing(target, snapshot)` and `stamp_vendoring(target, new)` (below), then
     `remediate_windows_hook_entry(target)` (`scaffold.py:93`).
  4. `git add -A`. No staged change means already current: roll back, print
     "already at <new[:8]>", exit 0. Otherwise commit
     `chore(forge): upgrade Forge <old[:8]>..<new[:8]>` with trailer `Forge-Upgrade: <old>..<new>`
     (full shas), run the checks, then unset `forgeOriginal`.
- Reuse from `upgrade.py` by an in-place split of `_cmd_upgrade_locked`, so the lines keep their
  place and indentation and the old path calls the same functions:
  - `ensure_missing(target, harness) -> list[str]` is the block at `upgrade.py:4817-4948`: `.envrc`,
    JSONL `.gitattributes`, the sign-off carry at `4829-4858`, README onboarding, the `.gitignore`
    blocks and removal of the old `.gstack/` rule, ephemeral untrack, and `PROJECT_STARTERS`.
  - `stamp_vendoring(target, commit)` is `4951-4957`: `VENDORED_FROM` plus `write_manifest`
    (`check_vendor_integrity.py:64`).

  The old caller keeps `commit = head_sha(harness) or "unknown"`.
- Checks: `git worktree add --detach <tmp> HEAD` from the target. Run from the checkout with
  `sys.executable`: `factory/scripts/check_dual_runtime.py`, `check_factory_scaffold.py`,
  `check_vendor_integrity.py`, `forge.py next`, `forge.py audit`, and `forge.py doctor --fast` (exit
  0, or exit 1 with its "required tool(s) missing" line, per `doctor.py:1694-1706`). The board data
  runs as a subprocess, not in process, so it loads the upgraded tree's own code with a fresh cache:
  `[sys.executable, "-c", "import sys; from pathlib import Path; sys.path.insert(0, 'factory/scripts'); from forge_cli import board; board.aggregate_state(Path.cwd())"]`
  with `cwd=<tmp>` (`board.py:571`). Then `git status --porcelain --untracked-files=no` must be
  empty. In `finally`: `git worktree remove --force` and `git worktree prune`. Linked-worktree state,
  including `forge next`'s heal marker, lives under `<common>/worktrees/<name>/` and goes with it.
- Rollback guard around everything after the branch is created: `except BaseException` (so
  `KeyboardInterrupt` and `SystemExit` included), and during apply SIGTERM is turned into an exception
  by a temporary `signal.signal(SIGTERM, ...)` handler, restored afterwards. Rollback:
  `git reset --hard`; `git checkout <original>`; `git branch -D <branch>` (drops its config); delete
  every recorded write path that did not exist before and is not tracked at the original HEAD, plus
  the directories it created that are now empty (no `git clean`); restore `<git-dir>/forge/` except
  the held lock; remove the throwaway worktree; then re-raise.
- Report: the upgrade branch; archived count and folder; refreshed, added and retired Forge paths;
  kept client-edited doc contracts and profiles; `ensure_missing` notes; next steps:
  `git show --stat HEAD`, `git diff <original>..HEAD`, `git push -u origin <branch>`, open a PR into
  `<original>`.
- Legacy tag: `forge-legacy-upgrade` at `1a08c7bcc39dd9ce9f110b09b1291c71d0ff91b0` (on
  `origin/main`; its `upgrade.py` still has `_check_legacy_retirable` and `_retire_legacy_agents`, and
  its `forge` launcher runs `factory/scripts/forge.py`). A delivery step, not a code change: the
  coordinator runs `git tag forge-legacy-upgrade 1a08c7bc` and
  `git push origin forge-legacy-upgrade` at merge. The test checks the constant, not the tag.
- Fixture `factory/tests/old_client.py`:
  - A session-scoped temp harness: `git clone --shared --no-checkout <git-common-dir of HARNESS>`,
    detached at `HARNESS`'s HEAD, overlaid with its modified, untracked non-ignored and deleted files
    (`git ls-files -m -o -d --exclude-standard`) and committed. It is clean, holds the code under test,
    and descends from every old commit.
  - `build(sha)` runs `git worktree add --detach` in the temp harness, then that version's
    `forge.py init` (under `factory/scripts/`, or `.agents/scripts/` before the rename) with
    `gc.auto=0`, then commits with a local test identity and sets `refs/remotes/origin/main`.
  - Builds are cached per session; each test gets a `shutil.copytree(symlinks=True)` copy.
  - Versions: `8563f8c6` (July), `43f6bede` (September), `47516c55` (Lean era), and pre-rename
    `fc2fc1db` (`2ebba90d^`).
  - Missing history fails with a clear message instead of skipping; CI checks out with
    `fetch-depth: 0` (`factory-scaffold.yml:14`).
- Tests: `factory/tests/test_upgrade_flow.py`. The slow builds sit behind the session fixture. Each
  refusal case compares HEAD, branches, worktree list,
  `git status --porcelain --ignored --untracked-files=all` and a digest of `<git-dir>/forge/` minus
  `locks/state/lean-upgrade.lock`, before and after. Interruption cases patch the check step in
  process to raise, raise `KeyboardInterrupt`, or send the process SIGTERM (skipped on Windows). The
  leftover-branch case builds the branch and its `forgeOriginal` config by hand.
- Deferred to CLEANUP: wiring `forge upgrade`, `--park` and the `Parked:` trailer, the ticket-check
  exemption, the "reviewed before upgrade" board label, message rewording, the harness-health step,
  the doctor skill check, and deleting the old machinery and tests. Deferred to DOCS: docs and the
  skill.
