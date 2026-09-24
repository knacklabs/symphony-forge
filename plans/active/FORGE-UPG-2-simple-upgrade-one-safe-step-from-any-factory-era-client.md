# Simple upgrade: one safe step from any factory-era client

## What and why

Upgrading a client repo to the current Forge doesn't work today. We rebuilt real client versions
from July to September and upgraded each one: none finished cleanly. Some were left half-upgraded,
stories in progress got stuck, and every upgraded client failed its next upgrade. The upgrade code is
about 4,800 lines, mostly for converting half-finished work between versions. We replace it with one
simple step that git makes safe. Client upgrades stay on hold until it ships.

## What changes for you

- Upgrade runs only on a Forge client with no uncommitted changes, and only forward. A repo without
  Forge is pointed to `forge adopt`; a very old client (before July 24) gets exact instructions for
  one older step first.
- If any checkout of the repo has a story, task, plan or Lite fix in progress, upgrade stops and names
  it: finish it on your current version, or park it with `--park <story>` to re-plan it later.
- Upgrade works on its own new branch and commits there. If any step or check fails, it puts you
  back on your original branch exactly as it was.
- Only the old review files current Forge can't read move into `.factory/archive/`. Everything else
  you own stays: stories, history, roadmap, decisions, docs you edited, your skills and agent
  profiles, and your sign-off.
- Upgrade ends by checking your skills the same way `forge doctor` does, and names anything missing
  or outdated (impeccable included) with `./forge doctor --fix`; it never blocks the upgrade.
- Upgrade prints what to do next: review the commit, open the PR. The upgrade skill follows it, then
  runs its existing after-upgrade steps (project backfill and re-authoring pending stories).
- Running it again changes nothing, and later upgrades work the same way.
- The automatic upgrade PR from the harness-health workflow goes away, because it can't see work in
  progress on a developer's machine.

This also covers the separate "upgrade preserves doc contracts" roadmap item: docs you edited are kept
and named in the report, never overwritten.

Today only two of the seven local myclaw checkouts can upgrade; the others first need their stories
finished or parked.

## Done when

- Clients built from the July, September and Lean-era harness versions, with nothing in progress,
  upgrade cleanly, and Forge's everyday commands then run without errors. A pre-July-24 client is
  refused with the older-step instructions, and following them reaches current Forge.
- A second upgrade changes nothing; a later one works; going backwards is refused.
- Work in progress anywhere in the repo, a dirty tree, an unreadable checkout or a non-Forge repo is
  refused before anything is written; a parked story can be planned again afterwards.
- A failure midway leaves the client exactly as it was.
- Client-owned files (including edited docs and the sign-off) survive, old review files end up in the
  archive, and the board shows those tasks as reviewed before the upgrade.
- The upgrade PR passes the ticket check; a change outside what upgrade produces is refused.
- The old migration code is deleted, and the client-upgrade hold is lifted after a real myclaw
  checkout upgrades cleanly.

## Risks

- Recurring-findings history starts fresh for archived reviews; the reviews themselves are kept.
- The ticket check cannot prove a harness file holds exact harness bytes without the harness itself,
  so a hand edit disguised inside an upgrade commit is caught by review, as every change is under
  full access.

## What I need from you

Approving this plan also approves one wording fix: decision 0088's example list says old grills and
approval files are archived; the confirmed spec archives only the old review files and three root
files, so the docs task corrects that example to match.

---

## Technical approach

- New flow in `factory/scripts/forge_cli/upgrade_flow.py` (target ~400-500 lines), built and tested
  first without being wired in; CLEANUP switches `forge upgrade` to it together with the ticket-check
  and harness-health changes, so nothing half-works in between; all preflight under the existing git-local lock: harness clean; target
  `constitution/VENDORED_FROM` present and an ancestor of harness HEAD; pre-rename `.agents/`
  machinery refused with the `forge-legacy-upgrade` route; target clean (`--untracked-files=all`);
  every listed worktree readable; in-flight check per worktree (git-local pointer else
  `.factory/run.json` phase not shipped; active git-local stage; `.factory/quickfix.json`; any
  `plans/active/` plan in any worktree whose roadmap item is not done); archive destinations that
  already exist; unshipped client files in
  `factory/`/`constitution/`/`harness/` (except client skills) and client or ignored files at required
  machinery paths refused.
- Source bytes: vendoring copies from a committed snapshot of the harness (`git archive HEAD` into a
  temp dir), never from the working tree.
