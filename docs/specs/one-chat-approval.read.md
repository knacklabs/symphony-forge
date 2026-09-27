---
reader: codex (gpt-6-sol)
read_at: 2026-09-27T15:20:44+00:00
read_hash: 773b37f78e7dfd1a971acb7e1756e5b932e3b5db
amended_hash: 90572c5c782d2fd71205139b01ac82976512ddad
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. The git-hook boundary contradicts the approval path.
   `approval._approve` uses `repo.commit_state`, which runs `git commit` in the story’s checkout and therefore runs that repo’s git hooks. The spec says running another repo’s git hooks is out of scope. Clarify whether that exclusion means only importing its rules into the chat, or whether the destination commit must avoid its hooks.
   Disposition: keep clarified: the approval commit runs the story repo's git hooks; out of scope is only loading its chat hooks

2. Replay refusal is scoped to the chat’s repo today.
   `approval._approve` checks and writes the consumed-event marker under `repo.forge_dir(top)`, where `top` is the chat’s repo. The spec requires replay refusal across repos but does not say where the shared marker lives or how concurrent approvals recheck the single matching story before committing. Pin that ownership and ordering before implementation.
   Disposition: keep the replay marker lives in the story's repo, checked after the one match and before any write

3. The remembered-repos list lacks a buildable contract.
   Specify its config path on each supported platform, file format, checkout identity and deduplication rule, and behavior when a write fails or two commands update it together. A directory that merely still contains `forge.toml` can also belong to a different checkout after replacement. The guide’s “every Forge repo on the machine” claim exceeds the specified *remembered* repos.
   Disposition: keep pinned the path, format, identity, dedup and write-failure rule; a replaced checkout still needs the exact match and cold read; guide says repos this machine has used

4. The version-mismatch instruction conflicts with the existing pin refusal.
   `repo.check_pin` currently tells the owner to install the version pinned by the repo. This spec instead says to upgrade the repo. Specify which version should change and the actionable refusal text.
   Disposition: keep the refusal names both versions and says to bring the repo's pin to the installed version

5. The Remote Control skill would still give obsolete approval instructions.
   Its description and example say approval requires a session in the story checkout. The spec says no Forge step needs that session, but only calls for a guide update. Include the skill’s approval guidance in the required change.
   Disposition: keep the Remote Control skill's description and example are part of the change
