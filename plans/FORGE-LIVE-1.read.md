---
reader: codex (gpt-6-sol)
read_at: 2026-09-28T13:39:36+00:00
read_hash: 944512ba26a5f556af5bb7460faefe07e4a46dd3
amended_hash: 81f480b35842522cf0644303bc3b743fdbec6d71
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. No confirmed spec anchors the six Done-when items.
   The story names behaviours, but no linked confirmed spec supplies their success measure. Confirm that contract before approval so the tasks can be checked against it.
   Disposition: keep the owner decided this story's behaviour in chat on 2026-09-28; the story doc is the contract, as for the other stories started from a fix.

2. The live story gate is incomplete.
   STAGE names `story.py` and `records.py`, but `approval._approve` still requires client sign-off, and `nextstep._approval` still tells a live repo it cannot approve a story. Put both paths in STAGE’s scope and test creating **and approving** a live story.
   Disposition: cut STAGE now covers approval and forge next's approval step, and Done-when 2 tests creating and approving a live story.

3. The “no auto-merge” and “no light review” promises have no current task owner.
   The Notes defer their use of `repo.is_prototype(top)` to FORGE-SALES-1 and FORGE-AHA-1, whichever lands later. Pin the integration and owning task for either landing order; a coordinator check on close does not build missing behaviour.
   Disposition: cut STAGE switches every prototype rule already on main when it starts; later SALES and AHA tasks use is_prototype themselves.

4. ADOPT cannot reach “ready to close” through the current bootstrap path.
   `close.py` treats only `kind == "migrate"` specially: it skips the Forge check before Forge exists on the base branch and enables protection after merge. ADOPT excludes `close.py` and does not pin its fix-state kind or the first PR’s check list. Assign and specify that path before ADOPT starts.
   Disposition: cut ADOPT's scope adds close.py and pins the adopt kind handled like migrate.

5. The pass-with-a-note rule can exempt a branch Forge started.
   `prcheck._started` identifies Forge work solely from state in the PR head. A PR that removes or changes that state would look like an outside branch and pass. Pin a trusted way to distinguish outside branches before changing the refusal.
   Disposition: cut Forge branches are told apart by their name prefix, not by state a pull request can remove.

6. The adoption inputs and preservation rule need a concrete contract.
   ADOPT’s options cover tests, checks and interfaces, while the promised answers about approver, merger and forbidden paths have no named record or enforcement point. Also specify what `forge init` does when an existing repository owns a path `forge sync` would write, especially its workflow or skill files; the current sync path rewrites generated destinations.
   Disposition: cut the approver, merger and never-touch paths go in AGENTS.md's House rules, and init stops, changing nothing, when a file it would write already exists.
