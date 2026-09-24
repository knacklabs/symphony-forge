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

- New flow in `factory/scripts/forge_cli/upgrade_flow.py` (target ~400-500 lines) wired to
  `forge upgrade`; all preflight under the existing git-local lock: harness clean; target
  `constitution/VENDORED_FROM` present and an ancestor of harness HEAD; pre-rename `.agents/`
  machinery refused with the `forge-legacy-upgrade` route; target clean (`--untracked-files=all`);
  every listed worktree readable; in-flight check per worktree (git-local pointer else
  `.factory/run.json` phase not shipped; active git-local stage; `.factory/quickfix.json`; any
  `plans/active/` plan whose roadmap item is not done); unshipped client files in
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
  next steps. On failure: reset, check out the original branch, delete the upgrade branch,
  `git clean -fd` of added paths (never `-x`), restore `<git-dir>/forge/`.
- Ticket check (`check_pr_ticket.is_harness_revendor`): a `Forge-Upgrade` commit is exempt when every
  change is one the upgrader produces — harness-owned paths, the manifest, 100% renames of
  archive-table paths into `.factory/archive/pre-*/`, Forge's `.gitignore`/`.gitattributes` blocks and
  old-rule removals, the README onboarding block, the sign-off pin, and, for each `Parked:` story, its
  plan move, `plan-meta.json` archive and roadmap status change. Anything else needs a normal ticket.
- Delete: the Lean inventories, revalidation, resume plans, preserve backups, profile hash tables, the
  `.agents` layout migration and the `run.json` pre-check; `approval.py`'s import of
  `_validate_completed_manifest`; `factory/schemas/lean-workflow-migration.json`; old tests.
- Tag `forge-legacy-upgrade` at the last harness commit that still carries the `.agents` migration.
- Board: a task with no selected review but archived review files shows "reviewed before upgrade".
- Messages: `tasks.py`'s legacy task-grill advice and other "run forge upgrade" texts for in-progress
  work say "finish or park, then upgrade"; harness-health's automatic upgrade step is removed.
- Doctor warns when the installed upgrade skill differs from the harness copy.
- Roadmap: `upgrade-preserves-doc-contracts` is marked covered by FORGE-UPG-2.
- Docs: retire `docs/specs/legacy-upgrade.md`; update `docs/getting-started.md`, WORKFLOW.md, the
  parity architecture's migration section, decision 0088's example list (approved above), and
  `install/claude/knacklabs-upgrade-project/SKILL.md` (finish or park, clean, run, follow the printed
  steps, then the existing backfill and re-authoring steps).

## Task decomposition

Each task ships its own pull request. OLD-CLIENT-FIXTURE first; CORE after it; PARK and DELETE-OLD
after CORE (disjoint: PARK adds to `upgrade_flow.py`'s park step, DELETE-OLD removes `upgrade.py`
machinery and old tests); EDGES after DELETE-OLD; DOCS-SKILL last.

| Label / exact task ID | What it delivers | Depends on | user_facing |
|---|---|---|---|
| Fixture / OLD-CLIENT-FIXTURE | Test helper that scaffolds a client from any harness commit in this repo's history (8563f8c6, 43f6bede, 47516c55, pre-2ebba90d) | none | false |
| Core / CORE | `upgrade_flow.py`: preflight, committed snapshot, archive, byte-ownership vendoring incl. doc contracts, sign-off carry, throwaway-worktree checks, commit, rollback; wired to `forge upgrade`; new tests | OLD-CLIENT-FIXTURE | false |
| Park / PARK | `--park` inside the branch and rollback, with its refusals and tests | CORE | false |
| Delete / DELETE-OLD | Old machinery, schema, approval coupling and old tests removed; legacy tag | CORE | false |
| Edges / EDGES | Ticket-check exemption, board label, reworded messages, harness-health step removed, doctor skill check, roadmap coverage note | DELETE-OLD | false |
| Docs / DOCS-SKILL | Specs, docs, decision 0088 example fix, upgrade skill | EDGES | false |

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
