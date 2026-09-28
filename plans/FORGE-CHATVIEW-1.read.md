---
reader: codex (gpt-6-sol)
read_at: 2026-09-27T17:02:41+00:00
read_hash: 0df693510bfa3a99a04e6cd837b88b5a83d77253
<<<<<<< HEAD
amended_hash: 11798d2bc5c68bbd2e179f54c0906e5f9117f7c2
=======
amended_hash: 931efaa363aca13db58280a28fbf80a3319455f7
>>>>>>> origin/main
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. The story depends on a confirmed spec that is absent.
   `docs/specs/codex-chat-view.md` does not exist, and the roadmap entry has no spec path. The code tasks therefore cannot be checked against spec behaviour. The spec task also cannot itself supply the owner confirmation required by Done-when 1. Create and confirm the spec before approving the code work, then make its tasks depend on that contract.
   Disposition: keep the spec is confirmed by the owner and on the roadmap in the promoted task's branch, which this read didn't see

2. START does not pin how to identify the one matching Codex project.
   Done-when 2 names `project/list`, but gives no response fields, pagination rule, or path comparison rule for the main checkout. Pin those before updating a chat’s `projectId`, so an ambiguous match leaves it in place.
   Disposition: keep pinned pagination, the roots field and resolved-path matching

3. START and ATTACH lack a complete pull request handoff.
   `attach(top, item, pr)` has no pinned `pr` shape. Today `_pull_request` returns no URL, owner, repo, or head branch, while `_publish` returns nothing after creating a PR. Pin the source of those fields and whether `thread/attachment/add` deduplicates by identity; ATTACH needs both to cover new and existing PRs.
   Disposition: keep pinned the gh pr view source, the dict passed to codex.attach, and the app-server's one-per-identity rule

4. WORDS does not define the fix-round number.
   “Fix round <n>” needs a source and a first value, including when a later `forge work` starts a fresh chat. The current `later` check and the brief’s `fix-round` check use different conditions, so the task cannot derive one exact preview line from the story.
   Disposition: keep n counts recorded turns from the turn log, so a fresh chat keeps counting

5. The stated cross-story wait is not enforced by Scope overlap.
   Forge checks overlap against tasks already started; it does not wait for unstarted FORGE-STEER-1 or FORGE-MERGE-1 tasks. Name their required merged tasks as a start precondition, or remove the claim that Scope overlap orders this work.
   Disposition: keep the Notes now state the start order the coordinator keeps, instead of claiming the overlap check enforces it
