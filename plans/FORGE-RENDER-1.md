# Close shows what a changed screen looks like

2 parts · Risks: none one-way · New moving parts: one small script that Forge copies into every client app; it runs inside the browser tests the app already has

## What changes for you

- When a client UI change closes, the app's own browser test step opens each screen on the app's check list, in its loaded state, in light and dark. Forge gives the agent a ready-made check. The agent adds a screen to the list when it builds or changes that screen. The browser and the tools are the ones the app already has. (Source: your request to create this story, 10 Nov 2026; your decision, 10 Nov 2026)
- The check always uses desktop width. It uses phone width only when the app needs a phone view. The agent asks once, before the app's build starts, whether the app needs a phone view, and writes the answer in the product brief. With no answer, the check uses desktop width only, and nothing is refused. An existing app has no answer yet, so it gets desktop width only until the agent asks at the next change to a screen. (Source: your decision, 10 Nov 2026: "Small check list but not all apps need mobile view, it's better to ask before start")
- Close reports three kinds of problem: sideways overflow, cut text and low contrast. Each report names the screen, the width and the theme. A screen with no problem gets one line that says so. The check also reports when the page that opened is not the listed screen, for example a sign-in page after a redirect, so it never calls the wrong page clean. (Source: your decision, 10 Nov 2026)
- A problem stops close, as a failed test does today. One screen can set aside one kind of problem if it gives a reason. The refusal shows how.
- Close makes no model call for this. Model cost is none.
- The check adds about 1 to 3 seconds for each screen on the list. This is an estimate and nobody has measured it. It runs where the app's browser tests run: on the laptop at close, or in the pull request check when the repo uses GitHub's checks.
- A new client repo gets the check, the agent's steps and the review rule when it starts. An existing client repo gets the same when it upgrades. No app file changes. A screen of an existing app joins the list the first time a change touches it. Old, untouched screens are not backfilled.
- A prototype marked as sample-data has no tests before sign-off, so it runs no rendered check then. The check starts with the first tests after sign-off.

Design: none (this story adds no screen and changes none; Forge ships a check and rules, not screens; owner rule, 31 Oct 2026)

## Why

Close checks only read code, so a screen that overflows, cuts text or fails contrast in dark mode can close and reach the client unseen. The design canvas pictures merged on 6 Nov 2026 cover only design canvases, not built screens. Not every app needs a phone view, so the check asks before it uses phone width.

## Done when

1. **A UI change that closes lists the rendered problems of each screen on the app's check list, by width and theme, or says that none were found.**
2. **Overflow, cut text and low contrast are each named with the screen, width and theme where they occur. A page that is not the listed screen is reported as a problem of its own. A problem stops close. One screen can set aside one kind of problem with a written reason.**
3. **The check uses desktop width always, and phone width only for an app whose phone-view answer is yes. With no answer, it uses desktop only and refuses nothing.**
4. **A new client repo gets the check, the question about the phone view and the review rule when it starts. An existing client repo gets them when it upgrades, with no app file changed, and a screen joins its list when a change first touches it.**
5. **A sample-data prototype runs no rendered check before sign-off. The check starts with its first tests.**

## Risks

Risks: none one-way. Each part reverts with its pull request. Nothing is deleted and no data changes. The story adds no new package: the app already installs its browser tool and its contrast tool. Model cost: none.

An accepted decision from 5 August 2026 says no browser is added to Forge's own tools or to a client repo, so that a page's width can be proven without one. That decision was about the board page in Forge's own tests. It also said that a real need for rendered checks would be a new decision with a named user. This story does not put a browser in Forge's own tools, and it adds no package to a client repo. The client starter has installed a browser test tool since 27 Sep 2026, after that decision, and no decision records the change. This story runs the check inside that tool and records a new decision in the same change. If you want Forge itself to start a browser at close, that is a different story, and it reverses the decision.

Trade-off: the agent adds each screen to the check list. Forge cannot see a screen that is not on the list. The review reports a changed screen that is not on the list as a serious finding, so a later step catches the miss. An app with no browser test tool gets no check and keeps today's rules.