- Run, on branch `forge-upgrade/<sha>-<ts>`: copy `<git-dir>/forge/` aside; apply `--park` (archive the
  story's state and `plan-meta.json`, move its plan to `plans/archive/`, clear the pointer, reset the
  roadmap item) — parking is inside the branch and the rollback; `git mv` the archive table into
  `.factory/archive/pre-<sha>/<path>`; vendor with the existing copy, client-skill preservation,
  ensure-missing, sign-off carry (legacy `run.json` sign-off → `harness.yaml` pin, kept) and
  `write_manifest` code; ownership by byte-compare against `git show <VENDORED_FROM>:<path>` for all
  harness files INCLUDING doc-contract files (client-edited ones are kept and named in the report).
- Checks run in a throwaway worktree of the upgrade commit (`check_dual_runtime`,
  `check_factory_scaffold`, `check_vendor_integrity`, `forge next`, `forge audit`,
  `forge doctor --fast`, board `aggregate_state`); any tracked change they make is a failure; the
  throwaway worktree is removed either way.
- Commit with trailers `Forge-Upgrade: <old>..<new>` and one `Parked: <story>` per parked story; print
  next steps. On any failure or interruption (including Ctrl-C): reset, check out the original
  branch, delete the upgrade branch, delete exactly the files the upgrade wrote that were not tracked
  before (its own list, not `git clean`), restore `<git-dir>/forge/` except upgrade's own lock file.
  A detached HEAD is refused up front.
- Ticket check (`check_pr_ticket.is_harness_revendor`): a `Forge-Upgrade` commit is exempt when every
  change is one the upgrader produces — harness-owned paths, the manifest, 100% renames of
  archive-table paths into `.factory/archive/pre-*/`, Forge's `.gitignore`/`.gitattributes` blocks and
  old-rule removals, the README onboarding block, the sign-off pin, and, for each `Parked:` story, its
  plan move, `plan-meta.json` archive and roadmap status change. Anything else needs a normal ticket.
- Delete: the Lean inventories, revalidation, resume plans, preserve backups, profile hash tables, the
  `.agents` layout migration and the `run.json` pre-check; `approval.py`'s import of
  `_validate_completed_manifest`; `factory/schemas/lean-workflow-migration.json`; old tests.
- Tag `forge-legacy-upgrade` at a commit already on main that still carries the `.agents` migration
  (1a08c7bc), so the route exists as soon as CORE ships.
- Board: a task with no selected review but archived review files shows "reviewed before upgrade".
- Messages: `tasks.py`'s legacy task-grill advice and other "run forge upgrade" texts for in-progress
  work say "finish or park, then upgrade"; harness-health's automatic upgrade step is removed.
- Doctor warns when the installed upgrade skill differs from the harness copy. The upgrade report ends
  with doctor's required-skill check (missing or outdated skills, and `./forge doctor --fix`), never
  blocking.
- Roadmap: `upgrade-preserves-doc-contracts` is marked covered by FORGE-UPG-2.
- Docs: retire `docs/specs/legacy-upgrade.md`; update `docs/getting-started.md`, WORKFLOW.md, the
  parity architecture's migration section, decision 0088's example list (approved above), and
  `install/claude/knacklabs-upgrade-project/SKILL.md` (finish or park, clean, run, follow the printed
  steps, then the existing backfill and re-authoring steps).

## Task decomposition

The owner chose three tasks. CORE first, then CLEANUP, then DOCS. Each ships its own pull request.

| Label / exact task ID | What it delivers | Depends on | user_facing |
|---|---|---|---|
| Core / CORE | Old-client test fixture; `upgrade_flow.py` with preflight, committed snapshot, archive, byte-ownership vendoring incl. doc contracts, sign-off carry, throwaway-worktree checks, commit and rollback, tested but not yet wired; the legacy tag | none | false |
| Cleanup / CLEANUP | `forge upgrade` switched to the new flow; `--park`; old machinery, schema, approval coupling and old tests deleted; ticket-check exemption; board label; reworded messages; harness-health step removed; doctor skill check; skills-ready report; roadmap coverage note | CORE | false |
| Docs / DOCS | Specs, docs, decision 0088 example fix, upgrade skill | CLEANUP | false |

## Verify plan

Each task: focused tests, `forge task close` (full suite plus one three-lens review), the CI-only
checks, green CI. The fixture-driven tests cover every acceptance item: clean upgrades from the three
versions followed by `forge next`, `forge audit`, `forge doctor --fast` and board data; the pre-rename
refusal and the two-step route (older upgrader from the legacy commit, then the new one) reaching
current; idempotence and a newer-harness upgrade; every refusal leaving the repo byte-identical; an
injected failure after vendoring restoring branch, files and git-local state; parking; archive paths;
the ticket check accepting the upgrade commit and refusing an added hand-made change outside its
categories. Before lifting the client-upgrade hold: upgrade a copy of myclaw-partb and confirm its
everyday commands.
