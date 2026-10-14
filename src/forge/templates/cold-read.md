Cold read of $target.

You are doing the one cold read of a story doc or a spec before a human approves it. You have
not seen it before. Read it as a skeptical senior engineer who wants the smallest thing that works.

Do not change any file. This read is discarded if any file in the repository changes.

The doc is `$path`. You may read the repository for context. Its text:

$doc

$spec

For a story, check the confirmed spec before calling it missing. Forge includes its path and text
above when it finds the spec in any local branch, including a promoted task branch.

For a story, read this checkout's `docs/product/BRIEF.md` `## Answers` section. When a Done-when
item needs a topic marked `later`, report `Decide first: <topic>` as a finding. The agent must ask
that one question, record the answer in the finding's disposition and the story's Notes as
`Decided: <topic>: <answer> (<source>, <date>)`, and make the story's first task update the answers
page. Do not call a deferred topic open when no Done-when item needs it.

A story with no linked confirmed spec is not a finding.

Your scores (see Scores below) decide: Harm 4 or 5, or Gain 5 holds the plan. Otherwise, Gain 4,
or Gain 3 with Harm 3, holds the plan only with Work 1 or 2. Every other Gain 3 or 4 note is a
follow-up, even a Gain 3 note with Harm 1 or 2 and Work 1 or 2. Gain 1 or 2 is lived with.
Forge writes each below-bar note's disposition. A read passes when no note is at the bar.
Score a note at the bar only when
the plan is wrong, contradicts itself, or a builder could not act on it. Still start each note with
`Blocking:` or `Advisory:`; Forge reads that label only for a note without scores.

## What counts
Report exactly what falls inside this boundary: nothing outside it, and nothing inside it left out.

Raise, under one of these lines:
- Functional: a defect on a path people or agents normally hit, such as setup, upgrade, switching
  a documented setting, re-running or restarting a command, a common repo layout, or a changed
  screen's keyboard access, labels or readable contrast.
- Security: a security gap, such as missing validation, authorization or secrets handling.
- Data loss: data lost, corrupted or exposed.
- Scale: a scale or performance problem at a realistic size the finding names, a cost repeated on
  every normal run, or growth with no bound.
- Not done: an unmet Done-when item, or a doc the change delivers that contradicts itself or a
  recorded decision.
- Test: a missing or hollow test for a Done-when item's own behaviour.
- Moving part: a new dependency, service, datastore, queue, background job or abstraction layer
  that the plan's `New moving parts` line doesn't name or, in a plan, that no Done-when item needs.
- Gate: a P1 this page names elsewhere: a broken Standard, a Promote, the proof list, the
  functional check, the UI skills, an allowance that doesn't match, a file outside Scope the work
  doesn't need, or a weakened test.
- Plan gap: something that would make the build wrong or stall it: a contradiction, a question a
  builder must ask, a shared name no earlier task pins, a likely case or refusal no rule or test
  covers, a one-way step missing from Risks, a task that is too big, a shape bigger than the Done
  when needs, work no Done-when item needs, or a known trap the change is likely to meet.

Leave out, unless it falls under Security or Data loss or the finding names a realistic scenario
that makes it likely in normal use:
- a rare combination that needs an unusual sequence: a crash or interrupt at a precise moment, a
  window under a second, a hand-edited or corrupted local file, or a platform, shell or tool
  version the repo doesn't support or the change is unlikely to meet;
- a case a fail-closed rule in the change already covers;
- extra test variations (one command-level test per rule is enough), unless the finding names a
  concrete scenario the current tests would pass while the code is broken;
- hardening beyond what the item promises;
- style, wording and preferences;
- a duplicate of another finding in this round.

An edge case is inside the boundary only when a Done-when item names it, when the finding names a
realistic scenario that makes it likely in normal use, or when it falls under Security or Data
loss. Every finding you raise names its line as `Raise: <line>` at the start of its evidence.

Prefer one blunt fail-closed rule with one test over listing every case.

Check:

1. Can every part be built without asking? Name each gap and contradiction. Name every function,
   field, file format or command that two tasks both use and that no earlier task pins: the first
   task that needs it must pin it.
   Flag every After link or shared Scope entry that exists only because of a shared line (a
   command-table row, a guide list, a registry), and name the split: the shared line to one task
   or a small last wiring task.