Trade-off: the check opens every screen on the list each time the app's browser tests run, not only the screens a change touches. A screen joins the list when a change first touches it, so the list grows only as fast as the app changes. The planner chose this because a filter by changed files misses shared parts such as the app shell, and it needs a base that the full run and the pull request check do not have.

Trade-off: nothing checks that the agent asked about the phone view. A missed question means desktop width only, which is the cheaper check. You chose to ask and not to refuse.

Trade-off: dark mode follows the browser's colour-scheme setting, as the starter's theme file does. An app whose dark mode ignores that setting shows its light colours twice, and the check says nothing about it.

Trade-off: an app that does not have the contrast tool still gets the overflow and cut-text checks. The result line says that contrast was not checked.

Trade-off: cut text can be a design choice (a table cell that ends in "..." for example). The check reports it, and the screen can set it aside with a reason.

## For the builders

<!-- Everything from here down is for the agents. The owner doesn't see it when approving, and
tightening it needs no new approval. -->

Rules for every part. No new `forge` command, no new setting, no new package and no screen. Nothing under `src/forge/templates/starter` or `src/forge/templates/starter-python` changes: the review reports a screen, page, route table or app shell added there as P1. `close.py` is at its 1,200-line ceiling (`test_5_forge_stays_small`) and does not change.

Each new test file starts with `STORY = "FORGE-RENDER-1"`. Tests run the forge command and never import forge. There is one test per Done-when number, so the numbers stay unique across the files: `test_1`, `test_2` and `test_3` in `tests/test_render_check.py`, `test_4` and `test_5` in `tests/test_render_words.py`. Each has a new client case (`forge init`) and at least one earlier-adopted case (`tests/fixtures/adopted-v1.2.2/client` and `forge sync`, as `tests/test_canvas_phone_viewport.py` does). The real-browser cases need `npm install`, Chrome and the network; they fail with a message that names the missing piece and never skip, so an offline run cannot pass without testing the helper (as `tests/test_uistandards_canvas.py::_browser` already asserts that Chrome exists). Before a round ends, run the two cheap checks from AGENTS.md.

### What exists (evidence)

Checked in this worktree on 10 Nov 2026. A part checks each name again before it starts.

