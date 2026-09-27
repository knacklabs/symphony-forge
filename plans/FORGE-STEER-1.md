# The coordinator can steer and question its Codex workers

## What changes for you

- When a worker's round needs one more sentence to get it right, the agent coordinating the work
  can give it that sentence with the round, instead of running another full round or opening a new
  fix.
- A worker that hits a decision it can't make asks, and waits. It doesn't guess or stop dead. The
  answer goes back into the same Codex conversation, so it keeps everything it already knew.
- A worker whose earlier conversation is still held by a leftover Codex process picks that
  conversation back up, instead of starting over from scratch.
- The coordinator can ask Codex a quick question about the code, answered read-only, without
  starting a fix.

## Why

Codex now builds Forge's tasks and fixes, but the coordinator can reach a worker only through its
brief. On 2026-09-26 and 27 most extra review rounds came from a missing sentence, a worker that
had to stop on a scope question, or a resume that started fresh. Every extra round re-sends the
brief and re-reads the whole change, so these gaps cost time and tokens for nothing. This story
builds the confirmed spec `docs/specs/codex-steering.md`.

## Done when

1. `forge work <item> --note "<text>"` puts the text into that round's brief under "From the
   coordinator", records it in the turn log, and Forge doesn't insert it into a later round unless
   given again; an empty note is refused.
2. A round whose final message ends with a `Question:` paragraph prints the question and adds no
   commit of its own; `forge work` without `--note` and `forge close` both refuse while it is
   unanswered; the answering `forge work --note` continues the same conversation, or on a fresh
   start carries the question and answer in its brief.
3. On Codex's "already has an active writer" resume error, Forge stops that item's matching recorded
   Codex processes, restarts its driver, retries once and continues; other resume errors behave as
   today; it starts fresh only if the retry fails, saying why.
4. `forge ask "<question>"` prints an answer from a read-only Codex turn, changes no file in the
   checkout, keeps its records under `.git/forge/`, and discards the answer if a tracked or
   untracked file changed during the turn.
5. The Forge skill and the guide describe notes, questions and `forge ask`, and when to use each.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| RESUME | Resume past a leftover writer | In the driver, on the exact "already has an active writer" resume error: stop the item's matching recorded Codex processes with Forge's existing stop code, restart the app-server, retry once; every other resume error unchanged | 3 | `src/forge/codex_turn.py` | `tests/test_steer_resume.py` | — | no |
| STEER | Notes, questions and ask | `forge work --note` and its "From the coordinator" brief section and turn-log `note`; the `Question:` contract with the thread-record `question`, the refusals and the answer round; `forge ask` under its own `ask` records; the `--note` flag and the `ask` command row | 1, 2, 4 | `src/forge/cli.py`, `src/forge/worker.py`, `src/forge/close.py`, `src/forge/codex.py`, `src/forge/ask.py`, `src/forge/templates/brief.md` | `tests/test_steer_note.py`, `tests/test_steer_question.py`, `tests/test_steer_ask.py` | — | yes |
| DOCS | Tell the coordinator | The Forge skill's rules for notes, questions and `forge ask`, and the guide's section on them | 5 | `src/forge/templates/skill.md`, `docs/guide.md` | `tests/test_steer_docs.py` | STEER | yes |

New moving parts: none

## Risks

- RESUME stops Codex processes that still hold a conversation, which could cut off work in
  progress. It stops one only while this `forge work` holds the item's one-worker lock (so no
  other `forge work` for the item can be running a turn), only when it was recorded for this item,
  and only when its start time and command still match; anything else keeps today's behaviour.

## Notes

- RESUME and STEER start together: RESUME changes only `src/forge/codex_turn.py` and calls the
  stop code that already exists in `src/forge/codex.py`; STEER owns every change to `codex.py`,
  `cli.py`, `worker.py` and `close.py`. DOCS goes last so every command it names exists.
- STEER pins the names: the `--note` flag, the brief heading "From the coordinator", the turn-log
  field `note`, the thread-record field `question`, and `threads/ask/` for `forge ask`'s records
  (a kind of its own, never `threads/fix/`).
- The answering round's brief always carries the question and its answer, whether the conversation
  continues or starts fresh, so no fresh-start signal is needed.
- A question clears only after the answering turn completes. If the answering turn fails or is
  interrupted, the question stays unanswered, and `forge work` without `--note` and `forge close`
  keep refusing.
- RESUME's trigger is the error text Codex returns ("already has an active writer"); it never stops
  an unrecorded process or one whose start time and command no longer match.
- `forge ask` reuses `codex.run` with a read-only sandbox, like the cold reader, and the cold read's
  tracked-and-untracked snapshot to detect changes.
- Each test file starts with `STORY = "FORGE-STEER-1"`, and its `test_<n>_` names cite the Done-when
  items its task covers.
