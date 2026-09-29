---
reader: codex (gpt-6-sol)
read_at: 2026-09-29T03:44:18+00:00
read_hash: 6d991c50eabb038e34edfe4cc9554f3bc74bbe11
amended_hash:
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. Unproven: Done-when items 1–5 have no confirmed spec to trace to.
   No linked confirmed spec was found, and the [product brief](/docs/product/BRIEF.md) does not state these upgrade behaviors or a success measure.
   Disposition: keep this story comes from a reported bug, not a planned feature; the Why states the evidence, and Notes say so.

2. Trap: item 3’s “open fix” exception needs a precise eligibility rule.
   [check_pin](/src/forge/repo.py:290) currently checks only the caller’s pin. PENDING must pin which fix states, branches, and local worktrees count as pending, and what happens if more than one qualifies; otherwise an old worktree could keep the default branch’s version gate open.
   Disposition: cut: details item 3 pins the rule: a local worktree on an unmerged fix/ branch pinning exactly the installed version; the first when several.

3. Trap: items 3 and 4 must route through the CLI version gate.
   [cli._run](/src/forge/cli.py:73) calls `check_pin` before either command handler. The approval warning and `forge close` folder message cannot work from a mismatched checkout through handler changes alone. Pin the command-specific routing and test the public commands.
   Disposition: cut: details item 3 puts the exception in repo.check_pin called from cli._run, skips it for forge hook, and tests public commands.

4. The PENDING → SYNCED After link exists only because both edit `doctor.py`.
   The [story](/plans/FORGE-UPGRADE-1.md) gives that as its sole reason. Assign the shared `doctor()` comparison and wording seam to one task, or put the shared edit in a small last wiring task; retain After only for a code dependency.
   Disposition: cut: only DOCTOR changes doctor.py; SYNCED reuses its comparison; no After link.

5. Item 5 has no workable untracked-file path yet.
   [migrate](/src/forge/migrate.py:174) refuses a checkout with untracked files, while `_plan` reads tracked Git trees and `_apply` runs in a new worktree. Pin where the leftovers are listed, confirmed, and removed, including the dry run and link checks.
   Disposition: cut: item 5 moves to forge doctor and doctor --fix, which already exist, instead of migrate.

6. Risks: none contradicts item 5.
   Deleting untracked files is a one-way step with no Git history to restore them. Name that data-loss risk and the confirmation boundary under Risks.
   Disposition: cut: Risks names the deletion and its confirmation boundary.

