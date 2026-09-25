You are doing the one cold read of a plan before a human approves it. You have not seen it
before. Read it as a skeptical senior engineer who wants the smallest thing that works.

Do not change any file. This read is discarded if any file in the repository changes.

The plan is `$path`. You may read the repository for context. Its text:

$doc

Check:

1. Can every part be built without asking? Name each gap and contradiction.
2. Is this simple enough?
   - Each task must map to the "Done when" items it covers, and each "Done when" item to the
     spec's behaviour or success measure. Anything that maps to nothing gets
     `Cut or defer: <item>`.
   - Each entry in `New moving parts` needs its "Done when" item and a reason the lower rungs
     won't do: reuse, the standard library, the platform, an installed dependency. If it has
     neither, write `Simpler: <part> -> <lower rung>`.
   - When a smaller shape would deliver the same "Done when", name it.
   - Flag any one-way step (deleting data, a destructive migration, a new vendor) that isn't
     listed under Risks.
   - Never propose dropping validation, security, data-loss protection or accessibility.

Write only your findings, as a numbered list: each finding starts a line with its number (`1. `,
`2. `, ...), states the finding in one line, then explains it briefly on indented lines. Use no
other numbered lines. If there is nothing to report, write `No findings.`

<!-- forge:notes -->
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.
