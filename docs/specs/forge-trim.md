---
slug: forge-trim
title: Forge sheds dead and duplicated code before it grows again
status: draft
saved: 2026-09-27T16:10:53+00:00
---

# Forge sheds dead and duplicated code before it grows again

## Why

Forge's rule is that it shrinks over time, enforced by an 8,000-line ceiling on `src/forge`. It
now sits at about 7,960 lines, so the next stories (agent merge, one-chat approval) can't land
their code. A first attempt reached the number only by joining lines and dropping blank lines,
which makes the code harder to read and removes nothing. A read-only audit found about 415 lines
Forge really carries for nothing: unreachable branches, a fallback for a module that now always
exists, three copies of the same file helpers, repeated story-doc parsing, docstrings that restate
the spec, the finished mode for migrating Forge's own repo, a skill text Forge never reads, and a
skill section that repeats the standards page.

## Behaviour

**Nothing a user sees changes,** except where the owner chose it below: every command's output,
refusals and generated files stay as they are, and every existing test keeps passing unless it
tests something this spec removes.

**Dead code goes.** The CLI's "not built" refusal and its missing-module branch, the prcheck
fallback import for `story`, and the standards-file existence check in the worker and its brief
wrapper are removed, since every module and the standards page always ship.

**Duplicates become one.** The file read and write helpers, the JSON-output helper, the worktree
list parsing, the worktree creation, the blocking-findings check, the shared refusals, the roadmap
append, the cold-read record and disposition checks, the story-doc section, table and cell parsing,
the approval hash, the interface-promotion problem and the temporary-index snapshot each live in
one place and are called from the others. Where two callers print different wording today, the
wording is passed in and stays the same.

**Docstrings stop restating the spec.** Module and function docstrings that repeat a spec section
or another module's docstring shrink to a short statement plus a pointer.

**The finished own-repo migrate mode goes.** `forge migrate`'s mode for moving Forge's own repo off
the copied-in Forge, and its tests, are removed; the v1 spec's passages about it are amended to say
the move finished at the switch. Migrating a copied-in client is unchanged.

**The migration skill text moves to `docs/`.** `src/forge/templates/migrate-skill.md` moves to
`docs/migrate-skill.md`, and the test that reads it follows it.

**The skill points to the standards page.** `forge sync` writes the standards page next to the
Forge skill, as it does the FDE guidance, and the skill's "Build simple" section becomes a short
pointer to it plus its "Finding forms" lines.

**No reformatting.** The reduction comes from removed or merged code and text, never from joining
lines or removing blank lines between definitions.

## Acceptance criteria

- `src/forge` counts at least 400 fewer lines than on main by the ceiling test's own count, with
  the ceiling unchanged at 8,000.
- No change joins lines or removes blank lines between definitions to save lines.
- The full test suite passes, with only tests of removed behaviour removed or moved.
- Every command's help and every refusal text that tests pin is unchanged.
- `forge migrate` has no own-repo mode, and the v1 spec says why; a copied-in client migrates as
  before.
- The migration skill text is at `docs/migrate-skill.md`.
- `forge sync` writes the standards page next to the Forge skill, and the skill's "Build simple"
  section points to it.

## Success measure

- Metric: lines in `src/forge` by the ceiling test's count.
- Baseline: about 7,960 on 2026-09-27.
- Target: at most 7,560.
- Check date: 2026-10-15

## Out of scope

- Changing any command's behaviour or output beyond the owner-chosen moves above.
- Raising or lowering the ceiling.
- Removing the vendored test-audit skill.

## Roadmap

- FORGE-TRIM-1: Forge sheds dead and duplicated code before it grows again
