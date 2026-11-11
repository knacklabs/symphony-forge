---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-11T11:03:12.765666+00:00
seconds: 180.631
read_hash: 2fac06c23bb89cd2077fa21b209e41c8a0148796
round: 5
passed: no
doc_seen: 2fac06c23bb89cd2077fa21b209e41c8a0148796
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 8b9a2004e36776cc9a4b77125b11a6a6cf8c0880
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1ca18-47ba-77a0-80ef-f0460a3afaad
session:
loop_choice: more
loop_reason: Owner's standing choice for 11 Nov 2026: one more round for one test-order point
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

1. Blocking: Data loss: The move-over instructions can delete other ignored files.
   Raise: Data loss
   [The plan](/plans/FORGE-GENCOMMIT-1.md:87) runs `git clean -fdX` on the whole types folder. The starter also ignores files named `.env` and `dist` folders ([.gitignore](/src/forge/templates/starter-python/.gitignore:1)).
   Case: normal use - An existing app has other ignored files in that folder; the command deletes them, and reverting the fix cannot restore them.
   Gain 4, Work 1, Harm 4
   Disposition: cut - the move-over step now runs `git rm --cached` on the two named paths only, says it removes only these two files from git's index and keeps them on disk, forbids `git clean` and path patterns, and proves the move with the fix's own test run; `test_5` checks the text has no `git clean`.

2. Blocking: Not done: New-app setup can fail after a local types generation.
   Raise: Not done
   The plan expects generated files to be ignored in Forge’s template tree ([plan](/plans/FORGE-GENCOMMIT-1.md:68)). But [init.py](/src/forge/init.py:218) collects files from that tree without checking Git’s ignore rules, and [repo.py](/src/forge/repo.py:1180) passes them explicitly to `git add`. Git refuses the ignored paths.
   Case: normal use - A developer generates the types in the template tree, then uses that Forge checkout to set up a Python app. Setup stops before its first commit.
   Gain 3, Work 2, Harm 3
   Disposition: cut - the plan now states the order: setup writes and commits only the template's own files, which no longer include the two files, so setup never names them in a new app or on a second run; in Forge's template tree nothing makes them, the live run's copy skips both names, and making them there by hand first needs `node_modules` and `.venv`, which setup already copies and git already refuses today; the promise about the nested `.gitignore` is removed.

3. Blocking: Functional: An API-only fast test can miss a broken web request.
   Raise: Functional
   [The plan](/plans/FORGE-GENCOMMIT-1.md:67) retains type-checking but stops selecting browser tests for an API-only change. The Python API’s `ProjectInput` and the web contract’s `ProjectInput` are separate definitions ([API schema](/src/forge/templates/starter-python/apps/api/app/projects/schema.py:31), [web contract](/src/forge/templates/starter-python/libs/projects/contracts/src/index.ts:52)).
   Case: normal use - Adding a required API request field leaves the web form’s type unchanged, so the fast type check can pass while the request fails.
   Adds work: retain coverage of mismatched request bodies for API-only changes; F 2 x H 2 = 4; 2 x C = 4.
   Gain 4, Work 2, Harm 3
   Disposition: cut - `scripts/affected.mjs` now selects the web part for every `apps/api/` change and `scripts/test.mjs` runs `api-types` once before both parts, so an API change makes the types and runs the web type check, Vitest and the browser tests as today; `test_affected_py_starter.py` expects them for the API case and a live block in `test_starter_tree.py` proves a real API-only run fails on a broken web type.

4. Blocking: Plan gap: Moving the files out of scope can leave the same parts waiting.
   Raise: Plan gap
   The move-over steps remove the paths from planned parts but leave their `After` links ([plan](/plans/FORGE-GENCOMMIT-1.md:87)). Forge still enforces those links independently of scope ([task.py](/src/forge/task.py:451)).
   Case: normal use - Parts were chained only because they shared these files; they still wait for review or merge after the move-over.
   Adds work: remove dependency links that exist only for these files; F 2 x H 2 = 4; 2 x C = 2.
   Gain 4, Work 1, Harm 2
   Disposition: cut - the plan no longer promises that parts stop waiting, only that these two files no longer cause it; it names what API parts still share (the files `forge feature` edits, such as `apps/api/app/main.py`), and the guide step leaves `After` links as they are.

