---
reader: codex (gpt-6.1-sol)
read_at: 2026-11-06T12:35:21.445498+00:00
seconds: 324.951
read_hash: b7c0a633b8b25e5fe54d4e09d4e9f9449944f1d7
round: 1
passed: no
doc_seen: b7c0a633b8b25e5fe54d4e09d4e9f9449944f1d7
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1b0d6-4f00-7690-80bf-f7883b7fb782
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

1. Blocking: Not done: item 1 omits the Python starter’s web lint and type checks.
   Raise: Not done.
   Case: normal use - a pull request changes a TypeScript file in a Python starter’s web app.
   `plans/FORGE-AFFECTED-1.md:68` selects Vitest and browser tests for this path but names no ESLint or TypeScript check. Those checks currently run through `src/forge/templates/starter-python/package.json:11-17`. The proposed selection can therefore pass a web change without the lint and typecheck that item 1 promises.
   Gain 4, Work 2, Harm 3
   Disposition: cut - the Python starter's web part now lists ESLint on changed files and the `tsc --build` of its tsconfigs next to vitest and the browser suite, and its API part lists ruff, mypy, `api-types` and import-linter (plan: How a change picks its tests; Done-when 2; `test_6`).

2. Blocking: Not done: item 1 runs library tests twice when their consuming web project is affected.
   Raise: Not done.
   Case: normal use - a change touches `libs/shared/util`.
   `plans/FORGE-AFFECTED-1.md:68` adds library test targets while making the web test target wrap today’s `test:hooks` command. That command uses `apps/web/vitest.config.ts:17`, which includes every library test. The web project depends on shared utilities through `libs/core/web/package.json:15`, so both targets run the same utility tests. A web-only change also runs unrelated library tests.
   Gain 4, Work 2, Harm 3
   Disposition: cut - test targets are now disjoint: the web app's target runs only `apps/web/src`, each library with tests has its own target, and the web vitest glob stays for the full run, so no test file is named by two targets (plan: TypeScript starter; `test_5`).

3. Blocking: Plan gap: the promised Nx-first selection has no implementation rule for existing workspaces.
   Raise: Plan gap.
   Case: normal use - an existing workspace defines Nx targets but its configured test command invokes pytest or Vitest directly.
   `plans/FORGE-AFFECTED-1.md:79` explicitly requires this repo to use Nx. However, SPLIT’s algorithm at line 67 only dispatches individual runners; its task row at line 111 defines no Nx detection or target mapping. Current `src/forge/fasttest.py:270-305` and `src/forge/quicktest.py:23-57` provide neither. The builder must invent how this required path works.
   Gain 4, Work 2, Harm 3
   Disposition: cut - SPLIT gets an `nx` step kind: an `nx run-many`/`nx affected -t X` step becomes `nx affected -t X --base=<merge base>` when `nx show projects --with-target X` names a project, else it runs whole; a direct runner step in an Nx workspace keeps its runner's selection (plan: Nx in an existing workspace; `test_1` Nx cases).

4. Blocking: Unproven: item 1 never exercises the starter’s selected execution path.
   Raise: Test.
   Case: normal use - CI runs `node scripts/test.mjs <merge-base>`.
   `plans/FORGE-AFFECTED-1.md:86` checks the selector separately with a fixed Nx response, then runs the full script without a base. The existing live command at `tests/test_starter_tree.py:232-234` also supplies no base. Every planned assertion could pass while `test.mjs` ignores its base argument and always runs everything.
   Gain 4, Work 2, Harm 3
   Disposition: cut - `scripts/test.mjs --list <base>` prints the commands the selected path would run, from the same code as a real run, and `test_5` and `test_6` run it with a base; the live case now runs `node scripts/test.mjs <base>` on a one-file change.

5. Blocking: Plan gap: upgrading cannot preserve forge.toml byte-for-byte in the upgraded worktree.
   Raise: Plan gap.
   Case: normal use - an earlier-adopted repo upgrades to the release carrying this change.
   `plans/FORGE-AFFECTED-1.md:75`, `:79` and `:86` require an unchanged `forge.toml` after upgrade and sync, while expecting the generated workflow’s version pin to change. `src/forge/upgrade.py:145-151` deliberately changes `forge.toml`’s version before sync. The proof must distinguish that required pin change from preservation of the app’s test settings.
   Gain 4, Work 1, Harm 2
   Disposition: cut - the proofs now say `forge.toml` differs from before only in its `version` line, and `forge.yml` only in its version pin.

6. Blocking: Trap: skipping the selection job can also skip every nightly smoke job.
   Raise: Plan gap.
   Case: normal use - the nightly schedule or a manual workflow run starts.
   `plans/FORGE-AFFECTED-1.md:69` limits selection to pull requests but adds `needs: select` to every smoke job. GitHub skips jobs whose required job was skipped unless their condition explicitly handles that status; an event-only condition does not establish this. [GitHub documents this dependency behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idneeds). The script-only schedule case at plan line 83 cannot detect the workflow skipping all jobs.
   Gain 4, Work 1, Harm 3
   Disposition: cut - the `select` job has no `if:` and runs on every event (`--all` off a pull request); each smoke job has `needs: select` and an `if:` that reads only the select outputs; `test_4` reads the workflow text for both and runs `--all` (plan: OWN, Done-when 4 (c)).

7. Advisory: Plan gap: the promised suggestion for an existing starter’s opaque script is undefined.
   Raise: Plan gap.
   `plans/FORGE-AFFECTED-1.md:92` says doctor and upgrade print a suggested fast command for an earlier starter using `node scripts/test.mjs`. Current `src/forge/quicktest.py:89-90` prints nothing for that command, and SPLIT only adds Playwright recognition. An earlier script also lacks the new base argument. The plan defines neither a runnable suggestion for that script nor its detection.
   Gain 3, Work 2, Harm 2
   Disposition: cut - the promised doctor and upgrade suggestion for an opaque script is removed; existing starters get the recipe in the guide and the agent asks first.

8. Advisory: STARTERS waits for SPLIT only because they share documentation lines.
   Raise: Plan gap.
   `plans/FORGE-AFFECTED-1.md:114` explicitly gives shared edits to `skill.md` and `docs/guide.md` as the reason for this dependency. STARTERS names no code contract supplied by SPLIT. Assign both documentation edits to STARTERS and remove the documentation-only dependency.
   Gain 2, Work 1, Harm 1
   Disposition: cut - the dependency is gone: each part edits its own guide paragraph, so the parts build at the same time.

9. Advisory: Split: STARTERS → TypeScript starter selection and Python starter selection.
   Raise: Plan gap.
   `plans/FORGE-AFFECTED-1.md:114` already estimates 450 changed lines outside tests, exceeding the requested roughly 400-line task boundary. Its split waits until 500 lines, although the task already combines two selection implementations and their test-script changes.
   Gain 3, Work 2, Harm 2
   Disposition: cut - the starters are now two parts, STARTERS_TS and STARTERS_PY, each under about 350 lines.
