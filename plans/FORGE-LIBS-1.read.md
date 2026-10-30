---
reader: codex (gpt-6.1-sol)
read_at: 2026-10-25T18:34:25.733895+00:00
seconds: 138.323
read_hash: 8a24ea203d4dfd08cc57a38a5ffc1b612b7ca8b2
round: 2
passed: no
doc_seen: 8a24ea203d4dfd08cc57a38a5ffc1b612b7ca8b2
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 2642caa26cc9277049c5e3a5380d517e3c5dc771
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1744a-ea14-7ba3-914f-74467a3f8217
session:
loop_choice: accept
loop_reason: The owner accepted; the two Python parent revision ids are corrected to full ids in the builders section
---
# Cold read notes

Written by `forge read`. Under every blocking finding, write one disposition line, amend the
doc, then run `forge read <doc>` again until a round has no blocking notes. Notes marked
`Advisory:` are recorded without requiring a disposition or another round:

- `Disposition: cut` when the doc was edited to remove it;
- `Disposition: defer` when the item moved to the spec's Out of scope;
- `Disposition: keep <one-line reason>` otherwise.

A finding inside What counts is cut or deferred. Keep one only when it falls outside that boundary
or is factually wrong or not worth the change, and give as the reason the Leave out line, the
missing Raise line, the cited fact that disproves it, why it is not worth the change, or the
human's `Decided:` line.

Only a genuine trade-off goes to the human, as a question with options.

## Round 1

1. Blocking: The Python schema revision forks the database story’s revision chain.
   Raise: Plan gap. Case: normal use - both stories land before a new Python app starts.
   [This plan](/plans/FORGE-LIBS-1.md:241) puts `0008_module_schemas` after `0007`. The local `story/FORGE-DATABASE-1:plans/FORGE-DATABASE-1.md:346` also puts `0008_columns` directly after `0007`, creating two Alembic heads. Its task rows at lines 475–476 also lack the schema prerequisites claimed here at lines 339–342. No task owns reconciling those contracts.
   Gain 4, Work 2, Harm 4
   Disposition: cut

2. Blocking: SERVER excludes the web configuration required to remove `@app/shared`.
   Raise: Plan gap. Case: normal use - installing the starter after SERVER merges.
   [SERVER’s Scope](/plans/FORGE-LIBS-1.md:329) permits only import changes under `apps/web/src`. But [apps/web/package.json](/src/forge/templates/starter/apps/web/package.json:6) still requires `@app/shared` through `workspace:*`, and [tsconfig.json](/src/forge/templates/starter/apps/web/tsconfig.json:30) references the removed library. These files must change before WEB can start.
   Gain 4, Work 1, Harm 1
   Disposition: cut

3. Blocking: SERVER and WEB break the Python starter before PYWEB can repair it.
   Raise: Plan gap. Case: normal use - creating or testing a Python app between these independently merged parts.
   [SERVER rewrites the shared web imports](/plans/FORGE-LIBS-1.md:181), then WEB moves their sources into libraries. [Python composition](/src/forge/init.py:154) copies only `apps/web` and two root files from TypeScript. Copying the new libraries and creating Python contracts is deferred to PYWEB, after both changes. The intervening Python apps therefore have unresolved imports or missing screens.
   Gain 4, Work 2, Harm 2
   Disposition: cut

4. Blocking: The pinned Python vendor contract rejects a clean starter.
   Raise: Functional. Case: normal use - running `test:imports` before any vendor provider exists.
   [The prescribed contract](/plans/FORGE-LIBS-1.md:155) supplies unmatched provider exemptions without changing import-linter’s default `unmatched_ignore_imports_alerting = error`. The [pinned version is 2.15](/src/forge/templates/starter-python/apps/api/pyproject.toml:17); its `importlinter/contracts/forbidden.py:76–87` makes those missing imports errors. It also rejects external subpackages such as the prescribed `google.cloud` at lines 241–248. Removing uninstalled packages does not resolve the unmatched exemptions.
   Gain 4, Work 2, Harm 2
   Disposition: cut