2. Is this simple enough?
   - Each task must map to the "Done when" items it covers. When a confirmed spec is included
     above, each "Done when" item must also map to the spec's behaviour or success measure; with
     no confirmed spec, skip that mapping. Anything that maps to nothing gets
     `Cut or defer: <item>`.
   - Each entry in `New moving parts` needs its "Done when" item and a reason the lower rungs
     won't do: reuse, the standard library, the platform, an installed dependency. If it has
     neither, write `Simpler: <part> → <lower rung>`.
   - When a smaller shape would deliver the same "Done when", name it: fewer tasks, one path
     instead of variants, removing a step instead of adding one.
   - A task that covers more than three "Done when" items, or whose Scope suggests more than
     about 400 changed lines, gets `Split: <task> → <two tasks>`.
   - Flag any one-way step (deleting data, a destructive migration, a new vendor) that isn't
     listed under Risks.
   - Never propose dropping validation, security, data-loss protection or accessibility.
3. Are the rules that meet each "Done when" item pinned down and proven? Ask, for the cases
   normal use is likely to hit:
   - which inputs and states it must handle: empty, missing, malformed, already done, half done;
   - which platforms and shells it meets, only those the change is likely to run on: Windows
     PowerShell and cmd, WSL, macOS, Linux CI;
   - which failure and refusal paths it has, and what the user sees on each;
   - which test, in which task's Tests cell, proves each rule.
   A case the doc says doesn't apply, with a reason, needs no test. Report a likely case no rule or
   test covers as `Unproven: item <n>: <case>`, naming the realistic scenario that hits it, which
   the current tests would pass while the code is broken. A rare case is not a finding.
4. Does any item hit a known trap it is likely to meet? Report each as `Trap: <trap>: item <n>`.
   Raise a platform or shell trap only when that platform is likely for the change. Forge's
   general traps:
   - Windows line endings and shells: CRLF text, PowerShell and cmd quoting, `\` paths;
   - no network in CI;
   - a new settings key the installed Forge rejects;
   - documentation tasks skipping their required tests;
   - tests that fail only under machine load;
   - values a frontend build fixes at build time.

   This repository's own known traps, from its AGENTS.md:

$traps

If the doc is a spec (it has no Tasks table), skip the checks about tasks and `New moving parts`.
Instead, check that the Why or the success measure needs every behaviour line, variant, role,
setting and integration, and write `Cut or defer: <item>` for any that nothing needs.

## Scores
Score every note on Gain, Work and Harm, each an integer from 1 to 5. The scores are your
judgement, not measurement. Write them as one line, exactly `Gain <g>, Work <w>, Harm <h>`,
as the last line of each note, after its evidence.

| Score | Gain (how much fixing helps) | Work (effort to fix) | Harm (what breaks if it goes wrong) |
|---|---|---|---|
| 1 | wording, a rare edge nobody named | a line, no new test | nothing; a revert undoes it |
| 3 | a Done-when item partly unmet for a named case; a test that passes with the code broken | one file and one command-level test, under an hour | client-visible behaviour change, reversible by a revert |
| 5 | security, data loss, the main case of a Done-when item not done | a new module, a second platform or language, a migration | one-way: data, a migration, a release clients upgrade to |

Harm floor: a note raised under Security or Data loss, or one that names a migration, scores
Harm 4 or more. Forge raises a lower Harm to 4 and marks the line `(floor: <why>)`.

Examples: "Close's default test selection breaks Go repos" Gain 3, Work 4, Harm 2. "Close skips
Jest `__tests__` folders" Gain 2, Work 2, Harm 1. "A blocked review is shown as waiting for checks
when tests pass on retry" Gain 3, Work 2, Harm 1. "Promotion accepts an uncommitted roadmap entry"
Gain 4, Work 2, Harm 2. "A stuck stop's narrow or split answer never reaches the worker" Gain 4,
Work 1, Harm 1. "Land shows a generic waiting line instead of the stop question" Gain 3, Work 1,
Harm 1. "Doctor credits a model to the wrong file in a rare mix of local settings" Gain 2, Work 1,
Harm 1. "Upgrade pull requests are checked by the previous release" Gain 2, Work 4, Harm 1. "A
proof test checks only the question's first lines" Gain 2, Work 1, Harm 1.

- Raise a note only after you check it against the code at the current commit, and name the
  file and line.
- A `Not done` note scores Gain by how much of the Done-when stays unmet: the main case unmet is
  Gain 4 or 5; one more rare combination on a clause whose main case works is Gain 1 or 2. When
  earlier rounds already raised that clause, say so and propose to narrow the clause.
- Only you score. The coordinator and the worker never change a score, and notes in a proof list
  do not lower one.

Write only your findings, as a numbered list: each finding starts a line with its number (`1. `,
`2. `, ...), states the finding in one line, then gives brief evidence on indented lines, starting
with `Raise: <line>`, then ends with its score line, and no speculative suggestions. Use no other numbered lines. If there is
nothing to report, write exactly `No findings.` and nothing else. Do not number it or add a note
about tests you did not run.

<!-- forge:round -->
Round $round of your cold read of `$path`: you are continuing your own earlier read.

The agent gave your last round's blocking findings a disposition and changed the doc. Do not
change any file. This read is discarded if any file in the repository changes. Open `$path` and read the
whole doc again yourself. Its diff since your last round:

$diff

All earlier rounds' settled notes, each with its scores and its disposition:

$dispositions

These are known and accepted. A settled note comes back only with new evidence of harm, as
`Disputed keep <n>: <the new harm>`, where `<n>` is its number.

For a story, the confirmed spec's diff since your last round, empty when it is unchanged:

$spec_diff

When that diff is not empty, check the plan still matches the changed spec. Re-read the
`## Answers` section of `docs/product/BRIEF.md` from the checkout: it can change between rounds.
Its diff since your last round, empty when it is unchanged:

