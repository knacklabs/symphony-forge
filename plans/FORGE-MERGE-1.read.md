---
reader: codex (gpt-6-sol)
read_at: 2026-09-27T15:01:43+00:00
read_hash: fc2a4bd76cbc5b072aea3358b6114951674a8527
amended_hash: a72ee932f253200f33e23cbbbf4ee53485f129ae
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. The spec prerequisite cannot be completed as a task without another human decision.
   `docs/specs/agent-merge.md` does not exist, and the roadmap entry is a placeholder without a spec link. Done-when 1 requires owner confirmation, which `spec confirm` requires before `roadmap add`. Confirm the spec and place it on the roadmap before approving this build story. Cut or defer: the spec task from this story.
   Disposition: keep the spec is confirmed by the owner and on the roadmap in the promoted task's branch, which this read didn't see; the task stays as the record

2. A previously fetched default branch can retain merge permission after the owner revokes it.
   Done-when 2 explicitly uses `origin/<default>` “as last fetched.” `forge merge` needs to fetch the default branch before checking permission, then refuse if the current default-branch setting is not `merge = "agent"`.
   Disposition: keep forge merge now fetches the default branch before reading the setting

3. The source of the required checks is unpinned.
   The notes say to wait on `forge.toml`’s `checks`, while `close` currently reads that list from the item’s checkout. An item could narrow its own checks even though it cannot grant itself merge permission. Pin the checks used by `forge merge` to the default branch’s configuration, and specify how it verifies the clean review when that list does not include `forge-pr-check`.
   Disposition: keep forge merge reads the checks from the default branch too; the clean review comes from the ready record

4. The ready record needs a persistence rule.
   `close` pushes the head before checks finish; committing `ready` and `ready_commit` afterward creates a different head from the one that passed. Specify where the record lives and how `forge merge` trusts and validates it without changing the checked commit.
   Disposition: keep the ready record lives in .git/forge/ready/<item>.json, never committed, so the checked head stays

5. Split: `MERGE` → setting and ready recording (2–3); merge command and cleanup (4–5).
   `MERGE` covers four Done-when items and spans five Python files plus the guide. The first part should pin `merge`, `ready`, `ready_commit`, and `forge merge <item>` for the second.
   Disposition: keep split into READY (setting, record, next step, stub command) and MERGE (the merge and tidy-up)

6. Both implementation tasks claim `docs/guide.md`.
   `MERGE` owns the command-list row and `DOCS` owns the setting section. Give the guide to one task, or put its edits in a small last wiring task. Keep any dependency needed for enabling this repo’s setting explicit.
   Disposition: keep READY owns the guide's command row, DOCS runs after it and owns the prose

7. `DOCS` omits the generated Forge skill files from its Scope.
   `src/forge/sync.py` writes the template to both `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`. Done-when 6 cannot deliver updated generated skills with only the template in Scope; add both generated paths.
   Disposition: keep added both generated skill files to DOCS's Scope
