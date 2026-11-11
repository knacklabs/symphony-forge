# Faster tests for repos with one combined test command

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- Some repos run all their tests through one combined script: a type check, a build, all unit tests and all browser tests, one after the other. For such a repo, Forge now suggests a quicker test setting. Forge builds it only from the steps the script already has. The steps stay the same, except that unit tests run only for the code that the change touches. Forge prints the suggestion when it checks the setup, when it upgrades a repo and when it adopts a live app. The agent asks you, then sets it in a small fix. Forge never changes the setting by itself. (Source: your decision, 11 Nov 2026)
- When the script has no unit-test step that Forge can limit this way, Forge says so in one line and suggests nothing. (Source: your decision, 11 Nov 2026)
- On a Windows laptop, a builder's own test run skips the browser tests. Browser tests are the tests that open the app in a real browser. The pull request check and the nightly full test run still run them. On Mac and Linux, nothing changes. (Source: your decision, 11 Nov 2026)
- When the latest nightly test run on the main branch fails, the board shows it under "Needs you", with a link to the run on GitHub. The next-step text also starts its lines with "Needs you". The entry goes away when a fix for that run starts, or when the next run passes. A repo with no nightly run shows nothing. (Source: your decision, 11 Nov 2026; when the entry goes away is the planner's choice)
- New repos and repos that adopted Forge on an earlier release both get these changes with the next release. Forge changes no app file. The quicker test setting comes only through the fix that you agree to.
- No model is called for any of this. The model cost does not change.

## Why

A client team reported this. Its Node app runs all tests through one combined script. Forge cannot choose only the related tests inside one script, so every builder test run and every pull request check ran the whole suite. The team reports that a builder's test run took about 11 minutes, and up to 24 minutes on Windows laptops. Forge did not measure these numbers. On Windows, the browser tests also failed for reasons that had no connection to the change: locked temporary folders, a browser that did not start in time, and a test database that did not start. One builder's round failed because of this. Pull request checks took 13 to 19 minutes until the team split them into groups by hand (also reported, not measured). A failed nightly run was easy to miss, because it showed as a short note only. On 11 Nov 2026 you decided to start all three improvements.

## Done when

1. **For a repo whose test setting runs one combined script with a Vitest or Jest step, the setup check, the upgrade and adoption print a suggested quick-test line made of the script's own steps, with only the unit-test steps limited to changed code; Forge writes no setting.**
2. **When the combined script has no step Forge can limit, the setup check says so in one line and suggests nothing.**
3. **On Windows, a builder's own test run skips the browser-test steps of the test setting and says so; the pull request check, close and the nightly full run still run them.**
4. **A failed latest nightly run on the main branch shows under Needs you on the board with a link to the run, and the next-step text marks its lines as Needs you.**
5. **That entry goes away when a fix for the run starts or the next run passes, and a repo with no nightly run shows none.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Source: GitHub issue 1530. The owner decision of 11 Nov 2026 is settled; cite it, do not reopen it.

### Done-when details

<!-- Under each Done-when item's number: its evidence, edge cases and the tests that prove it.
Workers and reviewers get the entries of the items they cover. An item with nothing to add has
no entry. -->

1. **What exists today.** `quicktest.suggest` (`src/forge/quicktest.py`) already prints
   `Suggested quick tests in forge.toml (keep the full test command for CI):` and one
   `fast_test = "..."` line when `fast_test` is empty. `forge doctor` (`doctor.py:507`) and
   `forge upgrade` (`upgrade.py:192`) call it. `forge init` adoption (`init._adopt`) does not.
   `quicktest.test_parts` splits the forge.toml command on `&&` and reads a `npm|pnpm|yarn|bun
   [run] <script>` part's package script one level deep (`runner_words`). For a combined script
   it fails in two ways:
   - Script steps are other scripts (`"ci": "npm run typecheck && npm run build && npm run test:api && npm run test:e2e"`):
     the part is classified `node-check`, so `suggest` prints nothing. This is the reported
     "doctor does not suggest a fast_test".
   - Script steps call a runner directly (`"test": "tsc --noEmit && vitest run && playwright test"`):
     the part is classified `vitest`, and `suggest` prints `npm test -- --changed {base} --passWithNoTests`.
     npm appends those flags to the last step (`playwright test`), so the line is wrong.
     `fasttest.close_tests` already guards this case at run time (the `&&|[;|]` check on the
     script body: "Compound scripts forward npm arguments to the last command"); `suggest` does
     not.

   **The rule.** A part is a combined script when its package script body contains `&&`, the
   same test `close_tests` uses. `suggest` replaces that part with the body's own `&&` steps,
   one level deep:
   - A step that names another package script (`npm run x`, `pnpm x`, `yarn x`, `bun run x`)
     stays as written.
   - A step that runs a tool directly gets the package manager's runner prefix: `npx` for npm,
     `pnpm exec`, `yarn`, `bunx`.
   - Then the existing per-kind logic runs on the expanded chain: a Vitest or Jest step whose
     own script is a single command gets `--changed {base}` or `--changedSince {base}` and
     `--passWithNoTests` (with npm's ` --` passthrough as today). A Vitest or Jest step whose
     own script is itself combined stays unchanged (same guard as `close_tests`, now also in
     `suggest`). Every other step (type check, build, browser tests, lint) stays unchanged.
   - Setup parts before it (`npm ci`) and Forge's Node wrapper (`init.NODE_TEST`) stay, as
     today.

   Expected output for the first example with `test = "npm ci && npm run ci"`:
   `fast_test = "npm ci && npm run typecheck && npm run build && npm run test:api -- --changed {base} --passWithNoTests && npm run test:e2e"`.
   For the second example with `test = "npm ci && npm test"`:
   `fast_test = "npm ci && npx tsc --noEmit && npx vitest run --changed {base} --passWithNoTests && npx playwright test"`.

   **Adoption.** `init._adopt` calls `quicktest.suggest(path, cfg)` after it writes the
   adoption commit, as `upgrade` does. Import `quicktest` inside the function:
   `quicktest` imports `init` at module level. A new repo with no app (`forge init` with no
   history) gets nothing at init, because it has no script yet; it gets the suggestion from the
   setup check once its test script becomes combined. A new starter keeps its own `fast_test`.

   **Guide.** `skill.md` "Adopt a live app" step 9 (the paragraph at about line 1367, "When
   `fast_test` is missing, `forge doctor` and `forge upgrade` print one suggested ...") gains the
   combined-script case and adoption. It tells the agent to tell the owner one thing before
   agreeing: changed-only selection follows imports, so API tests that reach the code only through
   a URL run only in the nightly full run. The paragraph at about line 2122 ("Compound npm scripts
   also keep their full command ...") says that doctor, upgrade and adoption now suggest a
   `fast_test` built from the script's steps. The existing "Once the human agrees, set it in
   `forge.toml` through a fix" stays the only way the setting changes.

   **Test.** New file `tests/test_combined_script_quick_test.py`, one rule, `test_1`,
   parametrized: (a) new repo (`_new_repo` + `forge init`, then a `package.json` with the
   first example) where `forge doctor` prints the expected line; (b) the second example, which
   today prints the wrong line; (c) earlier-adopted repo (the `unsynced_up` fixture from
   `tests/test_upgrade_command.py`, as `test_quick_test_suggestions.py::test_2` uses it) where
   `forge upgrade` prints it; (d) adoption of a repo with history, where `forge init` prints it;
   (e) the item 2 case. Every case asserts that forge.toml has no `fast_test` afterwards. The
   existing cases in `tests/test_quick_test_suggestions.py` must still pass unchanged.

2. A combined script whose expanded steps hold no Vitest or Jest step (for example
   `tsc && mocha && playwright test`), or whose body uses `;`, `|` or `||`, or a step that starts
   with an environment setting (`NAME=value ...`): `suggest` prints one line and no
   `fast_test`, for example `The test command runs one combined script with no Vitest or Jest
   step that Forge can limit to changed tests, so Forge suggests no fast_test.` Proven by case
   (e) of the same test.

3. **The rule.** `test_parts` gains one kind, `browser`: a Node part whose own words or
   one-level script name `playwright` or `cypress`, and no `vitest` or `jest`. Bare `forge test`
   (the builder's own run: `fasttest.test` with neither `--change` nor `--pytest`) on Windows
   (`os.name == "nt"`) removes the `browser` parts from the command that `review.close_test`
   returns, before `review.test_run`, and prints one line, for example
   `On Windows this run skips the browser tests (npm run test:e2e). The pull request check, close and the nightly full run still run them.`
   Keep `init.NODE_TEST`'s wrapper when the command has it, as `suggest` does.
   - `forge test --change` (the pull request check and close) and `forge test --full` (the
     nightly run) are unchanged on every platform.
   - The skip works on separate `&&` parts only. A single combined script that holds the browser
     tests still runs whole; the suggestion from item 1 is what splits it. Say so in the guide.
   - Close in a local-test repo does not reuse the builder's pass: `review.passed_record` keys
     on the command text, and the shortened command differs.
   - `fasttest.pytest_tests` drops `node-check` parts from a mixed command; add `browser` to the
     same list so the pytest picker does not start browser tests either.
   - Python browser tests (pytest-playwright) are not recognised. A failing embedded database in
     API tests is not covered; only browser steps are skipped.
   - No setting turns the skip off. A builder who must run the browser tests on Windows runs the
     repo's own browser script directly.

   **Brief.** `brief.md` (the paragraph at about line 165 on what bare `forge test` runs, and the
   rendered-check paragraph at about line 591, "Close runs the browser tests only when ...")
   says that on Windows the builder's own run skips the browser steps and that close and the pull
   request check still run them. `skill.md` gets the same sentence beside its matching paragraph
   (about line 265).

   **Test.** New file `tests/test_windows_worker_skips_browser_tests.py`, `test_1`: a client
   repo whose `fast_test` is `<a unit step> && npm run test:e2e`, with `test:e2e` naming a fake
   `playwright` (a script on `node_modules/.bin`, `.cmd` on Windows) that writes a marker file.
   Bare `forge test`: on Windows the marker is absent and the skip line is printed; on other
   platforms the marker is present and no skip line is printed. `forge test --change` writes the
   marker on every platform. Cases on a new repo and on one earlier-adopted repo. The test checks
   its own platform with `sys.platform`; it does not import forge. The Windows branch runs in the
   Windows test job (nightly and before release).

4. **What exists today.** `board_facts.failed_schedules(top)` reads the newest scheduled runs
   and manual full runs on the default branch (cached ten minutes, logs cached per attempt) and
   returns each workflow whose latest run failed. `nextstep._failed_schedules` turns them into
   `The latest scheduled <workflow> (<file>) run on <branch> failed in: ...`, `Failing tests: ...`
   and a `Next: forge fix start ...` line. A started fix whose `why` names `(<file>)` claims the
   alert and shows it above its own lines (`claim` in `nextstep._report`). The board's Needs you
   (`board_facts.needs_you`, called from `board_facts.team`) lists only stories, parts and fixes.

   **The change.**
   - `board_facts.failed_schedules` adds the run's `html_url` and `created_at` to each entry.
     Add them outside the per-attempt cache (`read`), because cached entries never expire.
   - `board_facts.team` adds one Needs you entry per failed run that no unfinished fix claims
     (the same rule as `claim`: a fix in `best` that is not merged, done or dropped and whose
     `why` contains `(<file>)`): `id` `run:<file>`, `kind` `run`, `reason` `failed run`,
     `title` `The nightly <workflow> run on <branch> failed`, `detail` the failed jobs,
     `since` the run's `created_at`, `url` the run page. It sorts with the others, oldest
     first, and counts in `team.sentence`.
   - `nextstep`: the first line of an unclaimed alert starts with `Needs you: `. Claimed alerts
     keep today's text. `nextstep.py` has 1,197 lines; this change must add no more than three.
     Do not touch `board.py` (1,200 lines).
   - `board_app/now.js`: the Me view keeps `run` entries (no owner), and `ask()` renders a `run`
     entry as a link to `url` that opens a new tab, with the verb `Fix` and the label `Nightly
     run` in place of the key. Use the existing `.ask` look; add to `now.css` only what an anchor
     needs to match the button. No new screen, no command on the page.
   - `run-reference.md` lists the new `failed run` reason and the `run` kind under
     `team.needs_you`. The pane (`mod/hooks/summary.ts`) already shows an entry with an unknown id
     by its title and reason, so it needs no change.

   **Test.** New file `tests/test_failed_nightly_needs_you.py`, `test_1`, built on the fakes of
   `tests/test_next_names_a_failed_scheduled_run.py`: with a failed latest scheduled run,
   `forge board --json` (or `forge next --json`) has the entry in `team.needs_you` with the
   link, and `forge next` prints `Needs you: The latest scheduled ...`. New repo and one
   earlier-adopted repo (`tests/fixtures/adopted-v1.2.2`, as the existing test does). Update
   the exact-line assertions of `test_next_names_a_failed_scheduled_run.py::test_1` for the
   prefix.

5. The same `test_1` continues: after `forge fix start` with the suggested `why`, the entry is
   gone from `team.needs_you` and `forge next` prints today's claimed lines with no prefix;
   with a passing latest run, there is no entry; with no scheduled runs, there is no entry and no
   line.

## Tasks

<!-- One row per task. Covers: the Done-when numbers it delivers, at most three. Scope: the paths
it may change. Before writing each Scope, search the code for the files the task needs. The plan
check refuses two tasks whose Scope paths have the same prefix up to the first wildcard, unless
one waits for the other through After, directly or through another task; it names both tasks.
Paths with a segment named `tests`, `test`, `__tests__` or `spec` do not cause Scope overlaps
and can be shared without an After link. Explicit After links still apply.
When tasks need the same production file, put it in the first task's Scope with the shared names and stubs;
tasks that need them wait for that task through After and then own only their files. Tests: the
tests it adds or changes. After: the tasks it waits for. When two tasks share a function, field,
file format or command, the first task pins it: it commits the shared names and stubs plus one
test that crosses both sides, and the tasks that use it list it under After. Split tasks so each
owns its files; shared lines (command table, guide list, registry) go to one task or a small last
wiring task; After only when a task needs another task's code. The
Developer column is optional: the lead fills or changes a GitHub username here, below For the
builders, without another approval. Leave it blank for an unassigned part. Forge next uses
the caller's GitHub login; another developer may start it with a warning. Existing tables
without Developer still work. The moving-parts line stays last: "none", or each new dependency, service, datastore,
queue, background job or abstraction layer, with the Done-when item that needs it. -->

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| QUICK | Quick tests for combined scripts and the Windows browser skip | `suggest` expands a combined package script into its own steps and limits only its Vitest or Jest steps; the one-line "nothing to limit" case; the same guard on combined runner scripts; adoption prints the suggestion; the `browser` part kind; bare `forge test` on Windows skips browser parts with one line; the pytest picker drops browser parts; the guide and brief text. | 1, 2, 3 | `src/forge/quicktest.py`, `src/forge/fasttest.py`, `src/forge/init.py`, `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `tests/test_combined_script_quick_test.py`, `tests/test_windows_worker_skips_browser_tests.py` | `tests/test_combined_script_quick_test.py` (`test_1`, new); `tests/test_windows_worker_skips_browser_tests.py` (`test_1`, new) | | no | |
| NIGHTLY | A failed nightly run shows under Needs you | The run link and date in `failed_schedules`; one Needs you entry per unclaimed failed run in `team`; the `Needs you: ` prefix in `forge next`; the board row as a link; the `failed run` reason in the run reference. | 4, 5 | `src/forge/board_facts.py`, `src/forge/nextstep.py`, `src/forge/board_app/now.js`, `src/forge/board_app/now.css`, `src/forge/templates/run-reference.md`, `tests/test_failed_nightly_needs_you.py`, `tests/test_next_names_a_failed_scheduled_run.py` | `tests/test_failed_nightly_needs_you.py` (`test_1`, new); `tests/test_next_names_a_failed_scheduled_run.py` (`test_1`, line text updated) | | yes | |

New moving parts: none

## Notes

- **Owner decision (11 Nov 2026, settled).** Start all three: (1) doctor, init and adoption see a combined test script with no `fast_test` and propose one; the agent asks the owner, then sets it through a fix; (2) heavy browser tests stay out of the builder's local test loop on Windows by default, and CI still runs them; (3) a failed nightly full run shows under Needs you on the board and in `forge next`.
- **Finding that changes point 1 and point 2.** The pull request check runs `fast_test` too: the generated workflow's tests job runs `forge test --change`, and `review.close_test` returns `fast_test` (with `{base}`) for it, the same command the builder's bare `forge test` runs. So a `fast_test` that leaves the browser tests out also removes them from every pull request check, and only the nightly run would catch a browser failure, after merge. It would also contradict the brief's rendered-check rule (`brief.md` about line 591: close runs browser tests only when the close command includes them). This is why the plan keeps the browser steps in the suggested line and skips them only in the builder's own run, which `fasttest.test` can tell apart (`--change` absent).
- **Open questions for the owner, recommendation first.**
  1. Where should browser tests run? **Recommended: the suggested line keeps the browser step; Forge skips it only in a builder's own run on Windows.** The pull request check and the nightly run keep running it, and Mac and Linux builders still see browser failures before the pull request. Option B: skip it in a builder's own run on every platform (the same code without the Windows condition; faster loops on Mac too, but a builder who changes a screen sees a browser failure only at the pull request check, which costs a round). Option C: leave the browser step out of the suggested line (no skip code; pull request checks then stop running browser tests, and failures show only in the nightly run after merge).
  2. When does the Needs you entry go away? **Recommended: when a fix for that run starts, or when the next run passes.** The coordinator already starts that fix without asking (`skill.md` about line 2411), and the fix then shows as work in progress. Option B: keep it until the next run passes, even while a fix is building; the owner then sees "needs you" when nothing waits on them.
  3. Should the suggestion drop the build step? **Recommended: no, keep every step except the unit tests.** Browser tests often need the build, and Forge cannot tell. The agent and the owner can remove a step before the fix.
- **Scores (F x H >= 2 x C).**
  - Suggestion for combined scripts: F 2, H 2 (slow loops; a wrong suggestion today), C 2 (about 40 lines). 4 >= 4. Kept.
  - Windows skip of browser parts: F 3 (every builder test run on Windows in such a repo), H 2 (failed rounds for unrelated reasons), C 1 (about 15 lines). 6 >= 2. Kept.
  - Needs you entry: F 1 to 2, H 2, C 2 (about 40 lines across Python and the page). Close; it stays because the owner decided it.
  - Hiding the entry while a claiming fix is open: F 2, H 1, C 1. 2 >= 2. Kept.
  - A setting that keeps browser tests in the Windows builder run: F 1, H 1, C 3 (a new setting). Left out; the builder can run the browser script directly.
  - A failed local full run (repos without CI, `forge test --full`) under Needs you: F 1, H 2, C 2. 2 < 4. Left out; that run already prints its fix line when it fails.
- **New and existing repos.** Point 1: new repos get the suggestion from the setup check once their script is combined; adopted repos get it at adoption, on upgrade and from the setup check. Point 2 and point 3 work for both after the upgrade, with no setting and no sync step; point 2 needs the suggested line, or another `fast_test` or `test` made of separate `&&` parts. Forge changes no app file and writes no setting.
- **No new command or setting.** The suggestion reuses `quicktest.suggest` and its callers; the skip reuses bare `forge test`; the board reuses `team.needs_you` and `failed_schedules`.
- **The coordinator guide for point 3.** NIGHTLY changes no step the coordinator takes: it already starts the fix that `forge next` names for a failed run, and the lines at `skill.md` about lines 2103 and 2411 stay true. So NIGHTLY does not edit `skill.md`, and the two parts share no file and can run at once.
- **Files near their limits.** `src/forge/nextstep.py` has 1,197 lines (limit 1,200): NIGHTLY may add at most three. `src/forge/board.py` has 1,200 lines: no part touches it; the board change lives in `board_facts.py` (617 lines).
- **Guides in flight.** Other parts in flight also edit `src/forge/templates/skill.md` and `brief.md`. Forge makes overlapping parts wait, so QUICK may wait for them. Keep the guide edits to the named paragraphs.
- **Not verified.**
  - The 11 to 24 minute and 13 to 19 minute numbers are reported by the client team, not measured by Forge. The speed gain of the suggested line is unknown until a repo uses it.
  - The client's exact script shape is not known. The plan covers steps that name other scripts and steps that call tools directly, one level deep.
  - Changed-only selection (`vitest --changed`, `jest --changedSince`) follows imports. API tests that reach the code only through a URL are not selected in the pull request check; the nightly run covers them. The guide tells the agent to say this to the owner.
  - The Windows causes (locked temporary folders, browser start-up timeouts, the test database) come from the report. Only the browser steps are skipped; a database failure in API tests is not addressed.
  - The board row as a link was not drawn or checked on screen; NIGHTLY's builder checks it on the running board at 1440 width, light and dark.
