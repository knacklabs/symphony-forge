---
reader: codex (gpt-6-sol)
read_at: 2026-09-27T16:58:03+00:00
read_hash: 6b879e01252d7c408d4df05cfb1baa4101eff6f5
amended_hash: 2ff3d9285ade891fa5bb2e2fc7dfa20eb28abc3d
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. The target of one project cannot be reached by the stated behavior.
   The spec changes chats only when a worker starts or resumes. Existing chats in the dozens of worktree projects remain there, and cold reads are named but never assigned to the repo project. Either include those chats in the assignment rule or measure only new worker chats. [Spec](/docs/specs/codex-chat-view.md:21).
   Disposition: keep cold reads are assigned too, and the measure counts only chats started after this ships

2. The pinned SDK route needs an exact contract.
   Forge pins `openai-codex` 0.156.1. Its public client has no project or attachment helpers, and its generated metadata update model has no `projectId` field. Pin the wire requests, response fields, and failure handling to use through `CodexClient.request`, or name a supported upgrade. The [app-server protocol](https://github.com/openai/codex/blob/main/codex-rs/app-server-protocol/src/protocol/common.rs) marks `project/list` experimental. [Current driver](/src/forge/codex_turn.py:104).
   Disposition: keep pinned project/list, thread/metadata/update and thread/attachment/add through the SDK's raw request, with failure handling

3. “The repo’s main checkout” does not identify a project unambiguously.
   `repo.root()` returns the current worktree, so the spec must say how Forge finds the main checkout and compares it with a project’s roots, including multiple matching projects. Without that rule, workers can choose different projects for the same repo. [Repo root](/src/forge/repo.py:80).
   Disposition: keep the main checkout is the resolved parent of the git common dir; exactly one project root match, else none

4. The no-project acceptance criterion contradicts the naming and preview requirements.
   “Nothing is changed” when no project matches conflicts with renaming the chat and adding a preview line. Say that only the *project assignment* is left unchanged. [Spec](/docs/specs/codex-chat-view.md:42).
   Disposition: keep only the project assignment is left unchanged without a match

5. Cut or defer: pull request attachments.
   The Why describes project sprawl, long names, and unreadable previews; the success measure counts projects. Neither establishes a need for attachments. If retained, pin the attachment identity and URL for newly opened and already existing PRs, absent Codex chats, and retries after failure. The [app-server attachment contract](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md) makes repeated additions idempotent by identity key; `forge close` currently returns early for merged PRs and does not request an existing PR’s URL. [Close flow](/src/forge/close.py:43).
   Disposition: keep the owner chose attachments; the Why now names the chat-to-PR gap and the identity, payload and repeat rules are pinned

6. Task names on resumed rounds are unresolved.
   `forge work` changes a later task round’s kind to `Fix` and currently passes that kind into the thread name. The spec requires the task’s name throughout its chat, but does not say whether a resumed round renames it or keeps its original name. It also leaves “first words” and truncation at 60 characters undefined for long fix names. [Worker naming](/src/forge/worker.py:61).
   Disposition: keep names are set once at start and kept on later rounds; the 60-character cut is pinned

7. “Every brief” leaves the preview scope open.
   The shared worker brief also goes to Claude, while cold reads use a separate prompt. Pin which prompts gain the line and what that line says for a first build, a resumed fix round, and a cold read. That keeps the preview requirement testable without silently changing other workers’ briefs. [Worker brief](/src/forge/worker.py:212), [cold read](/src/forge/story.py:139).
   Disposition: keep every worker brief and cold-read prompt gets the pinned first line
