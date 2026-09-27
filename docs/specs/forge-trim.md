---
slug: forge-trim
title: Forge sheds dead and duplicated code before it grows again
status: draft
saved: 2026-09-27T16:10:53+00:00
---

# Forge sheds dead and duplicated code before it grows again

## Why

Forge's rule is that it shrinks over time, enforced by an 8,000-line ceiling on `src/forge`. By the
ceiling test's own count it is at 7,961 lines, so the next stories (agent merge, one-chat approval)
can't land their code. A first attempt reached the number only by joining lines and dropping blank
lines, which makes the code harder to read and removes nothing. Two read-only audits, the second a
ponytail audit on Codex, found what Forge really carries for nothing: second copies of skill texts
that are already checked in byte for byte, the finished mode for migrating Forge's own repo, a
skill text Forge never reads, and a skill section that repeats the standards page.

## Behaviour

**One copy of each shipped skill text.** The test-audit skill (its SKILL.md and NOTICE.md), the
FDE guidance and the Remote Control skill each exist today both under `src/forge/templates/` and,
byte for byte, as the checked-in copies `forge sync` writes. The package copies go: the build
bundles the checked-in copies at the same package paths, so `forge sync` writes exactly the same
files as before, whether Forge is installed from a wheel, from a source distribution or as an
editable checkout.

**The finished own-repo migrate mode goes.** `forge migrate`'s mode for moving Forge's own repo off
the copied-in Forge, and its tests, are removed. In Forge's own repo (`repo = "forge-source"`),
`forge migrate` now refuses before doing anything, saying Forge's own repo moved at the switch, so
it can never take the client path there. The v1 spec's passages about the mode are amended to say
the same. Migrating a copied-in client is unchanged.

**The migration skill text moves to `docs/`.** `src/forge/templates/migrate-skill.md` moves to
`docs/migrate-skill.md`, and the test that reads it follows it.

**The skill points to the standards page.** `forge sync` writes the standards page next to the
Forge skill for both hosts, as it does the FDE guidance, and the skill's "Build simple" section
becomes a short pointer to it plus its "Finding forms" lines.

**Nothing else changes.** Every other command's output, refusal and generated file stays the same,
and no helpers are merged or rewritten for this. The reduction comes only from the removals above,
never from joining lines or removing blank lines.

## Acceptance criteria

- `src/forge` counts at most 7,561 lines by the ceiling test's count (at least 400 fewer than
  7,961), with the ceiling unchanged at 8,000.
- No change joins lines or removes blank lines to save lines.
- A wheel, a source distribution and an editable install each give `forge sync` the same test-audit,
  FDE and Remote Control files as before, byte for byte.
- In Forge's own repo `forge migrate` refuses before any change; a copied-in client migrates as
  before; the v1 spec says why.
- The migration skill text is at `docs/migrate-skill.md`.
- `forge sync` writes the standards page next to the Forge skill for both hosts, and the skill's
  "Build simple" section points to it.
- The full test suite passes, with only tests of removed behaviour removed or changed.

## Success measure

- Metric: lines in `src/forge` by the ceiling test's count.
- Baseline: 7,961 on 2026-09-27.
- Target: at most 7,561.
- Check date: 2026-10-15

## Out of scope

- Merging or rewriting shared helpers.
- Changing any command's behaviour or output beyond the owner-chosen moves above.
- Raising or lowering the ceiling.

## Roadmap

- FORGE-TRIM-1: Forge sheds dead and duplicated code before it grows again