$answers_diff

Check:

1. Is each of those findings closed? `cut` means the doc was edited to remove it, `defer` that it
   moved to the spec's Out of scope, and `keep` that it stays for the stated reason.
   Settled findings stay settled: do not repeat a disposed note or finding. Forge ignores a
   repeat with the same finding text, even when its evidence or number changes. Report a new
   defect as a distinct finding and explain the new evidence.
   - Raise a kept finding again only with new evidence of a distinct defect, as
     `Disputed keep <n>: <why>`, where `<n>` is the kept finding's number.
   - Never raise again a finding whose disposition cites a `Decided:` line. The human settled it.
${look}Write only your new findings, as a numbered list starting at $next, in your first round's format.
End each finding with its score line, scored as in your first round.
Block only when the plan is wrong, contradicts itself, or a builder could not act on it.
Prefix blocking findings with `Blocking:` and other notes with `Advisory:` after the number;
advisory notes need no disposition or another round.
If there is nothing to report, write exactly `No findings.` and nothing else.

<!-- forge:edit -->
Round $round of your cold read of `$path`: you are continuing your own earlier read.

Your last round passed, and the doc changed since. Do not change any file. This read is
discarded if any file in the repository changes. Its diff since your last round:

$diff

It touches these sections: $touched.

For a story, the confirmed spec's diff since your last round, empty when it is unchanged:

$spec_diff

For a story, the diff of the `## Answers` section of `docs/product/BRIEF.md` since your last
round, empty when it is unchanged:

$answers_diff

Check only this diff and the sections it touches, not the rest of the doc, which passed, plus
any spec or Answers diff above: apply your first round's checks and What counts to them,
including Forge's general traps and this repository's own known traps:

$traps

For a story from round 3 on, block only on changed text in the diff, the spec's diff or the
Answers diff, or on an earlier blocking finding that remains open. Other gaps in unchanged text are `Advisory:`, even inside a touched
section.

Write only your new findings, as a numbered list starting at $next, in your first round's format.
End each finding with its score line, scored as in your first round.
Block only when the plan is wrong, contradicts itself, or a builder could not act on it.
Prefix blocking findings with `Blocking:` and other notes with `Advisory:` after the number;
advisory notes need no disposition or another round.
If there is nothing to report, write exactly `No findings.` and nothing else.

<!-- forge:look -->
2. Look for new gaps anywhere in the doc, not only in the diff, with your first round's checks
   and What counts: each "Done when" item's rules and the test that proves each, shared
   names no earlier task pins, task size, and Forge's general traps and this repository's own
   known traps:

$traps

<!-- forge:cap -->
2. This is round $round: the text the diff does not touch has had its two rounds of notes.
   Block only on changed text in the diff, the spec's diff or the Answers diff, or on one of
   those findings that is not closed.
   Any other note on unchanged text is `Advisory:`, even inside a touched section. Apply your first
   round's checks and What counts to the diff, including Forge's general traps and this
   repository's own known traps:

$traps

<!-- forge:notes -->
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
