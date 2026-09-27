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
| RESUME | Resume past a leftover writer | On the exact "already has an active writer" resume error: stop the item's matching recorded Codex processes, restart the driver, retry once; every other resume error unchanged | 3 | `src/forge/codex_turn.py`, `src/forge/codex.py` | `tests/test_steer_resume.py` | — | no |
| ASK | Read-only question | `forge ask "<question>"`: one read-only Codex turn under the name `ask` with `[models.lite]`, answer printed, discarded if files changed; its row in the command table | 4 | `src/forge/ask.py`, `src/forge/cli.py` | `tests/test_steer_ask.py` | — | yes |
| NOTE | A note for one round | `forge work --note`: the "From the coordinator" section in that round's brief, the note in the turn log, empty note refused | 1 | `src/forge/cli.py`, `src/forge/worker.py`, `src/forge/codex.py`, `src/forge/templates/brief.md` | `tests/test_steer_note.py` | RESUME, ASK | yes |
| QUESTION | Ask and wait | The `Question:` contract: printed, kept in the thread record, `forge work` without a note and `forge close` refuse while unanswered, the answer continues the conversation or rides a fresh start's brief; the brief says when to ask | 2 | `src/forge/worker.py`, `src/forge/close.py`, `src/forge/codex.py`, `src/forge/templates/brief.md` | `tests/test_steer_question.py` | NOTE | yes |
| DOCS | Tell the coordinator | The Forge skill's rules for notes, questions and `forge ask`, and the guide's section on them | 5 | `src/forge/templates/skill.md`, `docs/guide.md` | `tests/test_steer_docs.py` | NOTE, QUESTION, ASK | yes |

New moving parts: none

## Risks

Risks: none

## Notes

- RESUME and ASK start together; they share no file. NOTE waits for both because it also changes
  `src/forge/codex.py` (the turn log's note field) and `src/forge/cli.py` (the `--note` flag).
  QUESTION builds on NOTE's flag and brief section. DOCS goes last so every command it names
  exists.
- NOTE pins the shared names: the `--note` flag, the brief heading "From the coordinator", and the
  turn-log field `note`. QUESTION pins the thread-record field `question` and the refusal wording.
- RESUME's trigger is the error text Codex returns ("already has an active writer"); it never stops
  an unrecorded process or one whose start time and command no longer match.
- `forge ask` reuses `codex.run` with a read-only sandbox, like the cold reader, and the cold read's
  tracked-and-untracked snapshot to detect changes.
- Each test file starts with `STORY = "FORGE-STEER-1"`, and its `test_<n>_` names cite the Done-when
  items its task covers.
