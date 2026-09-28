---
reader: codex (gpt-6-sol)
read_at: 2026-09-28T11:09:59+00:00
read_hash: eb1f99f6c1a8de9f5dde59522ba2a3e23a8fbe66
amended_hash: 43429b186149d3e1725450ce616ee3a0553c59d8
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. The routing rule contradicts “Forge’s own work stays on Codex.”
   A `User-facing: yes` row can describe Forge CLI work, not just screens; FORGE-PROTO-1’s GATE task is an example. Pin a rule that identifies design work without routing Forge tasks to Claude.
   Disposition: cut design work now means user-facing work in client repos only; Forge's own repo is unchanged.

2. The promised design guidance has no implementing task.
   The current brief calls impeccable the one UI skill, and `forge doctor` checks skills only for the configured worker. No task owns delivery of Emil’s design engineering or the app baseline to a Claude worker, or checks that Claude can use the required guidance.
   Disposition: cut the Notes pin that the UI skills fix, which must merge first, delivers the guidance and the doctor check.

3. ROUTE has an unstated cross-story prerequisite.
   The exact prototype allowance is added by FORGE-PROTO-1’s GATE task and is absent from this branch’s `fix start`. Pin when GATE must land before this route can deliver prototype-fix behavior.
   Disposition: cut the Notes pin that ROUTE starts after FORGE-PROTO-1's GATE has merged.

4. The fallback’s checkout test needs a before-run baseline.
   `forge work` commits state before starting the worker, and the checkout may already be dirty. Define “Claude changed the checkout” by comparing HEAD and working-tree/index state immediately before and after Claude, so existing changes do not suppress the promised fallback.
   Disposition: cut Done-when 4 now compares HEAD, index and working tree just before and after the Claude run.

5. The Codex fallback lifecycle is not pinned.
   Current readiness, locking, recovery, and conversation continuation all depend on `workers = "codex"`. Design work overrides that setting, so ROUTE must explicitly use those Codex safeguards and resume the item’s existing Codex conversation when falling back.
   Disposition: cut Done-when 4 and the Notes say the fallback runs with every safeguard of a Codex round, continuing the item's conversation.

6. Simpler: combine SPEC and DOCS into one documentation task.
   They have independent documentation scopes and no ordering need; one task can cover Done-when items 1 and 5.
   Disposition: cut SPEC now covers the decision and the guide; DOCS is gone.
