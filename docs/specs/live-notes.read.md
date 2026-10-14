---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-14T12:40:21.346049+00:00
seconds: 342.057
read_hash: 47dfcd1ef3ef86508b5a3f40233d996fd43a5c49
round: 1
passed: no
doc_seen: 47dfcd1ef3ef86508b5a3f40233d996fd43a5c49
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a13a68-5b14-78e1-b8ce-3d9f5bcdd490
session:
blocked_rounds: 1
loop_choice:
loop_reason:
---
# Cold read notes

Written by `forge read`. Under every blocking finding, write one disposition line, amend the
doc, then run `forge read <doc>` again until a round has no blocking notes. Notes marked
`Advisory:` are recorded without requiring a disposition or another round:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

A finding inside What counts is cut or deferred. Keep one only when it falls outside that boundary
or is factually wrong, and give as the reason the Leave out line, the missing Raise line, the
cited fact that disproves it, or the human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: Streaming input does not establish the promised same-turn Claude steering.
   Raise: Plan gap. [docs/specs/live-notes.md:75](/docs/specs/live-notes.md:75) promises delivery into the running turn. Anthropic documents streaming input as messages processed sequentially across turns, with interruption handled separately. [Streaming input reference](https://code.claude.com/docs/en/agent-sdk/streaming-vs-single-mode#benefits).
   The existing streaming example at `src/forge/story.py:972–976` sends one user message; `src/forge/worker.py:641–652` likewise handles one prompt and its result. Neither establishes that a follow-up changes an unfinished Claude turn. A queued follow-up would leave acceptance criterion 2 and the five-second target unmet during a long round.
   Gain 5, Work 3, Harm 3
    Disposition: cut

2. Blocking: Notes sent during Codex capacity backoff have no defined destination.
   Raise: Plan gap. [docs/specs/live-notes.md:82](/docs/specs/live-notes.md:82) preserves notes the failed attempt already received, but does not cover a new note arriving before its retry starts.
   At `src/forge/codex_turn.py:318–323`, Forge keeps the round running while waiting 30, 60 or 120 seconds between attempts. No turn is active then, and [`turn/steer` rejects that state](https://developers.openai.com/codex/app-server#steer-an-active-turn). The fallback names a round that ended; this round has not ended. Whether the note reaches the imminent retry or waits for another `forge work` is unpinned.
   Gain 3, Work 2, Harm 3
    Disposition: cut
