---
reader: codex (gpt-6-sol)
read_at: 2026-09-27T16:51:07+00:00
read_hash: 39fb7c166c5f78c9c66c76db630fe4b5ca0488d3
amended_hash:
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. The spec is missing, so the story cannot yet be checked against its behaviour or success measure.
   `docs/specs/own-your-entry.md` does not exist, and the roadmap item has no spec reference. Owner confirmation is a prerequisite to approving this story; task A cannot supply that confirmation afterward. Complete it as a prerequisite fix.
   Disposition: keep the spec is confirmed by the owner and on the roadmap in the promoted task's branch, which this read didn't see

2. The fixed module tuple in `cli.py` recreates a shared command list.
   A command in a new module would require a `cli.py` edit, contradicting Done when 5. `GROUP_HELP` ownership also changes if a new command becomes a group’s first. Pin discovery and stable group ownership in COMMANDS, and make the fixture add a command in a new module.
   Disposition: keep discovery is by pkgutil over the package, no fixed list; group help declared exactly once, tested; the fixture adds a command in a new module

3. PAGE has no pinned way to generate a source-only `docs/commands.md`.
   Adding it to `sync.files` would make `init`, `doctor` and `migrate` treat it as a client file, violating the unchanged-files promise. SHIPS must pin the source-only output path and its relationship to `sync.files` and `sync.write` before PAGE uses it. The story must also reconcile a new `forge sync` “Wrote” message with its unchanged-messages promise.
   Disposition: keep docs/commands.md is written only in Forge's own repo, outside sync.files; client output and messages unchanged

4. SHIPS does not assign owners or define declarations for every current output.
   The existing list includes conditional `CLAUDE.md`, files expanded for both hosts, and files found by a template glob. A fixed `(path, render)` pair does not say how those are included or omitted. Pin those rules and the owner of each output; keeping their declarations in `sync.py` would contradict Done when 3.
   Disposition: keep ships(top, cfg) returns a path-to-text mapping per owner, covering conditional, per-host and folder files; owners pinned

5. COMMANDS pins field names but leaves the shared declaration contract open.
   COMMANDS and PAGE both depend on the types and loading rules for `run` and `args`, the ordering rules for `position`, and the exact `listing` text used for today’s guide table. COMMANDS must pin these, including group help and row order, before PAGE builds from them.
   Disposition: keep the declaration fields, their types, ordering by position and listing text are pinned in COLLECTOR

6. SHIPS has an unexplained `After: COMMANDS` dependency and avoidable shared Scope.
   The current `doctor`, `init` and `migrate` callers already use `sync.files`; SHIPS need not edit them merely to read a gathered list. COMMANDS and SHIPS also both claim six source modules. If they share a module collector, COMMANDS must pin it; otherwise assign each shared file to one task or a small last wiring task and remove the dependency created solely by overlap.
   Disposition: keep doctor, init and migrate left out of SHIPS; the After stays because SHIPS shares files with COMMANDS

7. Split: COMMANDS → collector and contract; command-module migration.
   Its Scope covers 18 source modules and a contract test, suggesting more than about 400 changed lines. Pin the collector and cross-module test first, then migrate declarations in bounded module groups.
   Disposition: keep split into COLLECTOR (format, collector, contract, first six modules) and COMMANDS (the rest)
