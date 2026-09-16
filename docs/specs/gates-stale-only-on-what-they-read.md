---
slug: gates-stale-only-on-what-they-read
title: Gates stale only on what they read
status: confirmed
saved: 2026-09-11T17:49:55+00:00
---

# Gates stale only on what they read

## Why

Shipping one 17-file client task through this harness took eight re-runs of
gates that had already passed. None was caused by the work changing: each was a
gate invalidated by an edit it never read.

The measured cases, all from GRANTED-1-T1 on 2026-09-11:

- A clean three-lens review stamped the stage. Closing the stage then failed on
  a verify command, and fixing that command in the contract invalidated the
  stamp. An unchanged tree was reviewed again to re-earn it. Decision 0066
  already says a stamp binds `delta_id` alone and that a contract re-record
  never affects it, so this is the implementation not keeping an accepted
  promise.
- Reverting two files so the diff was smaller and cleaner killed the stamp
  again, for the same reason.
- Amending a decision after a spec read re-staled that read; cutting a task
  worktree from trunk re-staled the task grill. In both cases the artifact and
  the records it cited were untouched.

The second cost is the recorder's round floor. Every recorded pass requires a
fresh AskUserQuestion round, so a pass with a genuinely empty frontier cannot be
recorded without inventing a question. Of roughly fifteen questions put to the
owner across that task, several existed only to satisfy the recorder.

The third is the grill budget. A read that died on an upstream tool failure
still consumed an allowance, and recording an escalation printed that grilling
continues while the next read was still refused, including a print-only dry run.
An owner instruction to retry was therefore unexecutable.

Two things this spec does NOT carry, both corrected by the spec cold read.
`forge task close` is a valid command and the intended closeout path; the client
repo was running an older vendored copy, which is a vendoring lag, not a defect
here. And scope widening already has a sanctioned non-cascading path in
`stage amend-scope`, which records measured paths without touching the contract.

## Behaviour

**A gate stales when its inputs change, not when the tree moves.** The general
form of this is an input manifest — a path-plus-digest list on every pass, with
one freshness predicate reading it — and that design is deferred as D-0035 with a
revisit trigger. Reading the machinery showed the cost this story was written to
remove had a far smaller cause, and the manifest is not needed to remove it.

**One list never joined the one definition.** `product_excluded_prefixes` is
documented as "The ONE definition of 'not product'" and exists because four lists
disagreed — its own example being that a decision record "was not a scope stray
but did stale the review stamp". It excludes `.factory/`, `plans/`,
`docs/decisions/` and `docs/context/ledger.json`. `requirements_digest` never
asked it: it takes the bare default of `.factory/` and `plans/` only. So a
decision record is product to the requirements gate and to nothing else, and
accepting a decision stales it alone.

That is the cascade this story removes. It fired on nearly every step of T1 and
T2, including the circular case where recording a decision invalidated the gate
that had already read the spec that decision came from.

**A newly accepted decision no longer stales the requirements gate.** An earlier
ruling here said the opposite: every accepted decision belongs in the manifest
because authors do not reliably know what they relied on. The owner reversed that
on 2026-09-13 for this gate, on the evidence above. The other gates are unchanged,
and the reversal is recorded in the plan's owner rulings.

**The pre-stage task guard is an explicit exception.** Task grounding hashes the
whole product tree BEFORE its stage starts, which is how work drifting from its
contract is caught before implementation begins. That guard is untouched. The
task gate keeps whole-tree grounding before stage start by owner ruling, and
already drops the product tree once the stage opens.

**One helper decides requirements freshness.** Two consumers compare a stored
digest against a fresh recomputation today — the plan-save gate and the
next-step text — and both move behind one helper. Two places answering one
freshness question independently is the same shape as the defect above, and
leaving one inline would replant it.

A single predicate across ALL gates, the board and the next-step text is the
deferred manifest design (D-0035), not this story.