- Source of the story. The owner's request on 10 Nov 2026 to create this story, and his decision the same day to keep it small and to ask about the phone view first. The intake text had no named source (cold read round 1, finding 1); the owner-facing text now cites both.
- Design checks that read source only. `src/forge/templates/design/ui-checks.js` (98 lines) reads source text and runs impeccable's checker. It starts no browser and needs no running app. `src/forge/ui_checks.py` (37 lines) runs it for `app_baseline.check` (called at `src/forge/close.py:280`) and, through `ships(top, cfg)`, writes `.forge/design/ui-checks.js` to every client repo. `sync.ships` (`src/forge/sync.py:379`, loop at `:444-450`) finds every module that defines `ships(top, cfg)`, and `init` merges the same result (`src/forge/init.py:456`), so more entries in the `ui_checks.ships` dictionary reach new and adopted repos with no other wiring. `tests/test_setup.py:55-56` (`LISTED`) and `tests/test_split_ships.py:35-36` list the shipped paths.
- Canvas pictures (merged 6 Nov 2026). `src/forge/templates/design/support.js` (148 lines) draws each canvas `.html` file at 1440 and 375 through Chrome's own protocol, waits for `document.fonts.ready` and for animations (at most 1 second), and fails when `Math.max(documentElement.scrollWidth, body.scrollWidth) > innerWidth` at 375. It opens `file://` pages with no server and no Playwright and does not wait for app data. The new check reuses its two widths, its settle wait and its overflow measure, and adds a wait for the page's data requests. It cannot reuse the file: a built screen needs the running app and a sign-in.
- The browser tool in client apps. `@playwright/test` 1.64.0, `@axe-core/playwright` 4.10.2 and `typescript` 5.9.3 are root dependencies of the starter (`src/forge/templates/starter/package.json:55,60-61`; the Python starter has the two browser tools at `starter-python/package.json:42-43`). `apps/web/playwright.config.ts` has `testDir: './e2e'`, `retries: 0`, `workers: 2`, `fullyParallel` and only a `junit` reporter. `apps/web/tsconfig.json` includes `e2e` with `strict` (from `tsconfig.base.json`) and `moduleResolution: Bundler`. `src/forge/templates/starter/scripts/test.mjs` installs Chromium and runs `web:e2e` whenever the web app is affected; after a failure it prints container logs. `src/forge/templates/starter-python/scripts/test-browser.mjs` runs Playwright once for each spec file and recreates the API before each file. `init` sets `fast_test = "node scripts/test.mjs {base}"` (`src/forge/init.py:231`). The starter's theme file follows `prefers-color-scheme` (`libs/shared/ui/src/components/theme-provider.tsx:16-19`). `src/forge/templates/conventions/frontend.md:36` says an app made before the starter layout keeps its own folders.
- How close runs tests and what it shows. `review.test_run` (`src/forge/review.py:385`) prints the last 30 lines, every line that has "skip" and its previous line, and every line that starts with `GAP` (`review.py:382`), then the failed test names and the full log path. `review.py` has 1,193 lines. The full run calls the same `test_run` (`src/forge/fullrun.py:29`). With `sample_data = true`, `repo._sample_settings` (`src/forge/repo.py:665`) blanks `test`, `fast_test` and `checks`, and `test_run` returns "Sample-data mode skips tests and CI." (`review.py:402`).
- Where the answers to setup questions live. `docs/product/BRIEF.md` has a `## Answers` section with one line per topic: `- <Topic>: <answer> (<source>, <YYYY-MM-DD>)` (`src/forge/templates/skeleton/docs/product/BRIEF.md`). The topic table is in `src/forge/templates/skill.md:773-786`. `nextstep.parse_answers` (`src/forge/nextstep.py:71`) reads only the topics in `ANSWER_TOPICS` and ignores any other line, and `MUST_ANSWER_TOPICS` (`:63`) are the only topics that can be open at sign-off. A new topic row in the table with no change to `nextstep.py` therefore refuses nothing. `forge.toml` is agent-managed and the agent asks before it changes it, and `PRODUCT.md` and `DESIGN.md` hold the look, not setup answers. `tests/test_proto_topics.py:6,30` checks that the twelve existing rows are present in order and does not fail on an added row that is not in its list.
- Where the rules for workers and review live. `src/forge/templates/brief.md:440-467`, `src/forge/templates/review.md:324-336` (`Gate: UI check` and `Gate: UI standards`), `src/forge/templates/skill.md:800-860`, `src/forge/templates/conventions/testing.md:58-90` (Browser tests, with "do not backfill untouched flows"), `docs/guide.md`.
- The accepted decision. `docs/decisions/0027-responsive-proof-without-a-browser.md` (accepted 2026-08-05, story PH-4). Decision: "No browser dependency is added to the harness or to any client repo." It rejects a headless browser in the board's tests as heavier than the other shapes it forbids, and says rendered assertions would be "a new decision with a named consumer". A search of `docs/decisions` for "playwright" finds nothing. Playwright reached client standards on 27 Sep 2026 (commit `0fe366a6b`) and the starter on 23 Oct 2026 (commit `e457764d3`), both after 0027. No decision records that change. The last decision file is `0108`.

### How the check works

Two files, shipped to every client repo: `src/forge/templates/design/render-check.mjs` (as `.forge/design/render-check.mjs`) and its type declaration `src/forge/templates/design/render-check.d.mts` (as `.forge/design/render-check.d.mts`). The declaration lets a strict TypeScript test import the helper without error TS7016. They are not app code, so `forge sync` may write them to an existing repo. The helper runs inside the app's own Playwright test, so Forge starts no browser and no server, and no Python reads a page.

