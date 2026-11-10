# Close shows what a changed screen looks like

2 parts · Risks: none one-way · New moving parts: one small script that Forge copies into every client app; it runs inside the browser tests the app already has

## What changes for you

- When a client UI change closes, the app's own browser test step opens each changed screen at desktop and phone width, in light and dark, and in its loaded, empty, loading and error states. Forge gives the agent a ready-made check. The agent adds one short test for each screen it builds or changes. The browser and the tools are the ones the app already has.
- Close reports four kinds of problem: sideways overflow, cut text, low contrast and layout jumps. Each report names the screen, the width, the theme and the state. A screen with no problem gets one line that says so. A screen the change does not touch is skipped, and the report says so.
- A problem stops close, as a failed test does today. One screen can set aside one kind of problem if it gives a reason. The refusal shows how.
- Close makes no model call for this. A model looks at the saved pictures only before a demo or before sign-off, one model call each time. This costs tokens: see Risks.
- The check adds about 5 to 10 seconds for each checked screen. This is an estimate and nobody has measured it. It runs where the app's browser tests run: on the laptop at close, or in the pull request check when the repo uses GitHub's checks.
- A new client repo gets the check, the agent's steps and the review rule when it starts. An existing client repo gets the same when it upgrades and refreshes its Forge files. No app file changes. The existing repo's first rendered check comes with the next change to a screen. An old, untouched screen is not backfilled.
- A prototype marked as sample-data has no tests before sign-off, so it runs no rendered check then. The check starts with the first tests after sign-off.

Design: none (this story adds no screen and changes none; Forge ships a check and rules, not screens; owner rule, 31 Oct 2026)

## Why

Close checks only read code, so a screen that overflows at phone width, cuts text, fails contrast in dark mode or breaks in its error state can close and reach the client unseen. The design canvas pictures merged on 6 Nov 2026 cover only design canvases at two widths, not built screens in their states.

## Done when

1. **A UI change that closes lists its rendered problems for each changed screen, by width, theme and state, or says that none were found. A screen the change does not touch is skipped.**
2. **Overflow, cut text, low contrast and layout jumps are each named with the screen, width, theme and state where they occur. A problem stops close. One screen can set aside one kind of problem with a written reason.**
3. **A new client repo gets the check and its rules when it starts. An existing client repo gets them when it refreshes its Forge files after the upgrade, with no app file changed, and the check first runs on its next change to a screen.**
4. **Close makes no model call for the check. The guide says a model looks at the saved pictures only before a demo or sign-off.**
5. **A sample-data prototype runs no rendered check before sign-off. The check starts with its first tests.**

## Risks

Risks: none one-way. Each part reverts with its pull request. Nothing is deleted and no data changes. The story adds no new package: the app already installs its browser tool and its contrast tool.

An accepted decision from 5 August 2026 says no browser is added to Forge's own tools or to a client repo, so that a page's width can be proven without one. That decision was about the board page in Forge's own tests. It also said that a real need for rendered checks would be a new decision with a named user. This story does not put a browser in Forge's own tools, and it adds no package to a client repo. The client starter has installed a browser test tool since 27 Sep 2026, after that decision, and no decision records the change. This story runs the check inside that tool and records a new decision in the same change. If you want Forge itself to start a browser at close, that is a different story, and it reverses the decision.

Trade-off: the agent writes one short test for each screen. Forge cannot see a screen that has no test. The review reports a changed screen with no rendered check as a serious finding, so a later step catches the miss. An app with no browser test tool gets no check and keeps today's rules.

Trade-off: dark mode follows the browser's colour-scheme setting, as the starter's theme file does. An app whose dark mode ignores that setting shows its light colours twice, and the check says nothing about it. The saved pictures show it to the model before a demo.

Trade-off: the empty, loading and error states are made by answering the screen's own data requests with an empty answer, no answer, or a server error. The agent lists those requests for each screen. A screen that shows its states in another way needs the agent to list a request that produces them.

Trade-off: when the pull request check has no known base, it checks every screen, not only the changed ones. A repo with many screens then pays more time there. Close on the laptop always knows the base.

