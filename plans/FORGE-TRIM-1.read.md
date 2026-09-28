---
reader: codex (gpt-6-sol)
read_at: 2026-09-27T16:26:56+00:00
read_hash: f0e591678f023fe3b29711844a64480c92af5c9e
amended_hash: cd847c0bc59e0f53e574ccb4f599ab852cfa8433
---
# Cold read notes

Written by `forge read`. Under every finding, write one disposition line, amend the doc once, then
run `forge read <doc> --amended`:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

Only a genuine trade-off goes to the human, as a question with options. There is no second read.

1. The spec prerequisite cannot be completed without another owner decision.
   `docs/specs/forge-trim.md` and its cold read do not exist. The roadmap already has `FORGE-TRIM-1` without a spec link, so `forge roadmap add` would refuse that key. Complete the spec, read, confirmation, and roadmap repair before treating it as the authority for these tasks. Until then, the Done-when items cannot be checked against the spec’s behaviour or success measure. Cut or defer: the spec task from this implementation story.
   Disposition: keep the spec is confirmed by the owner and on the roadmap in the promoted task's branch, which this read didn't see; the task stays as the record

2. The byte-for-byte promise contradicts Done when 5.
   Done when 2 says every install makes `forge sync` write the same files as before, while Done when 5 changes both Forge skill files and adds a standards page. Pin the compatibility check to the existing test-audit, FDE, and Remote Control files; specify the intended changes to the sync output separately.
   Disposition: keep the byte-for-byte promise now names only the three skill texts; item 5's changes are on purpose

3. “One checked-in copy” is not delivered by SKILLS’ Scope.
   The package copies, both hosts’ test-audit and FDE files, and the Claude Remote Control file are all tracked. Removing only the package copies leaves multiple checked-in copies. Either define the goal as one *source* copy or include the generated copies’ tracking and regeneration in Scope.
   Disposition: keep reworded to one source copy: the synced copies in this repo are the source, the package copies go

4. SKILLS must pin the shared `sync.files` contract before STANDARDS uses it.
   Both tasks edit `src/forge/sync.py` and depend on its output paths. SKILLS must fix the built-package versus editable-install source lookup and the existing output manifest with a cross-boundary test; STANDARDS can then add the standards entry. The `After: MIGRATE` link serves only the aggregate line count, not a code dependency. Run that count and the full suite after all tasks instead.
   Disposition: keep SKILLS pins sync's file list and source lookup with a cross-boundary test; STANDARDS waits for all tasks only for the count

5. MIGRATE leaves a required confirmation step outside the plan.
   It edits the confirmed `docs/specs/lean-forge-v1.md`. The story acknowledges that this invalidates its confirmation but assigns no save, cold read, or owner reconfirmation step. Done when 3 therefore requires another human decision unless that spec edit is settled before task work.
   Disposition: keep the owner confirmed the trim spec, which says the v1 spec's passages change; the Risk stays, and re-confirming the v1 spec waits until it is measured

6. Split: MIGRATE → remove the own-repo mode and add the refusal; move the migration guide and update its reader test.
   Its Scope spans a substantial source-mode removal, existing migration tests, a confirmed spec, a guide move, and a new test file. The separate Done-when items 3 and 4 give the split a clear boundary.
   Disposition: keep split MIGRATE into MIGRATE and GUIDE

7. Split: SKILLS → establish the single source and package mapping; verify wheel, source distribution, and editable-install output.
   Deleting the three package skill copies alone removes 355 lines; the build, sync, and new test changes put its Scope beyond about 400 changed lines. Keep the byte-for-byte checks in the verification task.
   Disposition: keep split SKILLS into SKILLS and PACKAGING
