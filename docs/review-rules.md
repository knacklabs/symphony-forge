# How Forge weighs a note

Two checks read your work before Forge ships it. The **cold read** reads the plan of a story
before you approve it. The **code review** reads each change before it merges. Both checks use
the same three scores and the same bar. Thus Forge judges a plan note and a code review note in the
same way.

## Three scores

The reader gives each note three scores from 1 to 5. The scores are a judgement. They are not a
measurement.

| Score | 1 | 3 | 5 |
|---|---|---|---|
| **Gain**: how much the fix helps | the words of a sentence, or a rare case that no one named | one case that the "Done when" names does not work | security, data loss, or the main case of a "Done when" does not work |
| **Work**: how much the fix costs | one line, no new test | one file and one test, less than one hour | a new module, a different platform, or a migration |
| **Harm**: what breaks if the problem stays | no part breaks, and a revert removes the change | a change that people can see, and a revert removes it | a change that you cannot reverse: data, a migration, or a release that clients install |

A note about security, data loss or a migration always gets Harm 4 or more. Forge sets this
floor if the reader gave a lower Harm. Forge shows the reason, for example
`Harm 4 (floor: security)`.

## The bar

| When | What occurs |
|---|---|
| Harm 4 or 5, or Gain 5 | The note stops the work. The worker fixes it now. |
| Gain 4, or Gain 3 with Harm 3, and Work 1 or 2 | The worker fixes it in this round. |
| Gain 4, or Gain 3 with Harm 3, and Work 3 or more | The note becomes a follow-up fix. The work continues. |
| Other Gain 3 notes | The note becomes a follow-up fix, even at Work 1 or 2. The work continues. |
| Gain 1 or 2 | Forge keeps the note in its record and does not fix it. |
| Harm 3, and the note adds new scope or reverses your decision | The agent asks you. |

A Gain 1 or 2 note never stops the work. This is true also when the reader calls the note
serious. Only Harm 4 or more can stop the work for such a note.
The Harm 4 or 5 and Gain 5 stop rule comes first. Below that rule, Gain 3 holds work only at
Harm 3 with Work 1 or 2.

A note with `Case: rare` never stops the work, whatever its scores. A note that stops work
must name a case in normal use. A security hole or data loss that any user can reach is normal use.

From code review round two, the review checks each earlier finding and raises new findings only for P0s in normal use.
A fix that breaks the main path is a P0. At the round limit, open findings below P0 need your choice.
Accept puts them in Known issues as follow-ups with your reason.

A worker can decline a finding as "not worth the code" with a reason in a commit message.
Forge records it as a follow-up, even if no code changed. A P0 stays open.
Review rules and recorded owner decisions settle a question for later readers and reviewers.

## Who decides

- **The reader gives the scores.** The worker and the agent do not change a score.
- **Forge applies the bar.** A plan passes its read, and a change is ready to merge, when no
  note is at the bar.
- **The agent decides small items.** The agent decides each note with Harm 1 or 2 that a revert
  can remove. Then the agent tells you.
- **You decide the other items.** The agent asks you about Harm 3 or more, about new scope
  outside the approved "Done when", about your approval and merge steps, and about a change to a
  decision that you made.

## Forge keeps each note, and a settled note does not come back

- **Forge keeps each note below the bar.** The read notes, the pull request and the record of
  the item on the default branch show each note with its scores. Thus you can find a known
  problem when a bug occurs later.
- **A settled note stays settled.** You, the agent or Forge can settle a note. Each later read
  and review gets the settled note as known and accepted. A reader can show the note again only
  with new evidence of harm.
- **The cold read gives its decisions to the code review.** If you accepted a plan note, the
  code review does not show that note again.

## When a loop stops

A fix gets one review round. A story part gets two by default; `task_review_rounds` in `forge.toml` changes that number. At the limit, open findings below P0 stop the change.
Forge asks: "One more round, split or accept?" Close, land and work show the same question until you answer.

One more round gives the worker one more attempt. Split moves the open findings to a follow-up fix.
Accept puts them in Known issues as follow-ups with your reason.
A merge of the default branch or a clean review does not clear an unanswered stop.

An open P0 returns to the worker. A P0 is a security hole, data loss or a broken main path.
If the same P0 stays open for two worker rounds in a row, Forge stops with the stuck question.
Work waits for your recorded choice of switch, same, narrow or split.

`forge land` runs at most one fix round, including across session handbacks. If findings, tests
or checks still need a worker, land stops. A review stop exits with status 3 and prints the
question. Record the choice with `forge close <item> --resolve <more|split|accept> --reason
"<human's choice>"`, then run land again.

A cold read stops at its round limit (two by default; `cold_read_rounds` in `forge.toml` changes it) when notes below P0 are still open, or when P0 notes are open
in two rounds in a row. Forge asks: "One more round, split or accept?"
Forge waits for your choice and never starts a third round by itself. Record your choice with
`forge read <KEY or spec or decision> --resolve <accept|more|split> --reason "<human's choice>"`.

A note from an earlier release of Forge has no scores. Forge judges that note as before, until
the next read or review gives new scores.

## Three examples

1. **"The default test selection of close breaks Go repos."** Gain 3, Work 4, Harm 2. The fix
   helps, but it needs the tools of a different language. The note becomes a follow-up fix, and
   the change merges.

2. **"The migration removes a column that contains data."** The reader gave Harm 2. Forge sets
   Harm 4 (floor: migration). The note stops the merge until the worker fixes it.

3. **"This sentence in the plan is not clear."** Gain 1, Work 1, Harm 1. Forge keeps the note in
   the read notes and does not fix it. The plan goes to you for approval.