Trade-off: a layout jump or cut text can be a design choice (a table cell that ends in "..." for example). The check reports it, and the screen can set it aside with a reason. The planner chose this way out.

Model cost: close adds no model call. The look at the pictures is one model call before a demo and one before sign-off. Each call reads pictures, which cost more than text. The plan limits it to the loaded state at both widths and both themes for each demo screen (4 pictures a screen), plus any picture where the check found a problem. A prototype with 10 demo screens reads about 40 pictures. This size is an estimate and nobody has measured it.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Rules for every part. No new `forge` command, no new setting, no new package and no screen. Nothing under `src/forge/templates/starter` or `src/forge/templates/starter-python` changes: the review reports a screen, page, route table or app shell added there as P1. `close.py` is at its 1,200-line ceiling (`test_5_forge_stays_small`) and does not change.

Each new test file starts with `STORY = "FORGE-RENDER-1"`. Tests run the forge command and never import forge. There is one test per Done-when number, so the numbers stay unique across the files: `test_1` and `test_2` in `tests/test_render_check.py`, `test_3`, `test_4` and `test_5` in `tests/test_render_words.py`. Each is parametrized with a new client case (`forge init`) and an earlier-adopted case (`tests/fixtures/adopted-v1.2.2/client` and `forge sync`, as `tests/test_canvas_phone_viewport.py` does). Before a round ends, run the two cheap checks from AGENTS.md.

### What exists (evidence)

Checked in this worktree on 10 Nov 2026. A part checks each name again before it starts.

- Design checks that read source only. `src/forge/templates/design/ui-checks.js` (98 lines) reads `.tsx`, `.jsx`, `.html`, `.css`, `.vue` and `.svelte` text and runs impeccable's checker on files. It starts no browser and needs no running app. `src/forge/ui_checks.py` (37 lines) runs it for `app_baseline.check` (called at `src/forge/close.py:280`) and, through `ships(top, cfg)`, writes `.forge/design/ui-checks.js` to every client repo. `sync.ships` (`src/forge/sync.py:379`, loop at `:444-450`) finds every module that defines `ships(top, cfg)`, and `init` merges the same result (`src/forge/init.py:456`), so a second file in the `ui_checks.ships` dictionary reaches new and adopted repos with no other wiring. `tests/test_setup.py:55-56` (`LISTED`) and `tests/test_split_ships.py:35-36` list the shipped paths.
- Canvas pictures (merged 6 Nov 2026). `src/forge/templates/design/support.js` (148 lines) draws each canvas `.html` file at 1440 by 900 and 375 by 900 through Chrome's own protocol (`capture`), waits for `document.fonts.ready` and for animations to finish (at most 1 second), and fails when `Math.max(documentElement.scrollWidth, body.scrollWidth) > innerWidth` at 375. It opens `file://` pages with no server and uses no Playwright. The new check reuses its two widths, its settle wait and its overflow measure. It cannot reuse the file: a built screen needs the running app, a sign-in and API answers, and Playwright already offers those.
- The browser tool in client apps. `@playwright/test` 1.64.0 and `@axe-core/playwright` 4.10.2 are root dependencies of both starters (`src/forge/templates/starter/package.json:60-61`, `starter-python/package.json:42-43`). `apps/web/playwright.config.ts` has `testDir: './e2e'`, `retries: 0`, `workers: 2` and `fullyParallel`, so a new spec file in `apps/web/e2e/` runs with no config change. `src/forge/templates/starter/scripts/test.mjs` installs Chromium and runs `web:e2e` whenever the web app is affected. `init` sets `fast_test = "node scripts/test.mjs {base}"` (`src/forge/init.py:231`). `src/forge/templates/starter/apps/web/e2e/served-app.spec.ts` already runs axe for serious and critical violations on the built page. The starter's theme file follows `prefers-color-scheme` and toggles `dark` on the `html` element (`libs/shared/ui/src/components/theme-provider.tsx:16-19`). `test-results/` is in the starter's `.gitignore`.
- How close runs tests and what it shows. `review.close_test` (`src/forge/review.py:363`) picks the command and computes the merge base; `review.test_run` (`:385`) runs it, prints the last 30 lines, every failed test name and the full log path. With `sample_data = true`, `repo._sample_settings` (`src/forge/repo.py:665`) blanks `test`, `fast_test` and `checks`, and `test_run` returns "Sample-data mode skips tests and CI." (`review.py:402`). `review.py` has 1,193 lines.
- Where the rules for workers and review live. `src/forge/templates/brief.md:440-467` (design rules and the `pendingScreens` line), `src/forge/templates/review.md:324-336` (`Gate: UI check` and `Gate: UI standards`), `src/forge/templates/skill.md:800-860` (canvas paragraph and the pre-demo step), `src/forge/templates/conventions/testing.md:58-90` (Browser tests, with the line "do not backfill untouched flows"), `docs/guide.md`.
- The accepted decision. `docs/decisions/0027-responsive-proof-without-a-browser.md` (accepted 2026-08-05, story PH-4). Decision: "No browser dependency is added to the harness or to any client repo." It rejects a headless browser in the board's tests as heavier than the other shapes it forbids, and says rendered assertions would be "a new decision with a named consumer". A search of `docs/decisions` for "playwright" finds nothing. Playwright reached client standards on 27 Sep 2026 (commit `0fe366a6b`) and the starter on 23 Oct 2026 (commit `e457764d3`), both after 0027. No decision records that change. The last decision file is `0108`.
- No place records a screen list or a route table that code reads. `docs/design/prototype/SCREENS.md` lists design screens by name, for the design only.