5. Blocking: Plan gap: The specified starter-test edits leave a contradictory assertion.
   Raise: Plan gap
   [The plan](/plans/FORGE-GENCOMMIT-1.md:79) removes the ordering assertion, but [the preceding assertion](/tests/test_python_starter.py:143) still requires `api-types` in `test`, which the plan removes from that script.
   Case: normal use - The new Python starter is checked by the existing starter test, and that test fails.
   Gain 4, Work 1, Harm 1
   Disposition: cut - `test` keeps its `api-types` call, so lines 143-144 of `test_python_starter.py` stay true and only the `api-types.ts` file check at line 145 is deleted.

6. Blocking: Gate: The replacement checks weaken the generated API contract tests.
   Raise: Gate
   The plan asks for a member-delete route in `organisations/routes.py`, but that route is in [auth/routes.py](/src/forge/templates/starter-python/apps/api/app/auth/routes.py:238). Source checks also replace the existing checks of the generated [member](/tests/test_member_removal.py:24) and [history](/tests/test_assistant_historypy.py:24) contracts.
   Case: normal use - A route remains callable but is omitted from the API contract; the proposed source check and live route test can pass while generated clients lose it.
   Gain 4, Work 2, Harm 3
   Disposition: cut - both contract tests keep today's assertions under the live smoke run on the contract the run generates in `run["folder"]`; the member route source now points at `apps/api/app/auth/routes.py`; the plan says plainly that outside the live run these tests no longer check the contract, and why that is acceptable.

7. Blocking: Test: The fast-test checks do not prove that the affected path runs the type check.
   Raise: Test
   [The planned test](/plans/FORGE-GENCOMMIT-1.md:78) uses `--list`, which returns before spawning commands ([test.mjs](/src/forge/templates/starter-python/scripts/test.mjs:20)). The live smoke run uses no base and takes the full-test branch ([test_starter_tree.py](/tests/test_starter_tree.py:237)).
   Case: normal use - A fast command that lists `tsc --build` but omits the contract projects can pass both checks while missing an API incompatibility.
   Gain 3, Work 2, Harm 3
   Disposition: cut - the selection test now also asserts that the listed `tsc --build` line names the shared API types, the history and projects contract projects and the web app; a new live block in `test_starter_tree.py` runs `node scripts/test.mjs <base>` for real after an API-only change that breaks a web type and asserts it fails with the TypeScript error in `libs/history/contracts/src/index.ts`.

## Round 2

