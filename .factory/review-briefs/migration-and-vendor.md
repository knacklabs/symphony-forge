# Plan-contract review brief — migration-and-vendor

For each contract, emit a verdict — implemented | partial | missing — with file:line evidence, recorded as contract_verdicts in the quality artifact. Then review the diff normally; the contract check does not replace the quality/performance/security lenses.

## Task migration-and-vendor

### Plan contracts

- **CFS6-C1**
  - Source: plans/active/FORGE-CFS-1-story-state-stops-conflicting-across-prs.md#acceptance-criteria
  - Statement: intake on a legacy fixture starts the new layout with old artifacts untouched and readable
- **CFS6-C2**
  - Source: plans/active/FORGE-CFS-1-story-state-stops-conflicting-across-prs.md#acceptance-criteria
  - Statement: the merge-simulation test merges two concurrent story branches with zero .factory conflicts

### Reviewer focus

This is the ATOMIC activation (0046): intake sets the marker AND every audited legacy-path consumer migrates in the SAME task, gated by a green full suite - no half-migrated state ships. The marker is intake creating .factory/stories/<KEY>/ (story_uses_scoped_layout keys on its existence). Migrate the audited hand-joined reads to story-dir-first + legacy fallback (task 1's discipline): plans.py:135 plan grill + plans.py:78 history stages; check_board_complete.py:31 history dir; findings.py + audit.py history reads - so a shipped new-layout story (evidence in .factory/stories/<KEY>/, no history archive) is visible. AC1: intake on a LEGACY fixture leaves old singletons/history UNTOUCHED and readable (no data migration - legacy stays legacy, new stories go new-layout). AC2 headline: the merge-simulation test intakes two stories in two worktrees, records evidence in each, and merges one branch into the other's base asserting ZERO .factory conflicts. forge upgrade re-vendors scripts wholesale so clients get the change automatically at their next intake - verify the re-vendor includes the new files; no bespoke migration of client data. If the diff overruns the budget, the split is a SIGNAL (consumer-migration vs intake-activation), but they must land in the same story before ship. S-0007: TWO real production regressions the activation exposed (fix behavior, not tests): phase.py hand-reads legacy .factory/{decomposition,tests,verify,reviews} -> route through evidence_path (story-dir-first, legacy fallback) so scoped-story phase + design-skill routing work (test_next_routes_design_skills_by_feature_type); pr_ready's scoped new-layout ship path must handle .factory/scratchpad.md like the legacy path (test_precompact_scratchpad_snapshots_facts_and_findings). phase.py and pr_ready.py added to write_scope. The other 30 failing required tests are stale-test migrations (fix the tests per the two patterns).
