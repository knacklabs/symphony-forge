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
the story or the fix, and the next round doesn't carry it unless it is given again. An empty note
is refused. The turn log records the note's text with the turn.

**The worker can ask and wait.** A worker that needs a decision it can't make ends its turn with a
paragraph that starts `Question:`. `forge work` then prints the question, commits nothing, and
says to answer with `forge work <item> --note "<answer>"`. That next round continues the same Codex
conversation, so the worker keeps its context, and the note carries the answer. A round that ends
with a question never counts as a finished round: `forge close` refuses while the latest round is
an unanswered question, and names it. The brief tells the worker when to ask: when finishing
needs a path outside the item's Scope, or a choice the item doesn't settle.

**Resume survives a leftover process.** When Codex refuses to continue a conversation because
another process still holds it, Forge stops the Codex processes it recorded for that item, the
same way it recovers from a crash, and tries to continue once more. Only when that also fails does
it start a fresh conversation, and it says why.

**A read-only question.** `forge ask "<question>"` runs one read-only Codex turn in the current
checkout with the models in `forge.toml`'s `[models.lite]`, prints the answer, and changes nothing.
If any file changes during the turn, it discards the answer and says so. It needs no story or fix,
and it keeps no record besides its turn log.

**The coordinator uses them.** The Forge skill tells the coordinator: before starting another round
or dismissing a finding for a reason one sentence would fix, give the worker a note; answer a
worker's question with a note; use `forge ask` for a quick read-only look instead of starting a fix.
The guide describes `--note`, questions and `forge ask`.

## Acceptance criteria

- A note appears in that round's brief only, is recorded in the turn log, and an empty note is
  refused.
- A round that ends with a `Question:` paragraph prints the question, commits nothing, and the next
  `forge work --note` continues the same conversation; `forge close` refuses while a question is
  unanswered.
- When Codex refuses to continue a conversation another process holds, Forge stops that item's
  recorded Codex processes, retries once, and continues; it starts fresh only if the retry fails,
  saying why.
- `forge ask` prints an answer from a read-only Codex turn, changes no file, and discards the answer
  if a file changed during the turn.
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