8. Advisory: Not done: An API-only fast run can execute no web unit tests.
   Raise: Not done
   [The plan](/plans/FORGE-GENCOMMIT-1.md:70) keeps `vitest --changed <base> --passWithNoTests` from [test.mjs](/src/forge/templates/starter-python/scripts/test.mjs:71). Vitest selects changed files through Git and excludes ignored files. [Vitest source](https://raw.githubusercontent.com/vitest-dev/vitest/v3.2.4/packages/vitest/src/node/git.ts)
   Case: normal use - Only Python API code changes; the generated types are ignored, so no web test is selected and the command passes with zero tests.
   Gain 3, Work 2, Harm 3
   Disposition: cut - the plan now says exactly what a change to the API's code runs on the web side: `api-types`, the web type check and the browser tests always; Vitest stays changed-only because an API-only change leaves every web source file the same and the generated types are type-only imports removed before tests run, so no web unit test can see it; Done-when 2 no longer promises web unit tests; cost stated (a few minutes per such fast test, estimate).

9. Advisory: Plan gap: The updated selector conflicts with an existing test case.
   Raise: Plan gap
   [The plan](/plans/FORGE-GENCOMMIT-1.md:89) updates the tracked API-file case, but [the untracked API-test case](/tests/test_affected_py_starter.py:62) still requires `test:browser` to be absent.
   Case: normal use - A new API test selects the web part under the new rule, so this existing assertion fails.
   Gain 4, Work 1, Harm 2
   Disposition: cut - only a change under `apps/api/app/` (the code that makes the contract) selects the web part; a change to API tests, migrations or config selects only `api`, so the untracked `apps/api/tests/test_new.py` case keeps `test:browser` absent and no existing untracked case changes.

10. Advisory: Plan gap: The live regression conflicts with the history contract check.
    Raise: Plan gap
    [The plan](/plans/FORGE-GENCOMMIT-1.md:90) renames `HistoryEntry` in the live copy, then [the history test](/tests/test_assistant_historypy.py:26) reads that copy expecting `HistoryEntry`. The fallback selects another model, but the required error is still fixed to [the history contract](/src/forge/templates/starter-python/libs/history/contracts/src/index.ts:3), which reads only `HistoryEntry`.
    Case: normal use - The Python starter smoke run follows either named model choice and cannot satisfy both assertions as written.
    Gain 4, Work 1, Harm 2
    Disposition: cut - `_run_live_starter` reads the generated contract right after the full run and returns it as `run["contract"]`; the contract tests read only that, and the `HistoryEntry` rename runs last in the same copy, after which no test reads the copy; the fallback model is `Member` with its own expected file `libs/organisations/contracts/src/index.ts`.

11. Advisory: Functional: The conflict instruction fails when only one generated file changed.
    Raise: Functional
    [The guide step](/plans/FORGE-GENCOMMIT-1.md:105) names both paths in `git rm --cached`. Git stops if a named path has no index entry. [Git source](https://raw.githubusercontent.com/git/git/v2.47.1/builtin/rm.c)
    Case: normal use - One file has a modify/delete conflict while the other was deleted cleanly; the command fails and leaves the conflict unresolved.
    Gain 3, Work 1, Harm 2
    Disposition: cut - the conflict step now runs `git rm --cached --ignore-unmatch` on both paths, which keeps the removal for whichever path is still in the index and does not stop on a path already gone; `test_5` checks for `--ignore-unmatch`.

12. Advisory: Test: A local move-over test does not start without the files.
    Raise: Test
    [The plan](/plans/FORGE-GENCOMMIT-1.md:99) keeps both files on disk, but later says the fix’s test starts without them. In local mode, Forge runs the test in the existing checkout ([fasttest.py](/src/forge/fasttest.py:639)).
    Case: normal use - A local test passes using the files left on disk, without proving that a fresh checkout can regenerate them.
    Gain 3, Work 2, Harm 3
    Disposition: cut - the step now deletes the two files on disk by their two full paths and nothing else, says why that is safe (`api-types` writes both from the API code every time), then runs the repo's test command, which must pass and make both files again; the claim that the fix's test run starts without the files is removed; the git step keeps the "only these two paths, kept on disk" wording.

## Round 3

13. Advisory: Plan gap: Existing apps are told to omit files they still commit.
    Raise: Plan gap
    [The plan](/plans/FORGE-GENCOMMIT-1.md:81) says not to list the files in a part’s scope but does not exempt apps that still commit them. Its automatic move-over trigger depends on a plan read naming them as shared ([plan](/plans/FORGE-GENCOMMIT-1.md:98)).
    Case: normal use - Two parts in an unmigrated app omit the files, so Forge’s scope check cannot see that both will change them ([task.py](/src/forge/task.py:525)).
    Gain 3, Work 1, Harm 3
    Disposition: cut - `python.md` and the guide now say in one sentence that an app that still commits the two files lists both in a part's scope as today until it has moved over, so the scope check still sees the shared change; the move-over trigger is now the agent seeing the two files tracked in git (`git ls-files`) when it writes the next plan or fix for that app, then offering the fix to the owner, with no dependence on the plan read naming them; `test_5` checks both sentences.

14. Advisory: Scale: The live regression runs again for every copied Python app.
    Raise: Scale
    [The plan](/plans/FORGE-GENCOMMIT-1.md:90) puts the real fast-test regression in a helper gated only by the Python app’s `pyproject.toml`. That helper also runs for generated-feature and database-kind apps ([feature test](/tests/test_feature_command.py:381), [database test](/tests/test_database_kinds.py:260)).
    Case: normal use - A Python-starter pull request runs those smoke jobs, and each repeats the container start and API suite for the same regression. The plan estimates a few minutes per run; it has not measured them.
    Gain 3, Work 2, Harm 2
    Disposition: cut - the regression and the contract read move out of the shared `_run_live_starter` into `live_python_run`, which runs once per session and is the one place the Python starter smoke run starts the starter; the feature, database-kind and store helpers no longer run it; cost stated as one stack start and the API suite, once, in the Python starter smoke job (estimate).

## Round 4

15. Blocking: Data loss: The moved live run can remove another Docker project’s data.
    Raise: Data loss
    [The plan](/plans/FORGE-GENCOMMIT-1.md:90) moves the real run outside the helper that assigns an isolated Docker project. That helper does not return its isolated environment ([test_starter_tree.py](/tests/test_starter_tree.py:233)). The added run has no isolation specified; the starter script honors an inherited project name and removes its containers on cleanup ([test.mjs](/src/forge/templates/starter-python/scripts/test.mjs:17), [Docker documentation](https://docs.docker.com/reference/cli/docker/compose/down/)).
    Case: normal use - A developer runs the live smoke test with `COMPOSE_PROJECT_NAME` set to an existing project. The added run can remove a container and data stored in its writable layer.
    Adds work: isolate the added run’s Docker project; F 1 x H 3 = 3; 2 x C = 2.
    Gain 4, Work 2, Harm 4
    Disposition: cut - the regression now runs through an optional `after(copy, env)` argument of `_run_live_starter` that only `live_python_run` passes, inside the helper's `try`, in its own temporary copy and with its own `env` whose `COMPOSE_PROJECT_NAME` is the run's `starter-smoke-<uuid>`; it starts no second project, adds no `docker`, `down` or volume command, and the only removal is the `down` that `scripts/test.mjs` and the helper already run on that same project. The existing run has no such fault: it always sets its own project name over any inherited one (`test_starter_tree.py:233-234`).

16. Advisory: Functional: The offered fix fails when only one file is tracked.
    Raise: Functional
    [The new trigger](/plans/FORGE-GENCOMMIT-1.md:98) offers the fix if either file is tracked, but its first command names both without `--ignore-unmatch` ([plan](/plans/FORGE-GENCOMMIT-1.md:99)). Git stops when a named path is absent from the index. [Git source](https://raw.githubusercontent.com/git/git/v2.47.1/builtin/rm.c)
    Case: normal use - An app already stopped tracking one generated file; the offered fix fails before removing the other from Git.
    Gain 3, Work 1, Harm 2
    Disposition: cut - the trigger now fires when one or both files are tracked, and the main step now runs `git rm --cached --ignore-unmatch` on both paths, the same as the conflict step, so it removes whichever is still tracked and does not stop on an untracked one; the delete step needs nothing for a missing file; `test_5` checks `--ignore-unmatch` in both steps and the "one or both" trigger.

## Round 5

17. Advisory: Gate: The fast regression can replace the full run’s API report.
    Raise: Gate
    [The plan](/plans/FORGE-GENCOMMIT-1.md:83) runs the callback before the helper reads its API report ([test_starter_tree.py](/tests/test_starter_tree.py:340)). The callback’s fast run executes `test:api`, which writes that same report ([test.mjs](/src/forge/templates/starter-python/scripts/test.mjs:66), [package.json](/src/forge/templates/starter-python/package.json:14)).
    Case: normal use - If a change removes API tests from the full test command, the fast run can create a passing report afterward, so the existing smoke assertions still pass.
    Gain 3, Work 2, Harm 3
