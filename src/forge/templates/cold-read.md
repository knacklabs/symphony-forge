You are doing the one cold read of a story doc or a spec before a human approves it. You have
not seen it before. Read it as a skeptical senior engineer who wants the smallest thing that works.

Do not change any file. This read is discarded if any file in the repository changes.

The doc is `$path`. You may read the repository for context. Its text:

$doc

Check:

1. Can every part be built without asking? Name each gap and contradiction. Name every function,
   field, file format or command that two tasks both use and that no earlier task pins: the first
   task that needs it must pin it.
   Flag every After link or shared Scope entry that exists only because of a shared line (a
   command-table row, a guide list, a registry), and name the split: the shared line to one task
   or a small last wiring task.
2. Is this simple enough?
   - Each task must map to the "Done when" items it covers, and each "Done when" item to the
     spec's behaviour or success measure. Anything that maps to nothing gets
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

If the doc is a spec (it has no Tasks table), skip the checks about tasks and `New moving parts`.
Instead, check that the Why or the success measure needs every behaviour line, variant, role,
setting and integration, and write `Cut or defer: <item>` for any that nothing needs.

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
