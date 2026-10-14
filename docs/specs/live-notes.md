---
slug: live-notes
title: A coordinator's note reaches a running worker at once
status: confirmed
saved: 2026-10-14T13:03:30.999562+00:00
confirmed_by: "Ravi"
confirmed_hash: 64210bbc2d9841daa7106b4fb989eb710212dffeccf63d169d4253200ea13358
---

# A coordinator's note reaches a running worker at once

## Why

The coordinator cannot reach a worker while its round runs. When the coordinator sees a round go
the wrong way, it must wait for the round to end and then start a new round with the note.

- `forge work <item> --note "<text>"` puts the note into the next round's brief (FORGE-STEER-1,
  `docs/specs/codex-steering.md`). While a round runs, `forge work` refuses with "is already
  running ... wait for it to finish". Forge does not log this refusal.
- A worker's question ends its turn. The answer starts a new round.
- `forge stop <item>` ends the round's process tree. It does not ask the tool to end the turn.
- Forge drives Codex through the Codex app server. The driver (`src/forge/codex_turn.py`) reads
  the turn's pushed notifications through `turn.stream()`, and Forge already sends it lines on
  its stdin while the turn runs. The app server has `turn/steer`, which adds user input to the
  turn in flight and returns the active turn's id, and `turn/interrupt`, which cancels the turn
  in flight so that it ends with the status "interrupted"
  (https://developers.openai.com/codex/app-server.md).
- A headless Claude round (`_run` in `src/forge/worker.py`) runs `claude -p` and writes the brief
  to stdin once. Then stdin closes, so no message can reach the round. The Claude Agent SDK has
  streaming input and an interrupt. Streaming input queues a message into the running session,
  and Claude takes the messages in order, one turn after the other: a message does not change the
  turn that runs (https://code.claude.com/docs/en/agent-sdk/streaming-vs-single-mode). Forge already
  uses streaming input for its Claude cold reads (`src/forge/story.py`), but closes stdin after
  the first message.
- A native round (`src/forge/native.py`) is a subagent of the coordinating Claude Code or Codex
  session. Forge writes the brief, and the session runs the subagent. Forge hears from it only at
  `forge handback`. Forge has no channel to the running subagent. `forge stop` on a native round
  frees Forge's hold and tells the person to stop the subagent in the session.

So the run kinds can take a live note as follows:

| Run kind | Live note | Clean stop |
|---|---|---|
| Codex build, fix and light turns (app server) | Yes, through `turn/steer` | Yes, through `turn/interrupt` |
| Headless Claude rounds | Queued: the worker takes it when its current turn ends, in the same round | Yes, through the SDK's interrupt |
| Native session subagents (Claude Code or Codex) | No: the note waits for the next round | No: as today |

Measured in Forge's own repo, from the local turn logs (307 files) and the events log, read on
14 October 2026:

| What | Value |
|---|---|
| Codex build, fix and light turns, 26 September to 14 October | 905 |
| Turns that carried a note | 301 (33%), all in a new round; 232 continued the conversation, 66 started fresh |
| Notes given while a round ran | 0; Forge refuses them |
| Times the coordinator wanted to steer a running round | unknown; the refusal is not logged |
| Median length of a round that carried a note | 14 minutes |
| Median input tokens of a round that carried a note | about 131,000, mostly cached |
| Time from the end of a turn to the start of the next round with a note | median 9 minutes (quarter under 3, quarter over 52); this includes close and review time |
| Worker questions, 5 to 14 October | 32 |
| Turns that ended as interrupted | 3 of 1,074 |
| Uses of `forge stop` | unknown; Forge records no event for it |
| Notes in native rounds | unknown; native rounds write no turn log |

**Payback.** Build about 3 days.

| Case | Payback |
|---|---|
| The owner waits less for a wrong round to end, about 4 hours a month (guessed) | Don't build: 30 months |
| Also fewer rounds that exist only to carry a note, about 10 hours a month (guessed) | Smallest slice first: 12 months |

The confidence is low because Forge does not log how often the coordinator wanted to steer a
running round.

## Behaviour

The owner chose each of these on 14 October 2026:

1. **A note reaches the running round.** While a Codex or headless Claude round runs,
   `forge work <item> --note "<text>"` sends the note into that round at once. The turn log
   records the note once, with its time and the turn's id. When no round runs, the note goes into
   the next round's brief, as today. When the round ends before the tool takes the note, the note
   goes into the next round's brief, and Forge says so. The note rules do not change: Forge
   refuses an empty note, and a note never widens the item's Scope.
   - **Codex** takes the note inside the running turn, through `turn/steer`. Forge prints that the
     worker received the note in its running turn. When a Codex turn fails at capacity and Forge
     sends it again, the notes the failed attempt received go with the new attempt. A note that
     arrives while Forge waits to send the turn again goes into the new attempt's input.
   - **Claude** queues the note into the running session, through streaming input. The worker
     takes it as soon as its current turn ends, in the same Forge round, with no new brief. Forge
     ends a Claude round only when a turn ends and no note waits, or when that turn ended with a
     worker's question: then the question boundary wins, the round ends, and the waiting note goes
     into the next round with the answer. Forge prints that the note is
     queued and that the worker takes it when its current turn ends.
2. **Stop ends the turn cleanly.** `forge stop <item>` on a Codex or headless Claude round asks the
   tool to interrupt the turn (Codex `turn/interrupt`, the Claude interrupt). The round is recorded
   as interrupted. The worker's commits stay, and its uncommitted changes stay in the worktree.
   When the tool does not end the turn within 30 seconds, Forge ends the processes as today and
   says so. Only a person can run `forge stop`, as today.
3. **A question still ends the turn.** A worker's question ends its turn, and the answer starts a
   new round, as today.
4. **Sandbox rounds work the same.** In a sandbox round, the relay forwards notes and stop over its
   WebSocket to the same driver. That part is built with FORGE-SANDBOX-2. This spec covers rounds on
   the laptop.
5. **No polling.** The running `forge work` listens on a local socket for its item (a named pipe
   on Windows). `forge work --note` and `forge stop` connect to it. The driver passes the note or
   the stop to the tool on the line it already holds, and the tool's reply comes back the same
   way. No step checks a file or a status on a timer.

**Native rounds.** Forge cannot reach a native session subagent. A note given while a native round
runs goes into the next round's brief, and Forge says that the running subagent did not get it.
`forge stop` on a native round works as today.

**What the coordinator and the worker are told.** The Forge skill tells the coordinator to send a
note to a running round when one sentence would fix its direction, instead of waiting for the
round to end. The worker brief tells the worker that a note from the coordinator can arrive during
its turn, and that it must follow the note inside the item's Scope.

**New and existing repos.** A new repo (`forge init`) gets live notes and the clean stop from its
first round. An existing repo gets the same on upgrade and `forge sync`, and so does a repo adopted
on an earlier release. Nothing in `forge.toml` changes. A round that started before the upgrade
has no socket, so a note to it goes into the next round's brief, and Forge says so.

## The experience

- **The coordinator.** It watches a round and sees the worker take a wrong path. It runs
  `forge work <item> --note "Reuse codex.identity(); do not add a new helper."`. On Codex, Forge
  prints that the worker received the note, and the worker changes its path in the same turn. On
  Claude, Forge prints that the note is queued, and the worker takes it when its current turn
  ends. In both cases there is no new round and no new brief.
- **The owner.** The owner wants a round to end. The owner runs `forge stop <item>`. The turn ends
  as interrupted, and the commits stay. The next `forge work` continues from there.
- **A native round.** The coordinator gives a note to a native round. Forge prints that the note
  waits for the next round, because Forge cannot reach a session subagent.

## Out of scope

- Live notes and a clean stop for native session subagents.
- A change to the model or the effort during a round.
- Live notes to cold reads and reviews.
- The sandbox relay's part of this (FORGE-SANDBOX-2).
- Who on a team can send notes (FORGE-SANDBOX-3).
- A change to how a worker's question works.

## Acceptance criteria

1. While a Codex round runs, `forge work <item> --note "<text>"` sends the note through
   `turn/steer` into the running turn, records it once in the turn log with its time and the
   turn's id, and prints that the worker received it; a turn that fails at capacity and is sent
   again carries the notes it received, and a note given while Forge waits to send it again goes
   into the new attempt's input and is recorded once; an empty note is refused.
2. While a headless Claude round runs, the same command queues the note into the session through
   streaming input, records it in the turn log, and prints that it is queued; the worker takes it
   in its next turn in the same round, and the round does not end while a note waits.
3. When no round runs, or the round ends before the tool takes the note, or the round is native,
   the note goes into the next round's brief, and Forge says which case it was.
4. `forge stop <item>` on a Codex or headless Claude round interrupts the turn through the tool,
   records the round as interrupted, and keeps the commits and the uncommitted changes; when the
   tool does not end the turn within 30 seconds, Forge ends the processes and says so; delivery
   and stop use the tool's push interfaces and a local socket, with no polling.
5. The Forge skill tells the coordinator when to send a live note, and the worker brief tells the
   worker that a note can arrive during its turn and stays inside Scope.
6. A new repo gets live notes and the clean stop at init; an existing repo, including one adopted
   on an earlier release, gets them on upgrade and sync; a note to a round that started before the
   upgrade goes into the next round's brief.

## Roadmap

- FORGE-NOTES-1: A coordinator's note reaches a running worker at once

## Success measure

- Metric: in Forge's own repo, the share of notes given while a Codex or headless Claude round runs that reach that round without a new round, and for Codex the time from the note to the running turn receiving it
- Baseline: from 26 September to 14 October 2026, 0 notes reached a running turn; a note waited for the round to end (a median 14 minutes per round) and for a new round to start
- Target: at least 95% of notes given while such a round runs reach that round without a new round; on Codex, each reaches the running turn within 5 seconds, except a note that arrives during a capacity retry wait, which reaches the next attempt when it starts
- Check date: 2026-12-15
