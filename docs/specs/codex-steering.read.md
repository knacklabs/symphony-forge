---
reader: codex (gpt-6-sol)
read_at: 2026-09-27T04:40:22+00:00
read_hash: 3b74a7b2976b3efd09e3440a91934bd40386112a
amended_hash:
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. A note cannot authorize work outside an item's Scope.
   The spec tells a worker to ask when it needs an out-of-scope path, then resume with an answer in `--note`. The current brief still limits edits to Scope (`src/forge/templates/brief.md`). Pin whether that answer is guidance within Scope or requires a changed, approved task before work continues.
   Disposition: keep A note is now pinned as guidance inside Scope that never widens it; out-of-scope work still needs the item changed and approved, or a separate fix.

2. “Commits nothing” conflicts with the current work path.
   `worker.work` commits the item's `working` or `fixing` state before the turn (`src/forge/worker.py:71-75`), and the brief tells workers to commit their work. Define what happens if a worker has already edited or committed before ending with `Question:`, and where the unanswered question is recorded without a commit.
   Disposition: keep The question round now adds no commit of its own (the usual pre-turn state commit and the worker's own commits stay), and the question lives in the item's thread record under .git/forge/, never committed.

3. The question result needs an exact contract.
   Pin how Forge recognizes a final `Question:` paragraph, what happens with multiple questions or a failed turn, and what an unanswered `forge work` call does without `--note`. Place the `forge close` refusal before its merge, review and publish effects (`src/forge/close.py:39-84`).
   Disposition: keep The contract is pinned: a final-message paragraph starting 'Question:' at a line start through the end; failed turns stay failures; forge work without --note and forge close both refuse while unanswered, close before anything else.

4. A note persists in conversation history.
   A later round may omit the note from its new brief, but a resumed Codex conversation still contains the earlier turn. Narrow “the next round doesn't carry it” to “Forge does not insert it again”; otherwise the promised behaviour cannot be built.
   Disposition: keep Narrowed to 'Forge doesn't insert it into a later round's brief'; a continued conversation still remembers it.

5. Answering in the same conversation is not guaranteed by the existing resume rules.
   `codex.conversation` starts fresh after an approval change, checkout change or rewritten history, and `codex_turn.py` starts fresh when resume fails. Pin whether an unanswered question makes these cases refuse until resolved, or whether losing context is acceptable.
   Disposition: keep The answering round continues the conversation when the usual resume rules allow; when they start fresh, the new brief carries the question and its answer.

6. The leftover-process retry needs a safe trigger and owner.
   `codex.hold` already stops recorded leftovers before a turn, while `codex_turn.py` currently treats any resume RPC error as a reason to start fresh. Specify the particular “held by another process” error, which recorded process can be stopped without interrupting an active turn, and whether retry restarts the driver. Do not apply the recovery to every resume error.
   Disposition: keep The retry now fires only on the exact 'already has an active writer' error, stops only that item's recorded processes whose start time and command still match, restarts the driver and retries once; other resume errors behave as today.

7. `forge ask` has conflicting record and file-change requirements.
   The existing Codex path writes a thread record, lock and work log as well as a turn log (`src/forge/codex.py:205-355`); the spec permits only a turn log. Pin its log identity and whether those operational records are allowed. Also pin what “any file changes” covers: the current cold-read snapshot includes tracked and untracked files but omits ignored files (`src/forge/story.py:451-462`).
   Disposition: keep forge ask now uses the worker's Codex path under the name 'ask', so its thread record, lock and logs live under .git/forge/ (never committed), and its file check is the cold read's tracked-and-untracked snapshot.

8. Cut or defer: requiring a note before dismissing a finding that one sentence would fix.
   The existing dismissal path requires evidence from the reviewed commit (`src/forge/close.py:61-68`). When that evidence proves a finding wrong, another worker round adds no needed behaviour and works against the stated close-run target. Require notes when starting a worker round; retain direct evidence-backed dismissal.
   Disposition: cut The coordinator rule now asks for a note only instead of starting another round; evidence-backed dismissals stay as they are.
