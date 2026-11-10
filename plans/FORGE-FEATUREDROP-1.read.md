---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-10T17:49:02.372733+00:00
seconds: 726.353
read_hash: 1ef34e5d50e90f1a5ebeecfaf2deaef68b02f417
round: 1
passed: no
doc_seen: 1ef34e5d50e90f1a5ebeecfaf2deaef68b02f417
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1c688-ccdd-7ac1-8f0f-d13c2a9f3269
session:
loop_choice:
loop_reason:
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

1. Blocking: Security: The removal option does not preserve feature-name validation.
   Raise: Security. [The plan](/plans/FORGE-FEATUREDROP-1.md:60) branches to removal without specifying validation of the plural name. [The existing build command](/src/forge/feature.py:96) validates both names together, but removal has no singular name. Without a separate check, `../apps` can make `libs/<plural>` point at the app directory.
   Case: normal use - a removal command receives an invalid name containing a path.
   Adds work: validate the removal name before selecting files; F 1 x H 3 = 3; 2 x C = 2.
   Gain 4, Work 1, Harm 4
   Disposition: cut the check validates the plural with the build command's name pattern before it builds any path, and refuses `../apps` with the same message; test_1 covers it

2. Blocking: Not done: Removing the Python starter’s example feature breaks its retained model.
   Raise: Not done. [The plan](/plans/FORGE-FEATUREDROP-1.md:68) keeps `models.py` but deletes `schema.py`. The starter’s [projects model](/src/forge/templates/starter-python/apps/api/app/projects/models.py:17) imports `ProjectStatus` from that schema file. The retained database setup therefore cannot import the model. The planned live test removes generated clients and jobs, leaving projects in place.
   Case: normal use - a team removes the starter’s projects feature.
   Gain 4, Work 2, Harm 4
   Disposition: cut Forge no longer deletes any file; the guide's Python list keeps `models.py` and every file in the module that it imports (the starter's `projects` imports `ProjectStatus` from `schema.py`), and the check scans none of the kept module

3. Blocking: Not done: The check skips feature calls inside the database tests.
   Raise: Not done. [The plan](/plans/FORGE-FEATUREDROP-1.md:65) skips the retained data-layer files in full. The TypeScript [database test](/src/forge/templates/starter/apps/api/test/database.e2e-spec.ts:22) and Python [schema test](/src/forge/templates/starter-python/apps/api/tests/test_module_schemas.py:41) both call the projects API as well as checking retained tables. After projects is removed, those calls are neither listed nor usable, so the database tests fail.
   Case: normal use - a team removes projects and cleans every listed leftover.
   Gain 4, Work 2, Harm 3
   Disposition: cut the database test files are no longer skipped; only the Prisma folder, the migrations and the kept Python module are, so the projects calls in those tests are listed, and the guide tells the agent to change them; test_3 plants such a call

4. Blocking: Not done: A feature can use another feature without an import the check recognizes.
   Raise: Not done. [The users check](/plans/FORGE-FEATUREDROP-1.md:63) looks for package or Python module imports. The shipped [frontend guidance](/src/forge/templates/conventions/frontend.md:58) also shows calls such as ``api.post(`/orders/${id}/cancel`)``. A jobs screen can call clients this way without importing its package; removal then proceeds instead of stopping before changes. The specified leftover tokens also do not identify that dynamic relative URL.
   Case: normal use - one feature’s screen calls another feature’s API.
   Gain 4, Work 2, Harm 3
   Disposition: cut a use is now any match of the same patterns inside another module's folder, so a call by web address such as `api.get('/clients')` is found like an import; test_2 has a jobs file that calls the route and imports nothing

5. Blocking: Plan gap: The Python check has no defined removed state that keeps the data model.
   Raise: Plan gap. [CHECK](/plans/FORGE-FEATUREDROP-1.md:116) stops while the feature folder exists, but the [data rule](/plans/FORGE-FEATUREDROP-1.md:68) keeps `apps/api/app/<module>/` with `models.py` and `__init__.py`. The plan does not say whether the absent contracts folder or the retained Python folder determines that removal is complete. Its hand-removal test deletes the folders instead of exercising the required retained model.
   Case: normal use - an agent removes a Python feature by hand and runs CHECK again.
   Gain 3, Work 2, Harm 3
   Disposition: cut the removed state is defined: no `libs/<plural>/`, no generated test file, and in Python no `routes.py`, `service.py`, `tools.py` or `permissions.py`; the kept `models.py` and one-line `__init__.py` do not count; test_1 does the guide's list with the kept layer in place

