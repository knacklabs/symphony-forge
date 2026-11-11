---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-11T10:33:21.823703+00:00
seconds: 495.137
read_hash: 6405351f655dfe78dc32990fe52fc46ad5157bf6
round: 1
passed: no
doc_seen: 6405351f655dfe78dc32990fe52fc46ad5157bf6
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1ca23-d19c-7f91-abac-ec3333a0b580
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

1. Blocking: Not done: the suggestion can drop a second unit-test step.  
   Raise: Not done  
   Case: normal use - A combined script runs separate Vitest suites for an API and a web app.  
   The plan says to reuse the existing per-kind logic, but [quicktest.py](/src/forge/quicktest.py:91) skips a second runner of the same kind. The [starter package](/src/forge/templates/starter/package.json:14) has two such suites. One would disappear from the suggested command and, if accepted, the pull request check.  
   Gain 4, Work 2, Harm 3
   Disposition: cut - the suggestion no longer reuses the per-kind path for a combined script; every Vitest or Jest step of the script gets the changed option, a second step of the same kind included (Done-when 1, test_1).

2. Blocking: Not done: expanding an npm script loses effects of the original invocation.  
   Raise: Not done  
   Case: normal use - `npm test` has a `pretest` setup script, or `npm test -- --coverage` forwards a coverage option to its last step.  
   The [plan](/plans/FORGE-SLOWTEST-1.md:65) replaces the invocation with only its script body. npm also runs `pretest` and `posttest`, as its [local documentation](/opt/homebrew/lib/node_modules/npm/docs/content/using-npm/scripts.md:200) shows; the replacement also leaves out arguments supplied on the original invocation. The suggested command can therefore omit setup or coverage checks.  
   Gain 4, Work 2, Harm 3
   Disposition: cut - Forge suggests a line only when the invocation has no extra words, the combined script has no pre or post script, and every step is a bare call of another package script, so each step runs as the same command line with its own hooks; otherwise it prints why and suggests nothing (Done-when 1 and 2).

3. Blocking: Not done: the reported combined script still runs browser tests on Windows until a quick setting is accepted.  
   Raise: Not done  
   Case: normal use - A repo has `npm run ci` as its combined test script and has no `fast_test` yet.  
   [review.py](/src/forge/review.py:368) uses the original test setting in that case. The [plan](/plans/FORGE-SLOWTEST-1.md:125) says the Windows skip handles only separate parts and leaves a combined script whole. That contradicts the promised Windows builder run for the case that prompted the story.  
   Gain 4, Work 2, Harm 3
   Disposition: cut - the promise is now exact: a builder's own run on Windows skips separate browser steps only; a test setting that is one combined script still runs whole, browser tests included, until a setting with separate steps is set, and the plan says so to the owner (Done-when 3).

4. Blocking: Not done: the Python picker can start the browser tests that the Windows run just skipped.  
   Raise: Not done  
   Case: normal use - A Python API and a browser suite use `test = "pytest && npm run test:e2e"` and a quick setting containing `forge test --pytest {base} && npm run test:e2e`.  
   The outer run can remove the browser part, but [pytest_tests](/src/forge/fasttest.py:697) reads the full test setting again. It drops Node parts only when it also finds Vitest or Jest. The [planned change](/plans/FORGE-SLOWTEST-1.md:129) adds `browser` to that same conditional list, so this Python-and-browser command still runs the browser suite.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - one skip helper runs on all three paths of a builder's own run on Windows: the bare forge test command, the pytest picker's reread test setting, and close_tests; test_3 covers the Python-and-browser cases.

5. Blocking: Unproven: item 3: the generated Node wrapper survives the suggestion.  
   Raise: Test  
   Case: normal use - A new repo accepts the suggestion generated from Forge’s default Node test setting.  
   [quicktest.py](/src/forge/quicktest.py:44) unwraps only the exact original setting. An expanded suggestion has a different wrapped command, so its last script name retains the closing parenthesis when split. The [Windows test](/plans/FORGE-SLOWTEST-1.md:142) uses an unwrapped setting and can pass while the browser step in the generated suggestion is not recognized.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - the new combined-script suggestion is never wrapped in the generated Node wrapper (it is printed only when package.json exists), and the Windows skip leaves the wrapper command unchanged.

6. Blocking: Not done: unrelated scheduled workflows would appear as failed nightly tests.  
   Raise: Not done  
   Case: normal use - A repo has a failed weekly maintenance workflow and no nightly test run.  
   [failed_schedules](/src/forge/board_facts.py:406) reads scheduled runs across all workflows. The [plan](/plans/FORGE-SLOWTEST-1.md:162) adds each failure as a “nightly” row, so this repo would show an entry despite the promise that a repo with no nightly run shows none.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - only the full test run Forge knows (full_suite_workflow, else forge.yml in a CI-test repo) gives a Needs you entry and the Needs you prefix; other scheduled workflows keep today's next lines and never show on the board (Done-when 4, test_4).

7. Blocking: Not done: a failed-run entry can disappear before another run passes.  
   Raise: Not done  
   Case: normal use - The next nightly run starts while the previous one is still failed.  
   [failed_schedules](/src/forge/board_facts.py:429) picks the newest run before checking its conclusion. Once its cache refreshes, an in-progress or cancelled run hides the earlier failure. The [plan](/plans/FORGE-SLOWTEST-1.md:191) tests a passing run but not this state.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - per workflow, the newest run whose conclusion is success or failure decides; an in-progress, cancelled or skipped run never removes the entry (Done-when 6, test_6).

8. Blocking: Unproven: item 4: a merged fix can keep hiding later failures.  
   Raise: Test  
   Case: normal use - A fix for a failed run merges, then the same workflow fails again.  
   The [plan](/plans/FORGE-SLOWTEST-1.md:162) identifies claiming fixes through `best`. The board determines that a fix is merged separately when it [derives its row](/src/forge/board.py:381); the stored state in `best` can still say `ready`. The proposed test stops after starting a fix, so it would pass if that old fix suppressed every later failure.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - a fix never hides the entry; a fix whose board state is not done only changes the row's words, and test_6 covers a merged fix followed by a new failure (Done-when 6).

9. Blocking: Unproven: item 4: the board link is never exercised.  
   Raise: Test  
   Case: normal use - A person clicks a failed-run row on the board.  
   The [planned test](/plans/FORGE-SLOWTEST-1.md:183) checks JSON and next-step text only. The existing [row handler](/src/forge/board_app/now.js:127) opens an item drawer, so those assertions can all pass while clicking the new row never opens the run on GitHub.  
   Gain 3, Work 2, Harm 3
   Disposition: cut - Done-when 5 and test_5 in the real-Chrome board harness of tests/test_board_now_screen.py click the row and check that a new page opens at the run's url; the board JSON entry carries url (test_4).

10. Blocking: Gate: the three new tests use the same story test number.  
    Raise: Gate  
    Case: normal use - Both parts add the tests named in their task rows.  
    The [plan](/plans/FORGE-SLOWTEST-1.md:217) names all three new tests `test_1`. [test_rules.py](/tests/test_rules.py:26) requires test numbers to be unique across a story, so the required repository check would fail.  
    Gain 4, Work 1, Harm 2
    Disposition: cut - each Done-when has its own test number, test_1 to test_6, unique across the story's files.