The agent keeps one file of screens beside the app's other browser tests, in the folder that the app's Playwright config looks in (`apps/web/e2e/render.spec.ts` in the starter; an older app keeps its own folder). One file, not one for each screen, so the Python starter's runner recreates its API once for the whole list, and two parts adding a screen touch one array line each:

```ts
import { test } from '@playwright/test';
import { checkScreen } from '../../../.forge/design/render-check.mjs';
const screens = [
  { name: 'members', path: '/members', phone: true, prepare: signInAsAdmin },
];
for (const screen of screens) {
  test(`${screen.name} renders cleanly`, async ({ page }) => {
    await screen.prepare?.(page); // sign in or seed here, as any browser test does
    await checkScreen(page, screen);
  });
}
```

- Declared shape: `checkScreen(page, { name: string, path: string, phone?: boolean, waive?: Record<string, string> })`, which resolves to nothing and throws one `Error` for a screen with problems.
- Widths. 1440 by 900 always. 375 by 900 only when `phone` is true. The agent sets `phone: true` when `docs/product/BRIEF.md` has `- Phone view: yes (...)` in its `## Answers` section. No line, `no`, `ask the client`, `later` or no brief file means desktop only.
- Loaded state only. For each width the helper loads the path, checks that the page it got is the listed screen, waits until the page's data requests are done (`waitForLoadState('networkidle')`, capped at 5 seconds), then lets fonts and animations settle (at most 1 second, as `support.js` does), and measures with `colorScheme: 'light'`. It then calls `page.emulateMedia({ colorScheme: 'dark' })` and measures again, with no second load.
- Which screen loaded. After the load, the helper compares `new URL(page.url()).pathname` with the listed `path` (query and hash ignored). A mismatch is one problem, `wrong-screen: the page loaded <actual path>, not <path>`, and the helper measures nothing else for that screen and width, so a redirected sign-in page is never reported as the listed screen. The listed path is therefore the final path: an app that redirects `/` to `/dashboard` lists `/dashboard`. The path check was chosen over a listed marker because it needs no extra entry field and no knowledge of the screen's markup, and a redirect is the case that matters.
- Problems, each named `<screen> <width> <theme> <rule>: <detail>`. `overflow`: the page scrolls sideways, or a visible element ends beyond the viewport outside a box that scrolls. `cut-text`: a text element hides its overflow and its scroll size is larger than its box. `low-contrast`: axe's `color-contrast` rule only. When `@axe-core/playwright` cannot be loaded, the helper still runs the other two rules, and the result line ends with `low contrast not checked: <why>`.
- Output. Every problem is printed on its own line that starts with `Rendered problem: `, and then one `Error` lists them all, so the Playwright test fails. A clean screen prints `Rendered check: <name>: no problems (<widths>, light and dark)`. `review.test_run` keeps every line that starts with `Rendered problem: ` in the tail it shows, as it already keeps `GAP` lines (a constant `RENDERED` and one clause, 2 lines in `review.py`). A screen has at most 3 rules × 2 widths × 2 themes = 12 such lines. The starter's `junit`-only reporter may print nothing about a failed test; the helper's own output must reach the command's output, and the first test proves it against that exact config.
- Waiver. `waive: { 'cut-text': 'the ellipsis is intended' }` sets one rule aside for the screen. A waiver whose reason has no words waives nothing. The error text shows the exact line to add.
- The phone-view question. A new row in the topic table in `skill.md`: `Phone view | Does the app need a phone view? | no (default); yes | before the app's build starts`. The agent asks it once, records `- Phone view: <answer> (<source>, <date>)` in `## Answers`, and sets `phone` on each screen of an app whose answer is yes. For an existing app the agent asks at the next change to a screen when the line is missing. No Python reads the line, and nothing refuses when it is missing.

### Done-when details