6. Blocking: Not done: The non-starter instructions send the agent back to a command that always refuses.
   Raise: Not done. [The starter check](/plans/FORGE-FEATUREDROP-1.md:62) refuses whenever both starter markers are absent, while [the guide](/plans/FORGE-FEATUREDROP-1.md:88) says to run that same command after manual removal as the check. Removing a feature by hand does not add either marker.
   Case: normal use - an adopted app without a starter removes a feature.
   Gain 3, Work 1, Harm 3
   Disposition: cut the guide runs the check only in a starter app; in any other app it says to search for the feature's name and run the app's own build and tests, so it never sends the agent to a refusal

7. Blocking: Plan gap: The check has no rule for finding the feature’s singular name.
   Raise: Plan gap. [Removal](/plans/FORGE-FEATUREDROP-1.md:60) accepts only the plural, while the [leftover check](/plans/FORGE-FEATUREDROP-1.md:65) must find the singular Prisma accessor. [Feature generation](/src/forge/feature_schema.py:21) takes that name independently: `people --one person` produces `prisma.person`. The plan does not say how removal obtains `person`, and its test uses only regular pairs such as clients/client.
   Case: normal use - a feature has an irregular singular name.
   Gain 3, Work 2, Harm 3
   Disposition: cut the check takes only the plural and reads the model name from the kept Prisma schema file; Python needs no singular; test_1 builds `people --one person`

8. Blocking: Not done: The later-drop guidance omits the required two-release wait.
   Raise: Not done. [The plan](/plans/FORGE-FEATUREDROP-1.md:84) permits the later migration after the previous release is gone. The [database rule](/src/forge/templates/skills/database/SKILL.md:54) also requires keeping the old table for two releases. The planned guide can therefore direct a drop before the required wait is over.
   Case: normal use - a person requests table deletion after the feature-removal release.
   Gain 3, Work 1, Harm 4
   Disposition: cut the guide adds no drop rule and points to the database skill's migration rule (two releases, Contract line) as it is

9. Blocking: Plan gap: The backup order makes the later migration impossible to follow as written.
   Raise: Plan gap. [The plan](/plans/FORGE-FEATUREDROP-1.md:32) requires the backup before the drop step, and [its builder detail](/plans/FORGE-FEATUREDROP-1.md:84) puts it before writing the migration. [Mainline’s documented backup](/src/forge/templates/conventions/deploy.md:108) happens at Promote when the release already contains a migration.
   Case: normal use - the first migration after feature removal is the requested table drop.
   Gain 3, Work 1, Harm 4
   Disposition: cut the guide adds no backup order and points to the deploy guide's existing backup rule as it is

10. Blocking: Test: The live removal test is not assigned to both starter jobs.
    Raise: Test. [The plan](/plans/FORGE-FEATUREDROP-1.md:56) says to name the new test file in the smoke list, but [the current jobs](/scripts/smoke_select.py:8) have separate file lists and opposing Python filters. Adding it only to the TypeScript job satisfies that instruction while never running the Python removal against a live app.
    Case: normal use - the removal change runs in the starter smoke workflow.
    Gain 3, Work 1, Harm 3
   Disposition: cut no live test remains: the check and the guide tests read files only, so no smoke list changes; the missing live proof of the guide's list is stated as a trade-off and as unverified

11. Blocking: Plan gap: The two parts share the removal module without a pinned handoff.
    Raise: Plan gap. [The task table](/plans/FORGE-FEATUREDROP-1.md:116) gives both parts `feature_remove.py`, but CHECK names no deletion callable, stub, or test crossing that boundary. REMOVE is also directed to edit the first part’s file, contrary to the [shared-file rule](/src/forge/templates/skill.md:1382).
    Case: normal use - REMOVE starts after CHECK merges.
    Gain 4, Work 2, Harm 2
   Disposition: cut the second part is cut; one task owns the check module and the other owns only the guide texts, with no shared file

12. Advisory: Plan gap: Both parts rewrite the same guide text.
    Raise: Plan gap. [Both task scopes](/plans/FORGE-FEATUREDROP-1.md:116) include the skill, brief, guide and synced copies solely to change the removal wording between parts. Give the shared text to one part or a small final wiring part.
    Gain 2, Work 2, Harm 1
   Disposition: cut the shared guide text is now owned by one task

13. Advisory: Test: The new argument refusals have no planned command-level test.
    Raise: Test. [The plan](/plans/FORGE-FEATUREDROP-1.md:60) makes `--one` and `--field` optional in the parser and specifies new refusal messages, but its tests do not exercise missing build arguments or those arguments combined with `--remove`. The existing [build handler](/src/forge/feature.py:96) assumes the singular name is present.
    Gain 3, Work 1, Harm 2
   Disposition: cut the check is a separate command, so the build command's arguments do not change and need no new refusal test
