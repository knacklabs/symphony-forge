---
reader: codex (gpt-6-sol)
read_at: 2026-09-27T04:55:02+00:00
read_hash: 5e2a50cb78d58c10ff81773cc12d9e4f379c0caa
amended_hash: d853ba8bcb53f5c3865f3f7aeedbdac691e32e8a
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. ASK cannot keep its records separate within its stated Scope.
   `codex.run` uses `[models.lite]` for a Lite turn, but `codex._item_file` puts a Lite turn named `ask` under `threads/fix/ask`. ASK must also own the `codex.py` record-path change. That makes its claimed file independence from RESUME false; pin the shared path rule before either task uses it.
   Disposition: keep STEER now owns every codex.py change, including forge ask's own threads/ask/ record path; RESUME no longer touches codex.py.

2. The fresh-start question path is not specified at the point it must run.
   `worker.work` builds the brief before `codex.run`; `codex_turn.py` can then fail to resume and start a fresh conversation. That brief cannot yet contain the promised question and answer. RESUME must pin how the driver reports this fallback, and QUESTION must use that signal to put both into the fresh turn.
   Disposition: keep The answering round's brief now always carries the question and its answer, continued or fresh, so no fresh-start signal is needed.

3. The unanswered-question gate has no clearing rule.
   The doc pins the `question` field but does not say whether `forge work --note` clears it on invocation or only after a completed answering turn. Pin the latter outcome and the behavior after a failed or interrupted answer; otherwise `forge close` could proceed while the question remains unanswered.
   Disposition: keep Pinned in Notes: a question clears only after the answering turn completes; a failed or interrupted answer keeps it unanswered and the refusals stay.

4. NOTE’s After links do not describe code it needs.
   Its `--note` entry and ASK’s command-table row are separate lines in `cli.py`; its turn-log field and RESUME’s retry logic are separate work in `codex.py`. Assign each shared file’s lines to one task and remove the After links that exist only for file overlap, retaining dependencies only for a pinned interface another task consumes.
   Disposition: keep Tasks re-split so each owns its files: RESUME (codex_turn.py only) and STEER (all cli.py, codex.py, worker.py, close.py lines) start together; only DOCS waits, for STEER's commands.

5. `Risks: none` omits the writer termination risk.
   RESUME deliberately stops recorded Codex processes that may still be executing a turn. That can lose work in progress. Name the risk and pin the safe-stop and recovery behavior without weakening the process identity checks.
   Disposition: keep Risks now names it: RESUME stops a process only while holding the item's one-worker lock, only a recorded one, and only when its start time and command still match.
