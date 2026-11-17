---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-17T13:44:37.837949+00:00
seconds: 859.103
read_hash: f227639f9434c06b68db289bf83095b80013cbf7
round: 2
passed: yes
doc_seen: f227639f9434c06b68db289bf83095b80013cbf7
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 5de3d342ca7dfe2dce7ea6b31d0add199352fac4
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1e9a5-ba42-7df2-a8f1-79526a848260
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

1. Blocking: Not done: TypeScript pull requests can skip browser tests.
   Raise: Not done. Case: normal use - A web change runs the affected projects’ `test` targets, but the browser suite is a separate `e2e` target. The current script runs it explicitly; the planned `--step test` does not. The proposed test also keeps the existing browser assertion on the unpartitioned command. [Plan](/plans/FORGE-FASTCI-1.md:108), [web targets](/src/forge/templates/starter/apps/web/project.json:10), [current script](/src/forge/templates/starter/scripts/test.mjs:80).
   Gain 4, Work 2, Harm 3
   Disposition: cut - fixed: the TypeScript `--step test` also runs `web:e2e` when web is affected, and the starter test asserts it

2. Blocking: Not done: Python’s separate lint job lacks the types it must use.
   Raise: Not done. Case: normal use - Each pull-request job starts from its own clean checkout. The planned lint step does not generate API types, while the type-check step does; those generated files are ignored by Git, and the contracts import them. Type-aware lint therefore lacks resolved types. The full starter smoke generates them before lint and would miss this. [Plan](/plans/FORGE-FASTCI-1.md:109), [ignored files](/src/forge/templates/starter-python/.gitignore:12), [contract import](/src/forge/templates/starter-python/libs/auth/contracts/src/index.ts:2), [Oxlint’s type-aware linting documentation](https://oxc.rs/docs/guide/usage/linter/type-aware.html).
   Gain 4, Work 2, Harm 3
   Disposition: cut - fixed: the Python `lint` and `build` steps run `api-types` first, and the test asserts `api-types` comes before the linter

3. Blocking: Not done: The first upgrade to this release does not print the new suggestions.
   Raise: Not done. Case: normal use - A client runs `forge upgrade` using its installed older release. That release executes the planned suggestion call before installing the new release. Its subsequent new-release `sync` and `close` calls do not invoke the new function. [Plan](/plans/FORGE-FASTCI-1.md:110), [upgrade sequence](/src/forge/upgrade.py:194), [sync](/src/forge/sync.py:713).
   Gain 4, Work 2, Harm 3
   Disposition: cut - fixed: the suggestions print from doctor and from sync (which the first upgrade runs from the new release), not from `upgrade.py`; the test checks doctor and sync

4. Blocking: Unproven: item 3: A documentation-only pull request can pass without the four checks.
   Raise: Test. Case: normal use - The existing grouped workflow skips its test matrix for documentation-only changes and lets the required check pass; `forge test --change` also skips them. The plan retains that gate and tests its dependencies, but does not cover this case against the promise that all four checks pass. [Workflow](/src/forge/prcheck.py:82), [gate](/src/forge/prcheck.py:113), [test runner](/src/forge/review.py:405).
   Gain 4, Work 2, Harm 2
   Disposition: cut - fixed: item 3 and What changes for you say a docs-only change skips the four checks as today; the step-jobs test asserts the docs-only condition and gate pass are kept

5. Blocking: Plan gap: The TypeScript 7 task cannot pass its required Python starter test unchanged.
   Raise: Plan gap. Case: normal use - The new package aliases start with `npm:`, but the existing Python starter test requires every dependency version to contain only digits and dots. The plan requires that test to stay unchanged and leaves it outside the task’s scope. [Plan](/plans/FORGE-FASTCI-1.md:133), [existing assertion](/tests/test_python_starter.py:108).
   Gain 4, Work 1, Harm 2
   Disposition: cut - fixed: `tests/test_python_starter.py` is in the TS7 scope, and its version check accepts exactly the two TypeScript aliases

6. Blocking: Plan gap: The Oxlint task leaves affected tests outside its scope.
   Raise: Plan gap. Case: normal use - A newly created TypeScript app no longer has `eslint.config.mjs`, but the feature-removal test opens that file and expects its old guide text. The standards test also requires `ESLint` in the stack page that the plan changes to Oxlint. Neither test file is in the task’s scope. [Feature-removal test](/tests/test_feature_remove.py:151), [standards test](/tests/test_standards.py:112), [task scope](/plans/FORGE-FASTCI-1.md:155).
   Gain 4, Work 1, Harm 2
   Disposition: cut - fixed: `tests/test_feature_remove.py` and `tests/test_standards.py` are in the OXLINT scope, with what each must expect

7. Blocking: Not done: Common TypeScript version ranges receive no suggestion.
   Raise: Not done. Case: normal use - An app with `"typescript": "^5.9.3"` uses an older compiler, but its version does not start with a number, so the planned detection skips it. A caret is npm’s default prefix. The proposed test uses only an exact version. [Plan](/plans/FORGE-FASTCI-1.md:111), [npm configuration](https://docs.npmjs.com/cli/v11/using-npm/config/#save-prefix).
   Gain 3, Work 1, Harm 3
   Disposition: cut - fixed: the TypeScript check reads the major after a leading `^`, `~`, `>=`, `>`, `=` or `v`, and the test uses `^5.9.3`

8. Blocking: Unproven: item 3: Python’s separate steps may run unrelated checks.
   Raise: Test. Case: normal use - For a web-only change, the existing selector excludes Python API tests and Ruff. The proposed step tests check that `--step lint` lists lint commands and `--step test` lists tests, but they would still pass if those steps also ran the unrelated API checks. The existing exclusion assertions exercise only the command without `--step`. [Current cases](/tests/test_affected_py_starter.py:38), [planned tests](/plans/FORGE-FASTCI-1.md:141).
   Gain 3, Work 2, Harm 3
   Disposition: cut - fixed: each Python step only filters today's selection, and the test runs every case under every step with its absent commands still absent

9. Blocking: Not done: Upgrade cannot leave the generated workflow unchanged.
   Raise: Not done. Case: normal use - An existing app upgrades Forge without accepting separate checks. The plan says its workflow file does not change, but upgrade runs the new release’s sync, and the generated workflow includes the Forge version. The plan also says upgrade changes no file, while the same upgrade must write the new guide. [Promise](/plans/FORGE-FASTCI-1.md:10), [upgrade](/src/forge/upgrade.py:220), [workflow template](/src/forge/prcheck.py:44).
   Gain 4, Work 1, Harm 2
   Disposition: cut - fixed: the promise now says the workflow keeps its one tests job and only the release number changes, and that printing the lines changes no file; item 4 says the checks name each change without making it

10. Advisory: The public guide will describe the old starter checks.
    Raise: Functional. A developer reading the guide after this change will see that the Python starter uses ESLint and that the workflow has one tests job. The plan updates the shipped agent guide but leaves this page outside the tasks’ scopes. [Public guide](/docs/guide.md:541), [tasks](/plans/FORGE-FASTCI-1.md:149).
    Gain 2, Work 1, Harm 1
   Disposition: keep - below the bar (live with)

## Round 2

11. Advisory: Not done: The TypeScript build check runs lint again for shared changes.
    Raise: Not done. A change to `package.json` selects the full build path. The plan runs `scripts/test-build.mjs` there, but that script runs lint after its builds. The separate lint check therefore does not remove lint from the build check’s critical path. The proposed `--list` test sees the wrapper command, not the lint inside it. [Plan](/plans/FORGE-FASTCI-1.md:108), [build script](/src/forge/templates/starter/scripts/test-build.mjs:18).
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

12. Advisory: Plan gap: The React plugin is both global and limited to web overrides.
    Raise: Plan gap. The settings list `react` among the root plugins, while the custom-rule instructions say to enable it only in web-source overrides. Root plugins also apply outside those overrides, so a builder cannot follow both instructions as written. [Plan](/plans/FORGE-FASTCI-1.md:118), [Oxlint configuration reference](https://oxc.rs/docs/guide/usage/linter/config-file-reference.html).
    Gain 3, Work 1, Harm 2
   Disposition: keep - below the bar (follow-up)

13. Advisory: A repo already using TypeScript 7 can receive the older-compiler suggestion.
    Raise: Functional. The amended rule treats `>=5` as an older TypeScript version, but that range also permits version 7. A repo using version 7 directly, without `@typescript/native`, would be told to replace its compiler. [Plan](/plans/FORGE-FASTCI-1.md:111), [npm version ranges](https://github.com/npm/node-semver#ranges).
    Adds work: check the resolved compiler for open-ended ranges; F 2 x H 1 = 2; 2 x C = 4.
    Gain 2, Work 2, Harm 1
   Disposition: keep - below the bar (live with)

14. Advisory: Not done: The separate-check suggestion can be suppressed while CI still uses one job.
    Raise: Not done. If `test` contains `{step}` but `fast_test` does not, the planned suggestion is suppressed. Pull requests use `fast_test` when it exists, so the workflow still has no step jobs. [Suggestion rule](/plans/FORGE-FASTCI-1.md:113), [pull-request command selection](/src/forge/quicktest.py:13).
    Gain 3, Work 1, Harm 2
   Disposition: keep - below the bar (follow-up)

15. Advisory: Unproven: item 3: A starter switched to local tests can retain a CI documentation job.
    Raise: Test. With `{step}` and one group, the plan keeps the multi-job template. The current local-test removal chooses where to start deleting by the group count, so it would leave `docs-check` behind. The existing local-workflow test has no `{step}`, and the new step test uses CI tests. [Plan](/plans/FORGE-FASTCI-1.md:105), [removal logic](/src/forge/prcheck.py:458), [existing test](/tests/test_testplace_workflow.py:113).
    Adds work: cover a starter switched from CI to local tests; F 2 x H 1 = 2; 2 x C = 2.
    Gain 2, Work 1, Harm 1
   Disposition: keep - below the bar (live with)
