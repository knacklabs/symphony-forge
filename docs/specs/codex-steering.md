---
slug: codex-steering
title: The coordinator can steer and question its Codex workers
status: confirmed
saved: 2026-09-27T14:18:55+00:00
confirmed_by: "vrknetha"
confirmed_hash: 037e00c81f4f4958245553b2db657cb315eeebde8fd1fad355eac5d02b553ca8
---

# The coordinator can steer and question its Codex workers

## Why

Codex workers now build Forge's tasks and fixes, but the coordinator can reach a worker only
through its brief. When a round goes wrong for a reason one sentence would fix ("reuse
`codex.identity()`", "don't add Node to CI"), the only levers are another full round, a
dismissal, or a new fix with a better done-when. A worker that meets a decision it can't make can
only stop, and the whole round is lost. A conversation that a leftover process still holds starts
fresh and loses its context. And there is no quick, read-only question to Codex now that the
plugin is gone.

On 2026-09-26 and 27, most extra review rounds came from exactly these gaps, and every round
re-sends the brief and re-reads the change. Closing them makes the work faster and cuts the tokens
spent on rounds that change nothing.

## Behaviour

**A note for one round.** `forge work <item> --note "<text>"` puts the text into that round's
brief under a "From the coordinator" heading, after the brief's own rules. It changes nothing in
the story or the fix, and Forge doesn't insert it into a later round's brief unless it is given
again (a continued conversation still remembers it). An empty note is refused. The turn log
records the note's text with the turn. A note is guidance inside the item's Scope and never widens
it: work outside Scope still needs the item changed and approved the usual way, or a separate fix.

**The worker can ask and wait.** A worker that needs a decision it can't make ends its final
message with a paragraph that starts `Question:` at the start of a line; everything from there to
the end of the message is the question. The brief tells the worker when to ask: when finishing
needs a path outside the item's Scope, or a choice the item doesn't settle. Forge then:
- prints the question and says to answer with `forge work <item> --note "<answer>"`;
- makes no commit of its own for that round (the usual state commit before a turn stays, and
  whatever the worker already committed stays), and keeps the question in the item's thread record
  under `.git/forge/`, which is never committed;
- refuses `forge work <item>` without `--note` while the question is unanswered, repeating it;
- refuses `forge close` while the question is unanswered, naming it, before close does anything
  else.

A failed or interrupted turn is a failure as today, never a question. The answering round
continues the same Codex conversation whenever the usual resume rules allow; when they start fresh
(the approval, the checkout or the history changed), the new brief carries the question and its
answer, so nothing the worker needs is lost.

**Resume survives a process that is letting go.** Only when Codex refuses to continue a
conversation because it "already has an active writer", Forge waits a few seconds and tries to
continue once more. It never stops a process for this: by then the item's recorded process
identities belong to the new turn, so the holder can't be proven to be the item's own, and Forge
already stops the item's recorded leftovers before each turn. Every other resume error keeps
today's behaviour. When the retry also fails, Forge starts a fresh conversation and says why.

**A read-only question.** `forge ask "<question>"` runs one read-only Codex turn in the current
checkout with the models in `forge.toml`'s `[models.lite]`, prints the answer, and changes no file
in the checkout. It uses the same Codex path as a worker, under its own name `ask`, so its thread
record, lock and logs live under `.git/forge/` like a worker's and are never committed. If any
tracked or untracked (not ignored) file changes during the turn, the same check a cold read uses,
it discards the answer and says so. It needs no story or fix.

**The coordinator uses them.** The Forge skill tells the coordinator: before starting another round
for a reason one sentence would fix, give the worker a note in that round instead; answer a
worker's question with a note; use `forge ask` for a quick read-only look instead of starting a fix.
Dismissing a finding with evidence from the reviewed commit stays as it is. The guide describes
`--note`, questions and `forge ask`.

## Acceptance criteria

- A note appears in that round's brief only, is recorded in the turn log, and an empty note is
  refused.
- A round whose final message ends with a `Question:` paragraph prints the question and adds no
  commit of its own; `forge work` without `--note` and `forge close` both refuse while it is
  unanswered; the answering `forge work --note` continues the same conversation, or on a fresh
  start carries the question and answer in its brief.
- On Codex's "already has an active writer" resume error, Forge waits a few seconds, retries once
  and continues, and never stops a process for it; other resume errors behave as today; it starts
  fresh only if the retry fails, saying why.
- `forge ask` prints an answer from a read-only Codex turn, changes no file in the checkout, keeps
  its records under `.git/forge/`, and discards the answer if a tracked or untracked file changed
  during the turn.
- The Forge skill and the guide describe notes, questions and `forge ask`, and when to use each.

## Success measure

- Metric: close runs per merged item (task or fix), from the close and turn logs.
- Baseline: about 2.5 close runs per merged item on 2026-09-26 and 27 (estimated from the day's
  logs).
- Target: at most 1.8 close runs per merged item.
- Check date: 2026-12-15

## Out of scope

- Steering a turn while it is running.
- Changing the model or effort for one round.
- A structured result format for workers.
- Streaming a worker's progress.

## Roadmap

- FORGE-STEER-1: The coordinator can steer and question its Codex workers