### How the check works

One Node file, `src/forge/templates/design/render-check.mjs`, shipped as `.forge/design/render-check.mjs`. It is not app code, so `forge sync` may write it to an existing repo. It runs inside the app's own Playwright test, so Forge starts no browser and no server, and no Python reads a page. The agent adds one spec file per screen under `apps/web/e2e/render/<screen>.spec.ts` (one file for each screen, so two tasks never edit the same file):

```ts
import { test } from '@playwright/test';
import { checkScreen } from '../../../../.forge/design/render-check.mjs';
test('members renders cleanly', async ({ page }) => {
  // sign in or seed here, as any browser test does
  await checkScreen(page, { name: 'members', path: '/members', sources: ['apps/web/src/members/'],
    endpoints: { '/api/v1/members': { empty: { success: true, data: { items: [], nextCursor: null }, error: null } } } });
});
```

- Which screens. `checkScreen` runs a screen only when `FORGE_BASE` is set and a changed file (`git diff --name-only $FORGE_BASE`) lies under one of its `sources`, under `libs/shared/`, or is a stylesheet. When `FORGE_BASE` is not set, or git cannot answer, it checks the screen. A skipped screen prints `Rendered check: <name>: skipped, no listed source changed`. `review.test_run` sets `FORGE_BASE` to the merge base in the test command's environment (one line, next to the `FORGE_TEST_RESULTS` setting). The pull request check does not set it and checks every screen.
- States. For each width (1440 and 375, height 900) and each state, the helper sets the requests, loads the path and lets the page settle (fonts ready, animations done, at most 1 second, as `support.js` does). Loaded: the real answers. Loading: GET requests to each listed endpoint are held and never answered. Error: the same requests get a 500 with an error body. Empty: the same requests get the `empty` body that the spec lists; with none listed, the empty state is skipped and the line says so. Only `GET` requests are changed, so sign-in and writes still work.
- Themes. After each load it measures twice: with `page.emulateMedia({ colorScheme: 'light' })` and then `'dark'`, with no second load.
- Problems, each named `<screen> <width> <theme> <state> <rule>: <detail>`. `overflow`: the page scrolls sideways, or a visible element ends beyond the viewport outside a box that scrolls. `cut-text`: a text element hides its overflow and its scroll size is larger than its box. `low-contrast`: axe's `color-contrast` rule only. `layout-jump`: the layout shifts that a `PerformanceObserver` records in the first second after load add up to more than 0.1 (measured once for each load, before the theme change, ignoring shifts after input).
- Result. Every problem for the screen is collected, then one `Error` lists them all, so the Playwright test fails and close shows the screen's test name and the problem lines in its test output (last 30 lines, failed test names, full log path). A clean screen prints `Rendered check: <name>: no problems (1440 and 375, light and dark, <states>)`. Each measured state writes `test-results/render/<name>/<width>-<theme>-<state>.png` (16 files for a full screen).
- Waiver. `waive: { 'cut-text': 'the ellipsis is intended' }` on the screen's call sets one rule aside. A waiver with no words in the reason waives nothing. The error text shows the exact line to add.
- Missing pieces. When the axe tool cannot be loaded, the helper prints one line, `The rendered check did not run: <why>.`, and does not fail.

