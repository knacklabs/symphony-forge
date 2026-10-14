---
slug: item-cost
title: Each story, task and fix shows what it cost in tokens and time
status: confirmed
saved: 2026-10-14T10:44:00.399204+00:00
confirmed_by: "Ravi"
confirmed_hash: 8285427576ade5926bc5167e342f99228fb96f607195c9d800cc1f56772b594d
---

# Each story, task and fix shows what it cost in tokens and time

## Why

An engineering manager cannot see what a story, task or fix cost. Forge keeps some token counts,
but it loses many of them, and the board shows none.

- A Codex build turn keeps only the last usage report of the turn (`tokenUsage.last`). When Codex
  is at capacity and Forge sends the turn again, the run record keeps only the last attempt. A commit
  nudge turn is a second run whose count is not added to the round. Reasoning tokens reach the run
  record but not the per-turn list.
- A review keeps its counts in its own side file. A headless Claude run adds cache writes to its
  input count, so cache writes cannot be told apart.
- A native Claude round (a subagent of the coordinator's session) records no usage at its hand back.
- When a pull request's time record gets too large, Forge folds old rounds into a summary. The
  summary keeps time, not tokens, so the folded rounds' counts are lost.
- The board shows no tokens and no cost.

Measured in Forge's own repo, from the local logs and the turn logs, for 11 to 14 October 2026:

Each row states its unit. Rows with different units are not added together.

| What | Unit | Total | With token counts | Without |
|---|---|---|---|---|
| Codex build and fix turns (turn log) | attempts | 58 | 50 | 8: 7 started and never ended, 1 interrupted |
| Codex capacity retries | attempts | 0 | none | none; the only 2 in all saved logs were on 4 and 5 October |
| Codex review | attempts (one per review run) | 412 | 218 | 194: 178 on 11 and 12 October, before reviews kept counts, and 16 failed reviews |
| Codex cold read (turn log) | attempts | 48 | 48 | 0; the run record has counts for only 32, as it kept none on 11 and 12 October |
| Codex build round (`forge work` run record) | rounds | 53 | 7 | 46, all on 11 October, before the run record kept counts |
| Headless Claude run | attempts | 0 | none ran | none ran |
| Native Claude build | items | at least 67 | 0 | 67 of the 96 items that reached review have no attempt record at all |
| Codex helper agent threads | attempts | unknown | unknown | Forge does not record a helper thread apart from its parent turn |

Coverage per unit:

- Codex build and fix turn attempts: 50 of 58 have counts (86%).
- Review attempts: 218 of 412 have counts (53%).
- Cold-read attempts: 48 of 48 have counts in the turn log (100%), 32 of 48 in the run record (67%).
- Native Claude builds: at least 67 items have no attempt record, so their attempts cannot be counted.

Of the last 100 merged pull requests (10 to 14 October), 57 carry a time record. 56 of those keep
some token rows. 3 records are compacted, and none of the 3 summaries keeps a token total. 43 pull
requests have no time record.

**Payback.** Build about 5 days.

| Case | Payback |
|---|---|
| The owner stops putting cost together by hand, about 4 hours a month (estimated) | Don't build: 20 months |
| The owner also picks models and effort per kind of work from measured cost, about 8 hours a month (estimated) | Smallest slice first: 10 months |

## Behaviour

The owner chose each of these on 14 October 2026:

1. **Every run attempt gets a token receipt.** This includes Codex build turns, with each capacity
   retry and each commit nudge, Codex helper agents' threads, Codex and Claude reviews and cold
   reads, and headless Claude runs. Each receipt keeps the model, the activity (build, read or
   review), uncached input, cached input (cache read), cache write, output and reasoning tokens where
   the tool reports them, with cache writes split by cache duration where the tool reports it
   (Claude's 5-minute and 1-hour writes), the billing basis (plan login or API key), the item and the person who
   started the run. Each count is a delta for that attempt. Forge never adds a cumulative total or a
   total that includes the parent twice.
2. **Native agents report their own counts.** A native Claude agent reports through Claude Code's
   agent-stop hook. A native Codex run in a Codex-only repo reports through the Codex app server's
   thread usage. When Forge cannot read a count, the item shows "unknown" for that run. Forge never
   guesses a count and never uses the parent session's total.
3. **Receipts survive a new laptop.** The pull request's time record keeps token totals per model,
   activity and billing basis (plan login or API key), plus the number of runs and the number of
   runs with unknown counts. Compaction keeps these totals when it folds old rounds, so a fresh clone
   still shows the estimated cost and the unknown share.
4. **Cost.** Forge ships a price table per model: the price per million tokens for input, cached
   input, 5-minute cache write, 1-hour cache write and output, with the date of the rates. A run on
   an API key shows an estimated cost. When the tool does not report the cache duration, Forge uses
   the 5-minute rate and marks the cost as an estimate. A run on a plan login shows its tokens and
   "on plan".
5. **The board shows cost and time per item.** The local board and `forge board --json` show, for
   each story, task and fix: elapsed time, waiting time, automation time (never called effort),
   rounds, tokens by model and activity, estimated cost, and the share of runs with unknown counts.
   A story's token counts and run durations are the sum of its parts' receipts plus the receipts
   recorded under the story's own key (its cold reads). A story's elapsed and waiting time are the
   union of its parts' intervals, so parts that overlap count once, as Forge's time records do
   today. Forge does not count the coordinator's session (for example, story planning), because it
   cannot assign that session's use to one item.
6. **No Mainline needed.** All of this works on the laptop and in the pull request. The export to
   Mainline, with an allowlisted list of fields, is a separate story.

**Plan limits (FORGE-COST-2).** A developer on a plan login can hit the 5-hour or weekly limit in
the middle of a round with no warning, and the round stops. Where the tool reports plan limits (the
Codex app server's rate-limit reports, and Claude Code where it gives them), the board shows how
close each developer is to the plan's 5-hour and weekly limits.

**New and existing repos.** A new repo (`forge init`) gets receipts, the price table and the board
columns from its first run. An existing repo gets the same on upgrade and `forge sync`, and so does
a repo adopted on an earlier release. Runs and pull requests from before the upgrade show "unknown"
for counts Forge never recorded. Forge does not guess or backfill them. Counts that old records do
hold, such as review and turn counts, still show.

## The experience

Two people live with this: a developer who runs Forge through Claude Code or Codex, and the
engineering manager who answers for the team's model spend.

- **The manager.** She opens the board and sees each story's elapsed time, waiting time, automation
  time, rounds, tokens by model and activity, and estimated cost. A story row adds its tasks'
  tokens once, and parts that run at the same time count once in its elapsed time.
  When some runs have no counts, the row says what share is unknown, so she knows how far to trust
  the total.
- **The developer.** Nothing new to do. Each run writes its receipt by itself. After FORGE-COST-2,
  the board also shows how close he is to his plan's 5-hour and weekly limits, where his tool
  reports them.
- **After a laptop change.** A fresh clone shows the same totals for merged items, because the pull
  request's time record holds them.
- **Plan logins.** A run on a ChatGPT or Claude plan shows its tokens and "on plan", not a price.

## Out of scope

- The export of cost and time to Mainline.
- Stopping or slowing work when a budget or a plan limit runs out.
- Backfilling or estimating counts that Forge never recorded.
- The cost of CI minutes and sandbox credits.

## Acceptance criteria

1. Every run attempt (a Codex build turn, each capacity retry, each commit nudge, a helper agent's
   thread, a review, a cold read, a headless Claude run and a native agent) writes one receipt with
   the model, activity, uncached input, cached input, cache write by duration where reported, output
   and reasoning tokens where reported, billing basis, item and starter; native Claude counts arrive
   through the agent-stop hook and native Codex counts through the app server's thread usage; a run
   whose count cannot be read shows "unknown", never a guess or the parent session's total; the
   item's total equals the sum of its receipts, with no count added twice.
2. A pull request's time record keeps token totals per model, activity and billing basis, the number
   of runs and the number with unknown counts, also after compaction; a fresh clone shows the same
   totals, estimated cost and unknown share for a merged item.
3. With the shipped price table, an API-key run shows an estimated cost, priced by cache duration
   where reported and at the 5-minute rate, marked as an estimate, where not; a plan-login run shows
   its tokens and "on plan".
4. The local board and `forge board --json` show, per story, task and fix, elapsed time, waiting
   time, automation time, rounds, tokens by model and activity, estimated cost and the share of runs
   with unknown counts; a story's tokens and run durations are its parts' receipts plus its own cold
   reads, and its elapsed and waiting time count overlapping parts once; the coordinator's session is
   not counted.
5. A new repo gets all of this at init; an existing repo, including one adopted on an earlier
   release, gets it on upgrade and sync, and its older items show "unknown" for counts never
   recorded.
6. (FORGE-COST-2) Where the tool reports plan limits, the board shows each developer's use of the
   5-hour and weekly limits.

## Roadmap

- FORGE-COST-1: Every run keeps its token count, and the board shows cost and time per item
- FORGE-COST-2: The board shows how close each developer is to their plan limits

## Success measure

- Metric: in Forge's own repo, the share of attempts of each kind (Codex build and fix turns, reviews, cold reads, native builds) that have token counts, and the share of compacted pull request records that keep token totals
- Baseline: from 11 to 14 October 2026, Codex build and fix turn attempts 50 of 58 (86%), review attempts 218 of 412 (53%), cold-read attempts 48 of 48 in the turn log (32 of 48 in the run record), native Claude builds at least 67 items with no attempt record, and 0 of 3 compacted records
- Target: from the release on, at least 95% of attempts of each kind have counts, every native build has attempt records, and every compacted record keeps its totals
- Check date: 2026-12-15
