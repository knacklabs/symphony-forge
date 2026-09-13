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

**A gate stales when its inputs change, not when the tree moves.** Each recorded
pass carries an input manifest: an ordered list of entries, each a repo-relative
POSIX path and the SHA-256 of that path's bytes at record time. A deleted or
absent input records an explicit null digest, so its later appearance stales the
pass. The recorder validates the manifest: it refuses a pass whose manifest omits
the artifact under the gate, and it recomputes every digest against the tree at
record time, so a manifest cannot claim a state the repository does not have.

The manifest covers three things: the artifact under the gate, every handover
record the pass cites, and the applicable decision set. Applicable means every
decision whose status is accepted at record time, listed by id and digest. That
rule is deterministic and needs no judgement from the recorder. A decision that
becomes accepted after the pass was recorded stales it, because the pass was
ground on a corpus that no longer holds.

**The pre-stage task guard is an explicit exception.** Task grounding hashes the
whole product tree BEFORE its stage starts, which is how work drifting from its
contract is caught before implementation begins. That guard is untouched. The
task gate moves to manifest freshness only after stage start, which is where
every measured case occurred, so "all gates" below means all gates after stage
start.

**One predicate decides freshness, everywhere.** A single manifest-freshness
check is the only thing that answers "is this pass still valid", and every
consumer uses it: the spec, requirements, epics, plan, signoff and task gates,
the board, and the next-step text. Today the requirements gate hashes the
confirmed spec plus the whole product tree, and task grounding folds in the
product tree before stage start; both move onto the predicate.

**Passes recorded before this lands keep the behaviour they were recorded
under.** A pass with no manifest is judged by today's tree-based freshness, and
only passes recorded afterwards get the new rule. Nothing in flight breaks, here
or in a client repo mid-vendor, and the new behaviour arrives as work
re-records. Manifests are never backfilled: inferring what a reader read would be
fabricating evidence.

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

1. Every gate pass recorded after this lands carries an input manifest of
   repo-relative path plus content digest, covering the artifact, the cited
   handover records, and every accepted decision at record time. The recorder
   refuses a manifest omitting the gate's artifact, and refuses one whose digests
   do not match the tree. Asserted for all six gates in the gate table.
2. Editing a product file absent from a pass's manifest leaves that pass valid,
   asserted for all six gates.
3. Editing anything present in the manifest stales the pass, asserted for all
   six gates, including a decision that was read but not cited. A decision newly
   accepted after the pass was recorded also stales it.
3b. One manifest-freshness predicate answers every freshness question, asserted
   by the spec, requirements, epics, plan, signoff and post-stage task gates, the
   board and the next-step text all resolving through it. The PRE-stage task
   grill keeps whole-tree grounding, asserted by a test that an unrelated product
   file still stales it. The requirements gate no longer
   hashes the whole product tree, and its existing regression expecting an
   arbitrary new product file to stale a pass is replaced by one asserting the
   opposite, with the replacement named.
3c. A pass recorded WITHOUT a manifest keeps today's tree-based freshness,
   asserted against a fixture recorded in the old shape. No manifest is ever
   backfilled.
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
