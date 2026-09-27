---
reader: codex (gpt-6-sol)
read_at: 2026-09-27T16:43:51+00:00
read_hash: a4f48e7d6d779f8607e3e31c55075b405774c0d6
amended_hash: 306e0808d100c6e798235461dd5162586fcd6048
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. The generated guide table remains a shared file, contradicting the target of no waits caused by shared files.
   A new command must change `docs/guide.md` when the regeneration command runs, despite the criterion that it changes only its owning module and tests. Assign guide regeneration to a small final wiring task, or revise that criterion and the success measure.
   Disposition: keep the owner chose a generated docs/commands.md written by forge sync, never in a task's Scope, conflicts settled by regenerating

2. The command declaration contract is not pinned tightly enough to preserve help output.
   `cli.py` currently fixes command order, subgroup order and group help in `TABLE` and `GROUPS`; groups such as `spec` span modules. The first CLI task must define discovery, ordering, group ownership and the declaration fields. It must also replace the `TABLE` reader in `tests/test_contracts.py` while preserving its state changing command check.
   Disposition: keep pinned discovery from a fixed module list, declared position, group help ownership and the contract test's switch to declarations

3. Shipping ownership and source format are unspecified.
   The named skills, adapters, hooks and workflow do not each have an owning module today. `sync.files()` also renders merged files, conditional `CLAUDE.md`, repo dependent CI text and template globs; `shims()` writes hooks separately. The first sync task must assign owners and pin a declaration format that preserves these paths, rendering rules and `doctor`/`init`/`migrate` callers. A newly shipped template also necessarily changes its source file, which the “only the module” criterion omits.
   Disposition: keep pinned one owning module per shipped file and a path-plus-render-function declaration that keeps sync's rendering rules and its doctor, init and migrate callers

4. The declared command data cannot reproduce the current guide table.
   One-line help and arguments do not contain the guide’s usage examples or fuller descriptions, notably for `doctor` and `spec payback`. The first guide task must pin either additional per-command guide fields and exact table formatting, or an explicit change to those rows; the spec currently promises neither.
   Disposition: keep declarations carry the fuller description and example the table shows today, in today's format