1. Lists or says none.
   - Cases. A clean fixture page prints the `Rendered check ... no problems` line. A fixture page with one problem fails the test, and `Rendered problem:` names it. Several screens in one list run in one file.
   - `tests/test_render_check.py::test_1_a_closing_ui_change_lists_rendered_problems_or_says_none`, parameters `new client` (`forge init`, then the helper from `.forge/design/`) and `earlier adopted` (the fixture and `forge sync`; the clean page only). The test is `@pytest.mark.platform`. It installs `@playwright/test`, `@axe-core/playwright` and `typescript` at the versions that the starter's `package.json` pins (read from that file, so they cannot drift) into the fixture client with `npm install`. It copies the starter's `playwright.config.ts` and adds `launchOptions: { executablePath: process.env.CHROME_BIN }`, found as `_browser()` finds it. It serves the fixture pages with a local static server (`BASE_URL`) and runs `playwright test` with that config, so the starter's `junit`-only reporter is the one under test. It also runs `tsc --noEmit --strict` with `moduleResolution: Bundler` over the example spec and asserts that it exits 0, so any type error in the example (a missing declaration or a wrong argument type) fails the test.
2. Three problems named, stops close, waiver.
   - Cases. A listed screen whose address the static server redirects to a clean sign-in-like page: the result is one `wrong-screen` problem that names both paths, never a clean line. One fixture page whose faults show only in one place each: overflow only at 375 (a media query, with `phone: true`), cut text only in light, and low contrast only in dark (a colour that fails only under `prefers-color-scheme: dark`). The `Rendered problem:` lines name each with its exact screen, width and theme and no other combination. A table inside its own scrolling box at 375 is not an overflow. A waiver with a reason passes that rule only; the same waiver with no reason still fails. Without the contrast package installed, the overflow and cut-text results still appear and the result line says contrast was not checked.
   - Close shows them. A stand-in test command in a client fixture prints three `Rendered problem:` lines, then 60 lines of other output, and exits 1. `forge close` prints the three lines and refuses. This is the case that the starter's container logs would otherwise push out of the last 30 lines.
   - `tests/test_render_check.py::test_2_each_rendered_problem_names_its_screen_width_and_theme_and_stops_close`, parameters `new client` (all cases) and `earlier adopted` (the close case on the adopted fixture).
3. Desktop always, phone by answer.
   - Cases. A screen without `phone` is measured at 1440 only, and the result line says so. With `phone: true` it is measured at 1440 and 375. A second page overflows only at 375: without `phone` it passes, with `phone: true` it fails.
   - `tests/test_render_check.py::test_3_phone_width_is_checked_only_when_the_screen_asks_for_it`, parameters `new client` and `earlier adopted` (the fixture and `forge sync`; the desktop-only default).
4. New and existing repos.
   - Cases. `forge init` and `forge init --starter` write `.forge/design/render-check.mjs` and `.forge/design/render-check.d.mts` byte for byte as the templates, and write the worker brief, the guide, the browser-test convention and the synced skills with the new text, including the `Phone view` row. `forge sync` on the earlier-adopted fixture writes the same files and text, exits 0, and changes no file under `apps/`, `libs/` or `scripts/`, and not `package.json`. `forge doctor` says nothing new about the adopted repo. The open topics that `forge next` lists are the same, so a missing `Phone view` line refuses nothing. `tests/test_setup.py` and `tests/test_split_ships.py` gain the two paths.
   - `tests/test_render_words.py::test_4_new_and_existing_repos_get_the_rendered_check_and_the_phone_question`, parameters `new client` and `earlier adopted`.
