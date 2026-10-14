---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-14T13:04:47.862764+00:00
seconds: 74.406
read_hash: 59e62479cf6e3b74071cc7fb7e48ba70dba29587
round: 4
passed: yes
doc_seen: 59e62479cf6e3b74071cc7fb7e48ba70dba29587
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 85f77d491de0488a109b662e4e841cfc742d9f7b
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a13a68-5b14-78e1-b8ce-3d9f5bcdd490
session:
blocked_rounds: 0
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

## Round 2

3. Blocking: Claude’s queued-note rule conflicts with the unchanged question boundary.
   Raise: Plan gap. `docs/specs/live-notes.md:87–97` now requires Claude to continue within the same round whenever a note waits, while requiring an answer to a worker’s question to start a new round.
   A coordinator can queue direction before Claude ends its current turn with `Question:`. The queued direction need not answer that question. The doc does not establish which rule wins. `src/forge/worker.py:338–344` currently records the question after the round returns; continuing queued turns first could bypass that boundary or hide an earlier question behind the last response.
   Gain 3, Work 2, Harm 3
    Disposition: cut

4. Blocking: The five-second Codex target contradicts delivery during retry backoff.
   Raise: Not done. `docs/specs/live-notes.md:85–86` now explicitly places a note received during capacity backoff into the next attempt’s input, but line 171 still requires each Codex note to reach the running turn within five seconds.
   `src/forge/codex_turn.py:40` and `318–323` impose waits of 30, 60 and 120 seconds between attempts. A note arriving early in that wait cannot reach the next turn within five seconds. The destination is now defined; the timing requirement remains incompatible with it.
   Gain 3, Work 1, Harm 3
    Disposition: cut

## Round 3

No findings.

## Round 4

No findings.
