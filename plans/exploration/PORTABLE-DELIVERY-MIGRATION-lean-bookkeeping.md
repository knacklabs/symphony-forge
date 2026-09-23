---
story: FORGE-COORD-1
task: PORTABLE-DELIVERY-MIGRATION
title: Lean bookkeeping — git is the ledger; commit only what git cannot reconstruct
status: draft
source: owner direction 2026-09-23 ("keep bookkeeping as lean as possible"), option (a)
---

## Problem

PR #229 changed 837 files; only 148 were product code, docs and tests. The other 689 were Forge
bookkeeping: 268 per-event JSON files, 254 other `.factory` records (review generations, briefs,
combined briefs, triage, verify logs, stage measurement history), 89 per-lesson files and 78
per-window quickfix files (an open and a done record for every window). Reviewers and the Codex
review both read that noise, and it grows with every task.

## Principle

Git already records who changed what and when. Forge commits only the authority git cannot
reconstruct, in the fewest files, as append-only lines that merge without conflicts.

## Added acceptance criteria (on top of the recorded Portable criteria 1–12)

13. Lessons live in one append-only `plans/lessons.jsonl`; quickfix/Lite/degraded windows are one
    line each in the story's log, not an open file plus a done file. The PR `Ticket:` line stays the
    declaration Gate A reads.
14. Every committed append-only log (`events.jsonl`, `lessons.jsonl`) is marked `merge=union` in
    `.gitattributes`, so parallel branches merge their appended lines without conflicts; readers
    tolerate duplicate lines by event ID.
15. Events that only restate git facts (task started, stage done, PR linked, commit made) are not
    written; readers derive them from `git log`, commit trailers and the PR link.
16. Per task, the only committed proof is one `proof.json`: verify and test outcome, selected review
    verdict and blocking findings, and SHA-256 identities of every input (brief, review report,
    JUnit, product tree). Review generations, briefs, combined briefs, triage and verify logs move to
    the per-worktree git control directory (where stage state already lives) or a gitignored
    `.factory/tmp/`; nothing in normal runtime reads them from the commit.
17. Done stages keep only `id`, `title` and `status` in committed stage state; measurement history
    and receipts stay local.
18. A CI budget check fails a PR whose bookkeeping (everything under `.factory/` and `plans/` except
    active plans and decompositions) exceeds 10 files or 2,000 changed lines, naming the offenders.
19. `forge upgrade` folds existing per-lesson, per-window and transient files into the new layout
    once, with the same crash-safe inventory/readback/removal contract as criteria 3–6.

## Approach

- Reuse the Portable event-log writer for `lessons.jsonl` and window lines; no second log format.
- `.gitattributes` gains `merge=union` lines; no custom merge driver.
- `proof.json` replaces `verify.json`, `tests.json` and `reviews/selected.json` + `generations/`;
  pr-ready and the ship gate read `proof.json` plus the recomputed identities.
- The budget check is one small script in `factory/scripts/` wired into `factory-scaffold` CI.

## Out of scope

No event compaction or rewriting of history (criterion 9 stands). No change to what a gate decides —
only where its evidence is stored.

## Verification

Focused tests for each criterion; one end-to-end task run in a scratch repo showing its PR carries
at most 5 bookkeeping files; the budget check red on a synthetic 11-file bookkeeping PR and green
on the real one; Linux and native Windows proof for union-merged appends and the migration.