5. Advisory: The Python web app receives no vendor-SDK restriction.
   Raise: Not done. Case: normal use - a Python app’s web hook imports a listed SDK.
   [Item 3](/plans/FORGE-LIBS-1.md:221) adds only restrictions on `@app/*-web` and `@app/*-server`. Its [separate ESLint configuration](/src/forge/templates/starter-python/eslint.config.mjs:6) is not copied from TypeScript, and Python import-linter cannot inspect TypeScript. An `openai` import in `libs/projects/web` therefore passes despite the both-starters promise at plan lines 12–14.
   Gain 3, Work 2, Harm 2
   Disposition: cut

6. Advisory: Relative imports bypass the Python web boundary.
   Raise: Not done. Case: normal use - an editor inserts a relative import from another module’s hook.
   [The prescribed patterns](/plans/FORGE-LIBS-1.md:223) match package names only. From `libs/projects/web/src/reach-in.ts`, importing `../../../organisations/web/src/<hook>` matches none of them. The planned package-name-only negative case passes while this direct cross-module dependency remains permitted.
   Gain 3, Work 2, Harm 2
   Disposition: cut

7. Advisory: Shared guide and workflow edits still have competing owners.
   Raise: Plan gap. Case: normal use - starting the tasks whose listed prerequisites have finished.
   [The task rows](/plans/FORGE-LIBS-1.md:330) leave WEB/SCHEMAS sharing `brief.md`, PYWEB/SCHEMAS sharing the workflow, PYWEB/SCHEMASPY sharing `python.md`, and GUIDE/SCHEMASPY sharing `skill.md` and synced copies without ordering. [Task start](/src/forge/task.py:355) refuses overlapping scopes. GUIDE’s stated dependency on SCHEMAS is itself only for shared files. Assign these shared text and registration edits to one wiring owner.
   Gain 3, Work 2, Harm 1
   Disposition: cut

8. Advisory: SERVER’s required tree test includes libraries delivered later by WEB.
   Raise: Test. Case: normal use - closing SERVER before WEB starts.
   [Test 1 requires every folder in the table](/plans/FORGE-LIBS-1.md:185), including `shared/ui`, `core/web` and every module’s `web` library. Those belong to WEB, which waits for SERVER. The prescribed assertion cannot pass in SERVER’s own completed state.
   Gain 3, Work 1, Harm 1
   Disposition: cut

9. Advisory: The TypeScript smoke job also selects the new Python live tests.
   Raise: Scale. Case: normal use - every starter pull request runs both smoke jobs.
   [The workflow instructions](/plans/FORGE-LIBS-1.md:300) add both mixed-stack test files to the TypeScript command without excluding Python, then add their Python cases to the Python job too. The [existing TypeScript command](/.github/workflows/starter-smoke.yml:34) has no stack filter. Python browser and schema runs therefore execute in both jobs.
   Gain 3, Work 1, Harm 2
   Disposition: cut

## Round 2

10. Blocking: The fork fix introduces parent revision IDs that Alembic cannot resolve.
    Raise: Functional. Case: normal use - a new Python app runs its startup migrations.
    [Plan lines 228–230](/plans/FORGE-LIBS-1.md:228) name `0007_ids_and_updated_at` and `0008_module_schemas` but prescribe `down_revision = "0007"` and `"0008"`. The starter uses full IDs, as [its existing revision shows](/src/forge/templates/starter-python/apps/api/migrations/versions/0005_history.py:8). Alembic 1.20.0’s `script/revision.py:233–240` resolves parent IDs by exact lookup. These shortened IDs therefore fail, and the [startup command exits before starting the API](/src/forge/templates/starter-python/Dockerfile:19). Both parent references need their full revision IDs.
    Gain 5, Work 1, Harm 4
   Disposition: keep - The owner accepted; the two Python parent revision ids are corrected to full ids in the builders section
