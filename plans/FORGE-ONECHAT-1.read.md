---
reader: codex (gpt-6-sol)
read_at: 2026-09-27T15:25:59+00:00
read_hash: 2e4a90e27b9e0affe8ebc23d65e0bb06d31e8662
amended_hash: 6e84649968854169a3671f548f389fabcfbec350
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. The confirmed spec is a missing prerequisite, but the plan makes it a task of this story.
   `docs/specs/one-chat-approval.md` is absent, and the roadmap item has no spec link. The owner must confirm the spec before item 1 is done; that cannot be completed without asking them. Simpler: confirm and link the spec in a preceding fix, then remove the spec task from this story.
   Disposition: keep the spec is confirmed by the owner and on the roadmap in the promoted task's branch, which this read didn't see; the task stays as the record

2. REGISTRY does not pin when registration happens.
   `forge init` creates `forge.toml` during the command, while `forge migrate` creates it in a new worktree. Registering at command dispatch could remember an unsuccessful init or make `forge migrate --dry-run` change machine state despite its “Nothing was changed” promise. REGISTRY must pin the timing and dry-run rule.
   Disposition: keep registration happens only after success, never on a dry run, only with forge.toml

3. APPROVE needs a repo identity rule before combining candidates.
   The chat’s repo will normally already be in `remembered()`. Adding it again can count its one waiting story twice; a chat started in a worktree also has a different path from the remembered main checkout. REGISTRY must pin canonical repo identity for APPROVE to deduplicate.
   Disposition: keep main_checkout pins identity; APPROVE deduplicates by it

4. Moving the replay marker to only the matched story’s repo weakens the existing replay check.
   After one event approves a story in repo A, the same event could later approve an identical waiting story in repo B because B has no marker. APPROVE must pin how it checks consumed events across repos while keeping the marker in the story’s repo.
   Disposition: keep the marker is checked in both the chat's and the story's repo and written to both

5. The version refusal needs a pinned order and message.
   `repo.check_pin()` validates the target’s whole config before comparing versions, so a newer config can produce a config error instead of the promised version refusal. Its current advice also says to install the repo’s pinned version, contrary to item 4’s instruction to update the repo pin. APPROVE must pin a version-first read and the required refusal text before target-repo writes.
   Disposition: keep the version key is read first and the refusal text is pinned

6. `New moving parts: none` contradicts REGISTRY.
   A persistent machine-wide `forge/repos` file and its reader and writer are new moving parts. Name them there and tie their need to item 2; the file can remain a plain standard-library format.
   Disposition: keep named the file and its module as the new moving part for item 2