### Done-when details

1. Lists or says none.
   - Cases. A clean page prints the "no problems" line and writes the pictures. A page with one problem fails the test with that problem named. With `FORGE_BASE` set to a base where no listed source changed, the screen is skipped and the line says so; with one listed source changed, it runs. With no `empty` body listed, the empty state is skipped and the line says so.
   - New and existing. `tests/test_render_check.py::test_1_a_changed_screen_lists_its_rendered_problems_or_none`, parameters `new client` (`forge init`, then the helper from `.forge/design/`) and `earlier adopted` (the fixture, `forge sync`, the same helper).
   - How the test runs a real browser. The test is `@pytest.mark.platform`. It installs `playwright-core` and `@axe-core/playwright` at the versions that the starter's `package.json` pins (read from that file, so they cannot drift) into a temporary folder with `npm install`, and starts the system Chrome through `executablePath` set from `CHROME_BIN`, found as `tests/test_uistandards_canvas.py::_browser` finds it. It serves the fixture pages with Playwright's `page.route` on a made-up origin, so no app and no Docker are needed. When `npm`, the network or Chrome is missing it skips and prints which one. The stand-in is the page, never the helper.
2. Four problems, named.
   - Cases. One fixture page whose faults show only in one place each: sideways overflow only at 375 (a media query), cut text only in the error state (a clamped message), low contrast only in dark (a colour that fails only under `prefers-color-scheme: dark`), and a layout jump only in the loaded state (a block added after 300 ms). The failure text must name each of the four with its exact screen, width, theme and state and no other combination. A table inside its own scrolling box at 375 is not an overflow. A waiver with a reason passes that rule only; the same waiver with no reason still fails.
   - New and existing. `tests/test_render_check.py::test_2_each_rendered_problem_names_its_screen_width_theme_and_state`, parameters `new client` and `earlier adopted`.
3. New and existing repos.
   - Cases. `forge init` and `forge init --starter` write `.forge/design/render-check.mjs` byte for byte as the template, and write the worker brief, the guide, the browser-test convention and the synced skills with the new text. `forge sync` on the earlier-adopted fixture writes the same file and the same text, exits 0, and changes no file under `apps/`, `libs/` or `scripts/`, and not `package.json`. `forge doctor` says nothing new about the adopted repo. `tests/test_setup.py` and `tests/test_split_ships.py` gain the new path.
   - `tests/test_render_words.py::test_3_new_and_existing_repos_get_the_rendered_check_and_its_rules`, parameters `new client` and `earlier adopted`.
4. No model call at close.
   - Cases. In a client repo whose test command is a stand-in that prints the helper's failing lines, `forge close` calls the reviewer the usual number of times, and no call carries a picture path or a `test-results/render` path. The guide, `skill.md` and the worker brief say that a model looks at the saved pictures only before a demo or before sign-off, one turn each, and name the set to read (the loaded state at both widths and both themes for each demo screen, plus any picture the check flagged).
   - `tests/test_render_words.py::test_4_close_makes_no_model_call_for_the_rendered_check`, parameters `new client` and `earlier adopted`.