5. Sample-data prototype.
   - Cases. In a client prototype with `sample_data = true` and a test command that would create `test-results/render-ran`, `forge close` prints "Sample-data mode skips tests and CI.", runs no command and leaves no such file. After `sample_data` is set to `false`, the command runs.
   - `tests/test_render_words.py::test_5_a_sample_data_prototype_runs_no_rendered_check_before_signoff`, parameters `new client` (switch in `forge.toml`) and `earlier adopted` (the switch as the sign-off record's own line, which `tests/test_proto_signoff.py::_adopted_client` already sets up).

### New and existing repos

- **New repos** (`forge init`, `forge init --starter`, `forge init --starter python`, adoption): the helper and its declaration at `.forge/design/`; the worker brief step that adds each built or changed screen to the render list; the review rule; the `Phone view` question in the topic table; the browser-test convention. The starter ships no render list, because it ships no screens. The first screen the agent builds goes on the list, and the next close runs the check.
- **Existing repos** (upgrade, then `forge sync`): the same two files and the same text, and no app file. A screen goes on the list when a change first touches it, as the testing convention already says for browser tests ("do not backfill untouched flows"). The list sits in the folder where the app's own Playwright config looks. There is no `Phone view` line yet, so the check uses desktop width only until the agent asks at the next change to a screen. A repo with no Playwright keeps today's rules. A sample-data prototype gets the check with its first tests after sign-off.

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
| HELPER | The rendered check, shipped to every client repo | The Node file with `checkScreen` (loaded state, desktop always and phone by flag, light and dark, the three problems, the waiver, the `Rendered problem:` lines), its type declaration, the two entries in `ui_checks.ships` so `init` and `sync` write them, the `RENDERED` marker that keeps those lines in close's tail, and the real-browser tests. | 1, 2, 3 | `src/forge/templates/design/render-check.mjs`, `src/forge/templates/design/render-check.d.mts`, `src/forge/ui_checks.py` (the `ships` dictionary), `src/forge/review.py` (the `RENDERED` constant and one clause in `test_run`; 1,193 lines before, 1,195 after), `tests/test_render_check.py` (new), `tests/test_setup.py`, `tests/test_split_ships.py` | `tests/test_render_check.py::test_1_a_closing_ui_change_lists_rendered_problems_or_says_none`, `::test_2_each_rendered_problem_names_its_screen_width_and_theme_and_stops_close`, `::test_3_phone_width_is_checked_only_when_the_screen_asks_for_it`; `tests/test_setup.py` and `tests/test_split_ships.py` (the shipped-file lists gain the two paths) | | no | |
| WORDS | The steps and rules that make the agent use it | The worker brief step (add each built or changed screen to the render list beside the app's browser tests; set `phone` from the brief's `Phone view` answer), the review rule `Gate: rendered check`, the `Phone view` row and its sentence in `skill.md`, the guide paragraph, the browser-test convention, the synced skills, the decision record, and the new and existing repo cases. | 4, 5 | `src/forge/templates/brief.md`, `src/forge/templates/review.md`, `src/forge/templates/skill.md`, `src/forge/templates/conventions/testing.md`, `docs/guide.md`, `docs/decisions/0109-rendered-checks-run-in-client-browser-tests.md` (new), `.claude/skills/forge/SKILL.md` and `.codex/skills/forge/SKILL.md` (rewritten by `forge sync`), `tests/test_render_words.py` (new), `tests/test_fix_end_to_end_test_guidance.py` and `tests/test_fix_forge_says_end_to_end_tests_come_first_b.py` (only if they pin the testing convention's text), `tests/fixtures/worker-brief-before-delegation.md` (only if a brief test reads it) | `tests/test_render_words.py::test_4_new_and_existing_repos_get_the_rendered_check_and_the_phone_question`, `::test_5_a_sample_data_prototype_runs_no_rendered_check_before_signoff` | HELPER | no | |

Order. HELPER first: it pins the helper's name and place (`.forge/design/render-check.mjs` and its `.d.mts`), the call `checkScreen(page, { name, path, phone?, waive? })`, the output line `Rendered check: <name>: ...` and the problem line `Rendered problem: <screen> <width> <theme> <rule>: <detail>`, with real-browser tests that cross both sides. WORDS second, so the text states what the code does. The two share no file. The column says no for both because neither changes a screen: HELPER adds files that print lines in a test, and WORDS changes instructions for agents and reviewers. WORDS has the decision record because the story needs an accepted statement that the check runs in the client's browser tests; the coordinator accepts it with `forge decision accept`, and the story does not change decision 0027's text.

New moving parts: two small files (a Node script and its type declaration) shipped to every client repo and run inside the client's existing Playwright tests (Done-when 1, 2 and 3). It adds no package, service, job, setting or command, and Forge itself starts no browser.

## Notes

Question for the owner, with the planner's recommendation first.

1. Should a rendered problem stop close, or only be listed? Recommended: stop close. All three kinds fail the test, and one screen can set aside one kind with a written reason. This is how a failed test or a design-check problem already works, so close gets no new refusal code. The alternative is a list that never stops close; a list that nobody must act on is easy to ignore.

Later stories (wording for `plans/ideas.md`; this plan does not edit that file).
- Rendered states: "Do it later: the rendered check opens each screen in its empty, loading and error states too, by answering the screen's own data requests (kept on FORGE-RENDER-1)."
- Layout jumps: "Do it later: the rendered check reports layout jumps in each screen after load (kept on FORGE-RENDER-1)."
- Model look: "Do it later: before a demo or sign-off, a model reads saved pictures of the demo screens and reports what a person would see, one model call each time, with the cost stated (kept on FORGE-RENDER-1)." This story saves no pictures, so that story adds them.

Planner choices not asked of the owner. The check runs inside the app's browser tests and not from Forge's Python, so Forge starts no browser and no server and `close.py` does not change. It opens every screen on the render list each time the app's browser tests run; there is no filter by changed files (see Risks). A sample-data prototype runs nothing before sign-off, because it has no test step; the agent's walk through the demo steps stays the only look. The answer to the phone-view question lives in the brief's `## Answers` section because that is where the setup answers already live and no code needs to read it; `forge.toml` would need a settings change and a reviewed pull request for a value that only guides the agent. The default is desktop only.

Scores (F x H >= 2 x C).
- The rendered check: F 3 (every UI change), H 2 (a broken screen reaches the client), C 2 (about 120 lines of Node, a 10-line declaration, 2 Python lines, text). 6 >= 4. Kept.
- The phone-view question: F 2 (each new app), H 1 (a wasted check or a missed phone check), C 1 (one table row and a few sentences, no code). 2 >= 2. Kept, at the limit, because you decided it.
- The waiver: F 2, H 2 (without it close is stuck), C 1. 4 >= 2. Kept.
- Cut: the changed-screens filter and its base variable, the empty, loading and error states, layout jumps, the pictures and the model look, a check that dark mode really changed the colours.

This story removes no process, so it adds to Forge's size: about 130 lines of shipped files, two Python lines and text. It deletes nothing. The source-only design checks stay, because close still needs a check that starts no app.

Order with other work. FORGE-UISTANDARDS-1 (the checker and the canvas widths) and FORGE-NOSCREENS-1 (a starter with no screens) are already in this worktree. WORDS edits `brief.md`, `review.md`, `skill.md` and `docs/guide.md`, which other open stories also edit (FORGE-SAMPLE-1 edits `skill.md` and the guide). I did not check which stories are open, so a clash is a merge order at most.

Could not verify here (no test was run, as asked).
- Whether Playwright 1.64.0 prints test output when the config has only the `junit` reporter, so that `Rendered problem:` lines reach the command's output. The first test runs the starter's own config to find out. If they do not appear, the helper writes them with `process.stderr.write` instead, and the test shows which works.
- Whether `waitForLoadState('networkidle')` settles screens that poll their API; Playwright documents it as discouraged. The wait is capped at 5 seconds and the helper measures after it.
- Whether the machine that runs Forge's tests can run `npm install` for the three pinned packages. HELPER's tests fail with a message when it cannot.
- The 1 to 3 seconds a screen. It is an estimate from 1 or 2 page loads and 2 to 4 contrast scans. The builder measures one screen in `tests/test_render_check.py` and writes the real number into the guide.
- That axe's `color-contrast` gives stable results with `emulateMedia({ colorScheme: 'dark' })` in the pinned Playwright 1.64.0. The low-contrast-only-in-dark case proves it.