**Passes recorded before this lands keep the behaviour they were recorded
under.** Changing an exclusion changes the digest, so a stored value would stop
matching a recomputation and every existing pass would read as stale at once —
the very cascade this story removes, delivered to everyone in one go. The helper
therefore accepts the legacy digest as well, exactly as `grounding_matches`
already does for task grounding: the legacy digest covers a superset of the
inputs, so anything it accepts the new rule accepts too. Nothing in flight
breaks, here or in a client repo mid-vendor. Freshness evidence is never
backfilled: inferring what a reader read would be fabricating evidence.

**A review stamp binds the diff, as decision 0066 already requires.** A contract
edit that leaves the reviewed delta unchanged never invalidates a stamp. This is
restoring stated behaviour, not changing it.

**A recorded pass needs a real question only when there is one.** The round floor
is per gate, not per recording attempt. Re-recording the SAME gate for the SAME
story may reuse the rounds that gate already carries; a round is never reused
across gates, stories or tasks. This narrows decision 0051's "no round reused
across grills", whose intent — that every gate is genuinely ledger-matched —
survives intact, because the only case relaxed is re-recording a gate whose
question was already asked and answered.

**The grill budget counts reads, not failures.** A read that failed consumes no
allowance. The ledger already records this: the repeat-read guard ignores a
launch whose terminal row is `failed`, while the cap counts every launch
regardless. Two guards reading the same ledger disagree about what a read is, and
the cap's answer is the wrong one — a crashed launcher spends an allowance that
exists to stop a reader circling, when nothing circled.

A third state for a read that exits zero having produced nothing was specified
here and is deferred, not dropped: the upstream compaction fault that produced it
is fixed in codex 0.154.0, and detecting it means decoding the companion's JSON
payload, so it will be built when a run is actually observed doing it. Recording an escalation grants exactly one further read
for that gate and task, and that grant is spent when the next read completes,
clearing both the cap and the repeat-read guard, so the printed promise matches
the behaviour.

## Acceptance criteria

1. `requirements_digest` excludes exactly what `product_excluded_prefixes`
   excludes, rather than the bare default it takes today. The exclusion SET is
   asserted, not one example path, so the next list to drift is caught.
2. Accepting a decision record no longer stales a recorded requirements pass, and
   neither does a change to `docs/context/ledger.json`. Asserted both ways.
3. Editing the confirmed spec body still stales it, and so does changing a real
   product file. The gate is corrected, not disabled.
3b. No other gate's freshness moves. The spec, signoff, epics and plan gates keep
   their prefix-based rule, and the PRE-stage task grill keeps whole-tree
   grounding by owner ruling — asserted by a test that an unrelated product file
   still stales it.
3c. A requirements pass recorded BEFORE this lands keeps its settled meaning:
   changing the digest's exclusions must not reinterpret stored records into
   staleness all at once. Asserted against a fixture recorded in the old shape.
   (The general input-manifest design is deferred as D-0035.)
4. A stage review stamp survives a contract re-record that leaves the delta
   unchanged, asserted end to end through a stamp, a contract edit and a stage
   close, per decision 0066.
5. Re-recording the same gate for the same story reuses that gate's existing
   rounds and needs no new question; a round is refused when reused across a
   different gate, story or task; and the floor of one real round per gate still
   holds. All four asserted.
6. A launch whose terminal row is `failed` spends no allowance, and the cap and
   the repeat-read guard agree on that. Asserted both ways: a failed launch
   leaves the budget unchanged, and a successful one still spends it.
7. Recording an escalation permits exactly one further read for that gate and
   task, clearing both the cap and the repeat-read guard, and that grant is spent
   once the read completes. Asserted from an exhausted budget.
8. A named set of generated `./forge` invocations printed in next-step text
   parses against the real command grammar, arguments included. External programs
   and placeholders are out of scope.
9. Existing suites pass. The 93 failures already red on main are unchanged in
   count and identity, so this change is neither credited nor blamed for them.
