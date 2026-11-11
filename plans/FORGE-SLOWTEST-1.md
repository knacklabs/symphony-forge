# Faster tests for repos with one combined test command

2 parts · Risks: none one-way · New moving parts: none

## What changes for you

- Some repos run all their tests through one combined script: a type check, a build, all unit tests and all browser tests, one after the other. When such a repo has no quick-test setting, Forge says so in one line when it checks the setup, when it upgrades the repo and when it adopts a live app. Forge does not write a quicker command itself. (Source: your decision, 11 Nov 2026: "Forge detects, the agent writes it")
- The guide that Forge ships tells the agent how to write the quicker command for that repo: keep every step the tests need, limit only the unit tests to the code that the change touches with the test tool's own option for that, keep the browser tests in the pull request check, run the command once to check it, ask you, then set it in a small fix. Forge never changes the setting by itself. (Source: your decision, 11 Nov 2026)
- Repos whose test command runs one test tool directly keep the suggestion that Forge prints for them today.
- On a Windows laptop, a builder's own test run skips each step of its test command that runs only browser tests. Browser tests are the tests that open the app in a real browser. Forge knows such a step when it runs Playwright or Cypress, directly or through one script of the repo. The pull request check, the final check before merge and the nightly full test run still run them. A test setting that is one combined script still runs as a whole on Windows, browser tests included, until a quicker setting with separate steps is set. On Mac and Linux, nothing changes. (Source: your decision, 11 Nov 2026; the limits are the planner's choice for you to confirm)
- When the latest full test run on the main branch fails, the board shows it under "Needs you". The row looks like the other rows there. When you click it, the run opens on GitHub. The next-step text also starts its lines with "Needs you". This is only for the full test run that Forge knows: its own nightly run, or the workflow that the repo names for its full run. Other scheduled jobs never show there. The entry stays until a later full test run passes. A run that is still going or was cancelled does not remove it. While a fix for the failure is in progress, the row says so. A repo with no full test run on GitHub shows nothing. (Source: your decision, 11 Nov 2026; when the entry goes away is the planner's choice for you to confirm)
- New repos and repos that adopted Forge on an earlier release both get these changes with the next release. Forge changes no app file and writes no setting. No model is called, so the model cost does not change.

Design: none (the failed run is one more row in the board's existing Needs you list, drawn by the same row code with the same look; no new screen, style or layout)

## Why

A client team reported this. Its Node app runs all tests through one combined script. Forge cannot choose only the related tests inside one script, so every builder test run and every pull request check ran the whole suite. The team reports that a builder's test run took about 11 minutes, and up to 24 minutes on Windows laptops. Forge did not measure these numbers. On Windows, the browser tests also failed for reasons that had no connection to the change: locked temporary folders, a browser that did not start in time, and a test database that did not start. One builder's round failed because of this. Pull request checks took 13 to 19 minutes until the team split them into groups by hand (also reported, not measured). A failed nightly run was easy to miss, because it showed as a short note only. On 11 Nov 2026 you decided to start all three improvements, and then decided that Forge only detects the combined script while the agent writes the quicker command.

## Done when

1. **For a test setting that runs one combined script and has no quick-test setting, the setup check, the upgrade and adoption print one line that says so and suggest no command; Forge writes no setting.**
2. **The guide that new and upgraded repos get tells the agent how to write, check and propose the quicker command for such a repo.**
3. **On Windows, a builder's own test run skips each separate browser-test step on every path it takes, and the pull request check, the final check and the full test run still run them.**
4. **A failed latest full test run on the main branch shows under Needs you on the board with its run link, and the next-step text marks it as Needs you; other scheduled jobs never do.**
5. **Clicking that row on the board opens the run on GitHub.**
6. **The row stays until a later full test run passes, and a fix in progress changes its words, not whether it shows.**

## Risks

<!-- Each one-way step: deleting data, a destructive migration, a new vendor. -->

Risks: none

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Source: GitHub issue 1530. The owner decisions of 11 Nov 2026 are settled; cite them, do not
reopen them: start all three improvements; then "Forge detects, the agent writes it".
Story tests use `STORY = "FORGE-SLOWTEST-1"` and one test function per Done-when number:
`test_1` to `test_6`, unique across the story's files.

### Done-when details

<!-- Under each Done-when item's number: its evidence, edge cases and the tests that prove it.
Workers and reviewers get the entries of the items they cover. An item with nothing to add has
no entry. -->

1. **What exists today.** `quicktest.suggest` (`src/forge/quicktest.py`) prints
   `Suggested quick tests in forge.toml (keep the full test command for CI):` and one
   `fast_test = "..."` line when `fast_test` is empty. `forge doctor` (`doctor.py:507`) and
   `forge upgrade` (`upgrade.py:192`) call it; `init._adopt` does not. For a combined script
   today, steps that are other scripts give kind `node-check`, so nothing is printed; a body that
   calls `vitest` directly gives kind `vitest`, and `suggest` prints
   `npm test -- --changed {base} --passWithNoTests`, which npm passes to the last step only. That
   line is wrong.

   **Detection only.** A part of the `test` setting is a combined script when it is a
   `npm|pnpm|yarn|bun [run] <script>` call whose package script body contains `&&`, `;` or `|`
   (the test `fasttest.close_tests` already uses). When `fast_test` is empty and any part of
   `test` is a combined script, `suggest` prints no `fast_test` line and prints one line, for
   example
   `The test setting runs the combined script "ci", so Forge cannot limit its tests to the change. Write a fast_test for this repo as the Forge guide says, then ask the owner.`
   Forge builds no command from the script. When no part is a combined script, `suggest` keeps
   today's output exactly; the existing cases in `tests/test_quick_test_suggestions.py` pass
   unchanged.

   **Adoption.** `init._adopt` calls `quicktest.suggest(path, cfg)` after the adoption commit,
   as `upgrade` does. Import `quicktest` inside the function: `quicktest` imports `init`. A new
   repo with no app gets nothing at init; it gets the line from the setup check once its test
   script is combined. A new starter keeps its own `fast_test`.

   **Test.** New file `tests/test_combined_script_quick_test.py`, `test_1`, parametrized:
   (a) new repo (`_new_repo` + `forge init`, then a package.json whose `ci` script is
   `npm run typecheck && npm run build && npm run test:unit && npm run test:e2e` and
   `test = "npm ci && npm run ci"`): `forge doctor` prints the line and no `fast_test =` line;
   (b) a body that calls `vitest` directly (today's wrong case): the line, no `fast_test =`;
   (c) an earlier-adopted repo (the `unsynced_up` fixture, as
   `tests/test_quick_test_suggestions.py::test_2` uses it): `forge upgrade` prints the line;
   (d) adoption of a repo with history: `forge init` prints the line. Each case asserts
   forge.toml has no `fast_test` afterwards.

2. **Guide.** `skill.md` "Adopt a live app" step 9 (the paragraph at about line 1367, "When
   `fast_test` is missing, `forge doctor` and `forge upgrade` print one suggested ...") gains the
   combined-script case: doctor, upgrade and adoption print the one line, and the agent writes
   the command. The steps for the agent, in this order: keep every step the tests need, in the
   order the script runs them, including any step that runs after the tests; limit only the
   unit-test steps to changed code with the runner's own option and `{base}` (for example
   `vitest run --changed {base}` or `jest --changedSince {base}`), noting that npm passes
   `--` options only to the last command of a script; keep the browser-test steps, because
   the pull request check runs `fast_test` too; keep setup a script runs before or after itself
   (`pre` and `post` scripts); run the command once with `{base}` set to the default branch;
   tell the owner that changed-only selection follows imports, so API tests that reach the code
   only through a URL run only in the full test run; ask the owner; set it in `forge.toml`
   through a fix. The paragraph at about line 2122 ("Compound npm scripts also keep their full
   command ...") says doctor, upgrade and adoption now name a combined script and point to step 9.

   **Test.** Same file, `test_2`: the synced skill of a new repo (`forge init`) and of an
   earlier-adopted repo after `forge upgrade` and `forge sync` carries the combined-script text
   of step 9, read from `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md`, as
   `tests/test_setup_proposes_a_fast_test.py` reads them.

3. **Which runs skip.** Only a builder's own run: bare `forge test` without `--change`,
   `--pytest` or `--full`, which `review.test_run` marks with `FORGE_WORKER_TESTS=1` for its
   child processes. Only on Windows (`os.name == "nt"`). Only a browser part: `test_parts`
   gains the kind `browser` for a Node part whose own words, or whose one-level script body,
   name `playwright` or `cypress`, name no `vitest` or `jest`, and contain no `&&`, `;` or `|`.
   A step whose script reaches Playwright through another file (for example the Python
   starter's `node scripts/test-browser.mjs`) is not recognised and still runs; the brief says so.

   **Every path agrees.** One helper in `fasttest.py`, for example `skip_browser(top, command)`,
   removes the browser parts of a command and prints once
   `On Windows this run skips the browser tests (npm run test:e2e). The pull request check, the final check and the full test run still run them.`
   It leaves `init.NODE_TEST` unchanged (that command has one runner part). It is called on the
   three paths a builder's run can take:
   - `fasttest.test`, bare run: on the command `review.close_test` returns (`fast_test` or
     `test`), before `review.test_run`.
   - `fasttest.pytest_tests` when `worker` is true: on the `test` setting it reads again, before
     its mixed-command handling. This covers `forge test --pytest {base}` inside a quick
     setting, which reads the full `test` setting again.
   - `fasttest.close_tests` when `FORGE_WORKER_TESTS` is `1`: on its command. This covers a repo
     with no `fast_test` whose `test` has Python parts.

   `fasttest.pytest_tests` also adds `browser` to the kinds it drops from a mixed command, as
   it drops `node-check` today, so Mac and Linux keep today's behaviour.
   `forge test --change` (the pull request check and close) and `forge test --full` are
   unchanged on every platform. Close in a local-test repo does not reuse the builder's pass:
   `review.passed_record` keys on the command text, and the shortened command differs.

   **What a repo with no quick setting gets.** If its `test` is a chain with a separate browser
   step, the skip applies. If its `test` is one combined script, nothing is skipped: the
   script runs whole, browser tests included, until the agent and the owner set a `fast_test`
   with separate steps (item 2). No setting turns the skip off; a builder who must run the
   browser tests on Windows runs the repo's browser script directly. Python browser tests
   (pytest-playwright) are not recognised. A failing test database in API tests is not
   addressed.

   **Brief.** `brief.md` (the paragraph at about line 165 on what bare `forge test` runs, and
   the rendered-check paragraph at about line 591) says that on Windows the builder's own run
   skips separate Playwright or Cypress steps, that a step reaching Playwright through another
   file still runs, and that the pull request check and close still run them. `skill.md` gets
   the same sentence beside its matching paragraph (about line 265).

   **Test.** New file `tests/test_windows_worker_skips_browser_tests.py`, `test_3`. The browser
   step is `npm run test:e2e`, whose script runs a fake `playwright` on `node_modules/.bin`
   (`.cmd` on Windows) that writes a marker file. Cases: (a) `fast_test` is
   `<a unit step> && npm run test:e2e`; (b) `fast_test` is
   `forge test --pytest {base} && npm run test:e2e` and `test` is
   `<pytest command> && npm run test:e2e`; (c) no `fast_test` and `test` is
   `<pytest command> && npm run test:e2e`; (d) `test` is one combined script that holds the
   browser step. For (a) to (c): bare `forge test` on Windows writes no marker and prints the
   skip line; on other platforms it writes the marker and prints no skip line;
   `forge test --change` writes the marker on every platform. For (d) the marker is written on
   every platform. New repo for all cases, plus case (a) on an earlier-adopted repo. The test
   checks its own platform with `sys.platform` and does not import forge. Its Windows branch
   runs in the Windows test job (nightly and before release).

4. **What exists today.** `board_facts.failed_schedules(top)` reads the newest 100 scheduled
   runs of all workflows plus the manual runs of `full_suite_workflow` or `forge.yml` on the
   default branch (cached ten minutes in `schedule-cache`; logs cached per attempt for ever).
   Per workflow it keeps the newest run (`latest.setdefault`) and reports it when its conclusion
   is `failure`. `nextstep._failed_schedules` prints `The latest scheduled <workflow> (<file>)
   run on <branch> failed in: ...`, `Failing tests: ...` and `Next: forge fix start ...`;
   `claim` shows those lines above a started fix whose `why` names the cleaned `(<file>)` key.
   The board's Needs you lists only stories, parts and fixes.

   **What changes.**
   - Which workflow counts: the full test run Forge knows, which is `full_suite_workflow` when
     set, else `forge.yml` when `repo.test_place(cfg) == "ci"` (the generated workflow has its
     nightly job only then), else none. `failed_schedules` marks each entry with
     `full_run: true` when the run's file is that workflow. The row is found by this mark, not
     by position in the shared list: the request for that workflow's own runs
     (`actions/workflows/<file>/runs`, today limited to `event=workflow_dispatch`) drops the
     event filter, so it returns that workflow's scheduled and manual runs and other frequent
     jobs cannot push its newest result out; merge it with the all-workflow list by run id.
     Only `full_run` entries become Needs you entries and get the `Needs you: ` prefix in
     `forge next`. Other scheduled workflows keep today's `forge next` lines, with no prefix and
     no board entry.
   - Each entry also carries the run's `html_url` and `created_at`. Add `url`, `created_at`
     and `full_run` outside the per-attempt cache (`read`), because those cached entries never
     expire. A `schedule-cache` value from an earlier release, whose entries lack `full_run`,
     is treated as stale and read again.
   - `board_facts.team` adds one entry per `full_run` failure: `id` `run:<file>`, `kind` `run`,
     `reason` `failed run`, `title` `The latest full test run on <branch> failed`, `detail` the
     failed jobs, `since` the run's `created_at`, `url` the run page. It sorts with the others,
     oldest first, and counts in `team.sentence`.
   - `nextstep._failed_schedules`: the first line of a `full_run` alert starts with
     `Needs you: `, whether a fix claims it or not. `nextstep.py` has 1,197 lines; this change
     adds at most three. Do not touch `board.py` (1,200 lines).
   - `run-reference.md` lists the `failed run` reason, the `run` kind and `url` under
     `team.needs_you`. The pane (`mod/hooks/summary.ts`) shows an entry with an unknown id by its
     title and reason, so it needs no change.

   **Test.** New file `tests/test_failed_nightly_needs_you.py`, `test_4`, on the gh fakes of
   `tests/test_next_names_a_failed_scheduled_run.py`. A failed latest `forge.yml` scheduled run
   in a CI-test repo: `forge board --json` has the entry in `team.needs_you` with the run's
   `url`, and `forge next` prints `Needs you: The latest scheduled ...`. A failed scheduled run
   of another workflow: today's `forge next` lines with no prefix, and no entry. A local-test
   repo with no `full_suite_workflow`: no entry. A repo whose `full_suite_workflow` names a
   workflow: its failure gives the entry. New repo, plus one earlier-adopted repo
   (`tests/fixtures/adopted-v1.2.2`). Update the exact-line assertions in
   `test_next_names_a_failed_scheduled_run.py::test_1` only if its runs become `full_run`.

5. **The click.** `board_app/now.js`: the Me view keeps `run` entries (they have no owner). The
   existing `ask()` draws a `run` entry with its existing markup and classes (`button.ask`,
   `ask-head`, `verb`, `key`, `ask-title`), with the verb `Fix` (a `VERB` entry) and, in the
   `key` place, `Full test run`. Only the click differs: it opens `url` in a new tab
   (`window.open(url, '_blank', 'noopener')`) in place of the item drawer. No CSS change, no new
   screen or layout, no command on the page. This keeps `Design: none` true; a change that needs
   new styling stops and goes back to the coordinator for a design first.

   **Test.** New file `tests/test_failed_run_row_opens_run.py`, `test_5`, in the real-Chrome
   board harness of `tests/test_board_now_screen.py` (its `BROWSER` script pattern and the
   `client` and `live` fixtures from `tests/test_board_server.py`; only `gh` is faked). With a
   failed `forge.yml` run, the Needs you strip shows the row, and a click opens a new page at the
   run's `url` (route `https://github.com/**` to a stub reply so the test stays offline). New
   repo; the earlier-adopted case is in `test_4`, because the page draws the same JSON.

6. **When the row goes away.** `failed_schedules` keeps, per workflow, the newest run whose
   conclusion is `success` or `failure`; a run that is in progress, cancelled or skipped does
   not replace an earlier result. So the row goes only when a later run of the same workflow
   passes. This also changes `forge next` for every scheduled workflow: a newer unfinished run
   no longer hides a failure.

   **A fix in progress changes the words.** In `team`, a fix row on the board whose state is not
   `done` (the board's own derived state, so a merged fix counts as done) and whose saved `why`
   (from `best`) contains the same cleaned `(<file>)` key that `claim` matches (build it with
   `nextstep._failed_schedules`'s `clean`, so a name such as `nightly@2am.yml` still matches)
   puts `Fix in progress` in the row's `key` place, in place of `Full test run`. The title
   stays, so the short words fit the existing one-line row. The entry stays either way.
   `forge next` keeps today's `claim` placement, with the prefix.

   **Test.** `tests/test_failed_nightly_needs_you.py`, `test_6`: a failed run, then a newer
   in-progress run, then a newer cancelled run: the entry stays. After `forge fix start` with
   the suggested `why`: the entry stays and is marked as a fix in progress. After that fix
   merges and the next run fails again: the entry stays, not marked. A newer passing run: no
   entry and no `Needs you:` line. New repo, plus one earlier-adopted repo.

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
| QUICK | Name combined test scripts, guide the agent, and skip browser steps on Windows | The combined-script line in `suggest` with no suggested command; adoption calls `suggest`; the agent's steps in the guide; the `browser` part kind; one skip helper called on the three paths of a builder's own run on Windows; `browser` in the pytest picker's dropped kinds; the brief text. | 1, 2, 3 | `src/forge/quicktest.py`, `src/forge/fasttest.py`, `src/forge/init.py`, `src/forge/templates/skill.md`, `src/forge/templates/brief.md`, `tests/test_combined_script_quick_test.py`, `tests/test_windows_worker_skips_browser_tests.py` | `tests/test_combined_script_quick_test.py` (`test_1`, `test_2`, new); `tests/test_windows_worker_skips_browser_tests.py` (`test_3`, new) | | no | |
| NIGHTLY | A failed full test run shows under Needs you | `full_run`, `url` and `created_at` on `failed_schedules` entries; the full run's own runs request without the event filter; the newest finished run decides; stale old cache; one Needs you entry per failed full test run, with the fix-in-progress label; the `Needs you: ` prefix in `forge next`; the row drawn by the existing row code, whose click opens the run; the run reference text. | 4, 5, 6 | `src/forge/board_facts.py`, `src/forge/nextstep.py`, `src/forge/board_app/now.js`, `src/forge/templates/run-reference.md`, `tests/test_failed_nightly_needs_you.py`, `tests/test_failed_run_row_opens_run.py`, `tests/test_next_names_a_failed_scheduled_run.py` | `tests/test_failed_nightly_needs_you.py` (`test_4`, `test_6`, new); `tests/test_failed_run_row_opens_run.py` (`test_5`, new); `tests/test_next_names_a_failed_scheduled_run.py` (`test_1`, only if its line text changes) | | yes | |

New moving parts: none

## Notes

- **Owner decisions (11 Nov 2026, settled).** First: start all three: (1) doctor, init and adoption see a combined test script with no `fast_test` and propose one; the agent asks the owner, then sets it through a fix; (2) heavy browser tests stay out of the builder's local test loop on Windows by default, and CI still runs them; (3) a failed nightly full run shows under Needs you on the board and in `forge next`. Then, after read round 2: "Forge detects, the agent writes it". Forge only names the combined script; the shipped guide tells the agent how to write the command. The step-rewriting rule and its tests are removed. The existing exact suggestions for single-runner scripts stay as they are.
- **Finding that shapes points 1 and 2.** The pull request check runs `fast_test` too: the generated tests job runs `forge test --change`, and `review.close_test` returns `fast_test` for it, the same command the builder's bare `forge test` runs. A `fast_test` without the browser step would remove browser tests from every pull request check and contradict the rendered-check rule (`brief.md` about line 591). So the guide tells the agent to keep the browser step, and only the builder's own run on Windows skips it.
- **Planner's choices, written into the plan, for the owner to confirm at approval.**
  1. Browser tests: only a builder's own run on Windows skips separate browser steps. Other options: skip on every platform (faster Mac loops, but a builder who changes a screen learns of a browser failure only at the pull request check); or have the agent leave the step out of the quick command (pull request checks would stop running browser tests).
  2. A repo with no quick setting whose test setting is one combined script gets no skip on Windows until the agent and the owner set a command with separate steps.
  3. Forge knows a browser step only when it names Playwright or Cypress directly or in one package script; a step that reaches them through another file still runs.
  4. The Needs you row is only for the full test run Forge knows, stays until a later run of it passes, and shows a fix in progress in its label.
- **Design: none.** The NIGHTLY row uses the existing row code (`ask()` in `now.js`) with the same markup and classes and no CSS change; only its click target and its short label differ. If the builder finds the row needs new styling, the part stops and the coordinator makes the design first.
- **Scores (F x H >= 2 x C).**
  - Naming a combined script in one line: F 2, H 2 (a slow loop no one notices; a wrong suggestion today), C 1 (about 15 lines). 4 >= 2. Kept.
  - Windows skip on the three paths: F 3 (every builder test run on Windows in such a repo), H 2 (failed rounds for unrelated reasons), C 1 (one helper, three calls, about 20 lines). 6 >= 2. Kept.
  - Needs you entry and its click: F 1 to 2, H 2, C 2. Close; it stays because the owner decided it.
  - Newest finished run decides, and the full run's own request: F 2 (each night a run is in progress for an hour; frequent jobs fill the shared list), H 2 (a failure disappears), C 1. 4 >= 2. Kept.
  - Recognising browser steps that go through another file: F 1, H 2, C 2. 2 < 4. Left out; the limit is stated.
  - A setting that keeps browser tests in the Windows builder run: F 1, H 1, C 3. Left out.
  - A failed local full run (repos without CI) under Needs you: F 1, H 2, C 2. 2 < 4. Left out; that run prints its fix line when it fails.
- **New and existing repos.** Point 1: new repos get the line from the setup check once their test script is combined, and the guide text at init; adopted repos get the line at adoption, on upgrade and from the setup check, and the guide text through upgrade and sync. Points 2 and 3 work for both after the upgrade, with no setting and no sync step. Forge changes no app file and writes no setting.
- **No new command or setting.** The line reuses `quicktest.suggest` and its callers; the skip reuses the builder's bare `forge test` and the existing `FORGE_WORKER_TESTS` mark; the board reuses `team.needs_you` and `failed_schedules`.
- **The coordinator guide for point 3.** NIGHTLY changes no step the coordinator takes: it already starts the fix that `forge next` names for a failed run, and `skill.md` about lines 2103 and 2411 stay true. So NIGHTLY does not edit `skill.md`, and the two parts share no file and can run at once.
- **Files near their limits.** `src/forge/nextstep.py` has 1,197 lines (limit 1,200): NIGHTLY adds at most three. `src/forge/board.py` has 1,200 lines: no part touches it; the board change lives in `board_facts.py` (617 lines).
- **Guides in flight.** Other parts in flight also edit `src/forge/templates/skill.md` and `brief.md`. Forge makes overlapping parts wait, so QUICK may wait for them. Keep the guide edits to the named paragraphs.
- **Not verified.**
  - The 11 to 24 minute and 13 to 19 minute numbers are reported by the client team, not measured by Forge. The speed gain of a quick command is unknown until a repo uses one.
  - The client's exact script is not known; the agent writes its command with the owner.
  - Changed-only selection (`vitest --changed`, `jest --changedSince`) follows imports. API tests that reach the code only through a URL are not selected in the pull request check; the full test run covers them. The guide tells the agent to say this to the owner.
  - The Windows causes (locked temporary folders, browser start-up timeouts, the test database) come from the report. Only browser steps are skipped; a database failure in API tests is not addressed.
  - Whether `test_next_names_a_failed_scheduled_run.py`'s fake runs count as `full_run` (their files are named `forge-next-<n>.yml`, not `forge.yml`) was not checked by running it; if they do not, its lines keep today's text.