5. Sample-data prototype.
   - Cases. In a client prototype with `sample_data = true` and a test command that would create `test-results/render/`, `forge close` prints "Sample-data mode skips tests and CI.", runs no command and leaves no such folder. After `sample_data` is set to `false`, the command runs. The pre-demo text says that a sample-data prototype has no pictures to read before sign-off, and that the agent walks the demo in a browser as today.
   - New and existing. `tests/test_render_words.py::test_5_a_sample_data_prototype_runs_no_rendered_check_before_signoff`, parameters `new client` (switch in `forge.toml`) and `earlier adopted` (the switch as the sign-off record's own line, which `tests/test_proto_signoff.py::_adopted_client` already sets up).

### New and existing repos

- **New repos** (`forge init`, `forge init --starter`, `forge init --starter python`, adoption): the helper at `.forge/design/render-check.mjs`; the worker brief step that adds one render spec for each screen the worker builds or changes; the review rule; the guide and `skill.md` text for the look before a demo and before sign-off; the browser-test convention. The starter ships no render spec, because it ships no screens. The first screen the agent builds gets its spec, and the first close that touches it runs the check.
- **Existing repos** (upgrade, then `forge sync`): the same helper and the same text, and no app file. A screen gets its render spec when a story first changes it, as the testing convention already says for browser tests ("do not backfill untouched flows"). A repo with no Playwright keeps today's rules. A repo whose test command passes no base checks every screen it has a spec for. A sample-data prototype gets the check with its first tests after sign-off.

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
| HELPER | The rendered check, shipped to every client repo | The Node file with `checkScreen` (changed-screen filter, the four states, both widths and themes, the four problems, the waiver, the pictures, the one-line note when axe is missing); the second entry in `ui_checks.ships` so `init` and `sync` write it; `FORGE_BASE` in the test command's environment; the real-browser tests. | 1, 2 | `src/forge/templates/design/render-check.mjs`, `src/forge/ui_checks.py` (the `ships` dictionary), `src/forge/review.py` (the one `FORGE_BASE` line in `test_run`; 1,193 lines before, 1,194 after), `tests/test_render_check.py` (new), `tests/test_setup.py`, `tests/test_split_ships.py` | `tests/test_render_check.py::test_1_a_changed_screen_lists_its_rendered_problems_or_none`, `::test_2_each_rendered_problem_names_its_screen_width_theme_and_state`; `tests/test_setup.py` and `tests/test_split_ships.py` (the shipped-file lists gain `.forge/design/render-check.mjs`) | | no | |
| WORDS | The steps and rules that make the agent use it | The worker brief step (one render spec for each screen built or changed, with `endpoints` listed), the review rule `Gate: rendered check`, the `skill.md` look before a demo and before sign-off (one model turn, the picture set, the sample-data case), the guide paragraph, the browser-test convention, the synced skills, the decision record, and the new and existing repo cases. | 3, 4, 5 | `src/forge/templates/brief.md`, `src/forge/templates/review.md`, `src/forge/templates/skill.md`, `src/forge/templates/conventions/testing.md`, `docs/guide.md`, `docs/decisions/0109-rendered-checks-run-in-client-browser-tests.md` (new), `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_render_words.py` (new), `tests/test_fix_end_to_end_test_guidance.py` and `tests/test_fix_forge_says_end_to_end_tests_come_first_b.py` (only if they pin the testing convention's text), `tests/fixtures/worker-brief-before-delegation.md` (only if a brief test reads it) | `tests/test_render_words.py::test_3_new_and_existing_repos_get_the_rendered_check_and_its_rules`, `::test_4_close_makes_no_model_call_for_the_rendered_check`, `::test_5_a_sample_data_prototype_runs_no_rendered_check_before_signoff` | HELPER | no | |

Order. HELPER first: it pins the helper's name and place (`.forge/design/render-check.mjs`), the call `checkScreen(page, { name, path, sources, endpoints, waive })`, the `FORGE_BASE` variable, the output line `Rendered check: <name>: ...`, and the error line `<screen> <width> <theme> <state> <rule>: <detail>`, with real-browser tests that cross both sides. WORDS second, so the text states what the code does. The two share no file. The column says no for both because neither changes a screen: HELPER adds a file that prints lines in a test, and WORDS changes instructions for agents and reviewers. WORDS has the decision record because the story needs an accepted statement that the check runs in the client's browser tests; the coordinator accepts it with `forge decision accept`, as for any decision, and the story does not change decision 0027's text.

New moving parts: one small Node file shipped to every client repo and run inside the client's existing Playwright tests (Done-when 1 and 2). It adds no package, service, job, setting or command, and Forge itself starts no browser.

## Notes

Questions for the owner. Each has the planner's recommendation first.

1. Should a rendered problem stop close, or only be listed? Recommended: stop close. All four kinds fail the screen's test, and one screen can set aside one kind with a written reason. This is how a failed test or a design-check problem already works, so close gets no new refusal code. The alternative is a list that never stops close; a list that nobody must act on is easy to ignore, and the model look then finds the same problems late.
2. How does the check reach a screen's empty, loading and error states? Recommended: the agent lists, for each screen, the data requests it makes. The check answers them with an empty body, no answer, or a 500. Forge ships no screen and the app needs no extra code. The alternative is for each screen to offer its own way to show a state (for example a `?state=error` address). That puts test-only code in the app and every screen must carry it.
3. How many pictures should the model read before a demo or sign-off? Recommended: the loaded state at both widths and both themes for each demo screen (4 for each screen), plus every picture where the check found a problem. The alternative is all 16 pictures for each screen. That is four times the picture tokens for little gain, because a problem in the other states is already named in text by the check.

Planner choices not asked of the owner. The check runs inside the app's browser tests and not from Forge's Python, so Forge starts no browser and no server and `close.py` does not change. A sample-data prototype runs nothing before sign-off, because it has no test step; the agent's walk through the demo steps stays the only look, and the model read of pictures does not apply to it. In the pull request check with no base, every listed screen runs. Shared parts and any stylesheet count as changing every screen. The pictures stay in the ignored `test-results/` folder, so a repo that runs its tests only in GitHub's checks has no pictures on the laptop; the agent then runs the render specs on the laptop before the demo, as it already runs the demo steps in a browser.

Scores (F x H >= 2 x C).
- The rendered check: F 3 (every UI change), H 2 (a broken screen reaches the client), C 2 (about 150 lines of Node, one Python line, text). 6 >= 4. Kept.
- The model look before a demo or sign-off: F 2, H 2, C 2 (one model call). 4 >= 4. Kept, at the limit.
- The changed-screens filter: F 3, H 1 (time only), C 1 (about 15 lines and one Python line). 3 >= 2. Kept.
- The waiver: F 2 (a design choice trips the check now and then), H 2 (without it close is stuck), C 1. 4 >= 2. Kept.
- Cut: a check that dark mode really changed the colours, and a change to the pull request check to pass a base. Each would add code for a case that Risks names and the pictures show.

This story removes no process, so it adds to Forge's size: one shipped file of about 150 lines, one Python line and text. It deletes nothing. The source-only design checks stay, because close still needs a check that starts no app.

Order with other work. FORGE-UISTANDARDS-1 (the checker and the canvas widths) and FORGE-NOSCREENS-1 (a starter with no screens) are already in this worktree. HELPER edits `ui_checks.py` and one line of `review.py`; WORDS edits `brief.md`, `review.md`, `skill.md` and `docs/guide.md`, which other open stories also edit (FORGE-SAMPLE-1 edits `skill.md` and the guide). I did not check which stories are open, so a clash is a merge order at most, not a conflict in these Scopes.

Could not verify here (no test was run, as asked).
- Whether the machine that runs Forge's tests can run `npm install` for `playwright-core` and `@axe-core/playwright`. HELPER's tests skip with a clear message when it cannot. If the platform job cannot install them, the builder moves the real-browser proof to a job that can, and says so in the pull request.
- The 5 to 10 seconds a screen. It is an estimate from 8 page loads, 16 contrast scans and 16 pictures. The builder measures one screen in `tests/test_render_check.py` and writes the real number into the guide.
- That axe's `color-contrast` gives stable results with `emulateMedia({ colorScheme: 'dark' })` in the pinned Playwright 1.64.0. The test's low-contrast-only-in-dark case proves it.
- The exact line in `review.test_run` where `FORGE_BASE` is set. `review.close_test` computes the merge base for the default command, and `test_run` receives the review reference, so the builder computes it again with `git merge-base` there.
