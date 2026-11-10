---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-10T17:47:52.340343+00:00
seconds: 378.314
read_hash: 0e0fb8fc3c3612af10278a51f8df7e8430c881f5
round: 2
passed: no
doc_seen: 0e0fb8fc3c3612af10278a51f8df7e8430c881f5
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: b938f3963c1dab37d3ab8cc0732204573be66cfd
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1c67d-c6e9-70e3-b108-c24fe724077b
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

1. Blocking: Not needed: the new rendered-check script and picture review have no named source.  
   Raise: Not needed  
   Case: normal use - Every client app receives the roughly 150-line helper and the new review steps.  
   The [product brief](/docs/product/BRIEF.md:3) does not request them, and the [screen-design decision](/docs/decisions/0097-design-work-uses-opus.md:13) chooses a design worker rather than these checks. Name the source or sourced behavior that needs them, or remove them and add one line to `plans/ideas.md`.  
   Gain 4, Work 2, Harm 1
    Disposition: cut - the owner-facing text now names its source (the owner's request of 10 Nov 2026 and his decision the same day); the owner's decision also cut the story to a small check, and the pictures and the model that reads them moved to a later story (idea line in Notes).

2. Blocking: Not done: the first starter screen’s example test fails type checking.  
   Raise: Not done  
   Case: normal use - A worker adds the example test for a new screen.  
   The [example](/plans/FORGE-RENDER-1.md:72) imports the JavaScript helper from a TypeScript test, but the plan ships no type declaration. The starter enables [strict type checking](/src/forge/templates/starter/tsconfig.base.json:4) and [includes browser tests](/src/forge/templates/starter/apps/web/tsconfig.json:21). TypeScript reports `TS7016` before the browser check runs. The planned helper tests do not compile the example.  
   Gain 5, Work 2, Harm 3
    Disposition: cut - HELPER now ships a type declaration (`render-check.d.mts`) beside the helper, and `test_1` runs `tsc --strict` over the example spec and asserts no TS7016.

3. Blocking: Not done: existing apps can place the test outside their browser test directory.  
   Raise: Not done  
   Case: normal use - An adopted app keeps its Playwright configuration and browser tests at the repository root.  
   The [plan](/plans/FORGE-RENDER-1.md:70) always puts the new test under `apps/web/e2e/render`, while the [existing-app convention](/src/forge/templates/conventions/frontend.md:36) preserves the app’s layout. A root configuration that selects `./e2e` will not discover that test, so the next screen change gets no rendered check.  
   Gain 4, Work 2, Harm 3
    Disposition: cut - the render list is one file beside the app's own browser tests, in the folder its Playwright config looks in (the starter's `apps/web/e2e`; an older app keeps its own folder), as the existing-app convention says.

4. Blocking: Not done: shared shell changes can skip every affected screen.  
   Raise: Not done  
   Case: normal use - A change to the app shell alters the layout around several screens.  
   The [filter](/plans/FORGE-RENDER-1.md:82) checks only listed sources, `libs/shared/`, and stylesheets. The [standard shell location](/src/forge/templates/conventions/frontend.md:16) is outside those automatic matches and outside the example’s listed source. Existing screen tests can therefore all report “skipped” after a shell change.  
   Gain 4, Work 2, Harm 3
    Disposition: cut - the changed-files filter is removed; every screen on the render list is checked each time the browser tests run, so a shell change cannot skip a screen (Risks names the trade-off).

5. Blocking: Not done: the helper can measure loading content as the loaded or error state.  
   Raise: Not done  
   Case: normal use - A screen fetches its data after the page loads.  
   The [plan](/plans/FORGE-RENDER-1.md:83) waits for fonts and animations, but specifies no wait for the requested state to appear. The reused [canvas wait](/src/forge/templates/design/support.js:90) does not wait for app data. A slow response can leave the loading view on screen while its picture and results are labelled loaded, empty, or error.  
   Gain 4, Work 2, Harm 3
    Disposition: cut - the helper waits for the page's data requests (`networkidle`, capped at 5 seconds) before it measures; only the loaded state remains, so no wrong state label is possible.

6. Blocking: Not done: form submission states cannot be produced by the proposed check.  
   Raise: Not done  
   Case: normal use - A sign-in screen shows an error after a failed sign-in.  
   The [helper](/plans/FORGE-RENDER-1.md:83) reloads the page and changes only GET requests. The starter’s [sign-in rule](/src/forge/templates/starter/apps/web/e2e/rules/sign-in.spec.ts:11) submits a POST after a button click. Listing an endpoint cannot produce that error or the submission’s loading state, so the check measures the wrong view.  
   Gain 4, Work 2, Harm 3
    Disposition: cut - the empty, loading and error states moved to a later story (idea line in Notes), so no form-submission state is needed.

7. Blocking: Not done: layout jumps are not measured separately in both themes.  
   Raise: Not done  
   Case: normal use - A screen adds or rearranges content on load only in dark mode.  
   The [plan](/plans/FORGE-RENDER-1.md:84) loads once, measures the jump before changing theme, and then switches themes without reloading. It cannot reliably find or attribute a dark-only load shift, although Done-when 2 requires the theme where it occurred.  
   Gain 3, Work 2, Harm 3
    Disposition: cut - layout jumps moved to a later story (idea line in Notes) and are out of Done-when, tasks, tests and Risks.

8. Blocking: Not done: a missing contrast tool disables the entire check.  
   Raise: Not done  
   Case: normal use - An existing app has Playwright but does not have `@axe-core/playwright`.  
   The [plan](/plans/FORGE-RENDER-1.md:88) prints a note and passes without running the helper. That leaves overflow, cut text and layout jumps unchecked too; the stated exception in [Risks](/plans/FORGE-RENDER-1.md:35) covers an app with no browser tool, not one missing the contrast package.  
   Gain 4, Work 2, Harm 3
    Disposition: cut - a missing contrast tool no longer disables the check: overflow and cut text still run, and the result line says contrast was not checked (`test_2` covers it).

9. Blocking: Not done: local close can hide the rendered problems it must report.  
   Raise: Not done  
   Case: normal use - A rendered test fails and the starter prints container logs afterward.  
   The [starter test command](/src/forge/templates/starter/scripts/test.mjs:94) prints those logs after the browser failure. Local close retains only the [last 30 output lines](/src/forge/review.py:494), apart from selected skip lines. Those logs can push out the screen, width, theme, state and waiver instructions; a full-log path does not itself report them.  
   Gain 4, Work 2, Harm 3
    Disposition: cut - `review.test_run` keeps every `Rendered problem:` line in its tail, as it keeps `GAP` lines (2 lines in `review.py`, now in HELPER's Scope), and `test_2` runs `forge close` against 60 lines of later output.

10. Blocking: Functional: the full test run skips every rendered screen.  
    Raise: Functional  
    Case: normal use - The scheduled full suite runs on the latest default-branch commit.  
    [Full run](/src/forge/fullrun.py:77) passes that same commit as the base to `test_run`. The planned [environment change and filter](/plans/FORGE-RENDER-1.md:82) make the diff against that base empty, so every render test skips while the full suite can pass.  
    Gain 4, Work 2, Harm 3
    Disposition: cut - with the filter and the base variable removed, the full run checks every listed screen and skips none.

11. Blocking: Not done: picture review requires images that untouched demo screens never produce.  
    Raise: Not done  
    Case: normal use - An existing app demonstrates an old screen that has not changed since the upgrade.  
    The [plan](/plans/FORGE-RENDER-1.md:45) asks the model to read four pictures of every demo screen, but [does not backfill tests](/plans/FORGE-RENDER-1.md:112) for untouched screens. Running the existing render tests locally cannot produce pictures for a screen without one.  
    Gain 3, Work 2, Harm 3
    Disposition: cut - the model look at pictures moved to a later story (idea line in Notes), and the story saves no pictures, so no untouched screen needs one.

12. Blocking: Scale: skipped screens still restart the Python starter’s API.  
    Raise: Scale  
    Case: normal use - A Python-backed app has ten screen tests and changes one screen.  
    The [browser runner](/src/forge/templates/starter-python/scripts/test-browser.mjs:17) recreates the API and starts Playwright once per test file before the helper can skip it. The plan’s one-file-per-screen shape therefore adds ten sequential API recreations on that run, including nine for unchanged screens.  
    Adds work: avoid that setup for skipped screens; F 3 x H 2 = 6; 2 x C = 4.  
    Gain 3, Work 2, Harm 3
    Disposition: cut - the render list is one spec file for all screens, so the Python starter's runner recreates its API once, not once per screen.

13. Blocking: Trap: an offline CI run can pass without testing the helper.  
    Raise: Test  
    Case: normal use - A CI runner cannot reach the package registry.  
    Both behavior tests [skip when installation fails](/plans/FORGE-RENDER-1.md:95), so even a helper that misses every rendered defect can pass the suite. The existing [canvas browser test](/tests/test_uistandards_canvas.py:20) requires its browser instead of treating its absence as proof.  
    Gain 3, Work 2, Harm 3
    Disposition: cut - the real-browser cases fail with a message that names the missing piece (npm, network or Chrome) and never skip, as the canvas test asserts Chrome exists.

14. Advisory: Cut or defer the repeated adopted-repo browser cases.  
    Raise: Test  
    The [plan](/plans/FORGE-RENDER-1.md:93) repeats the full browser cases after both init and sync, while its [upgrade test](/plans/FORGE-RENDER-1.md:100) already checks that both paths ship the same helper. The repeated browser cases exercise the same helper path.  
    Gain 2, Work 1, Harm 1
   Disposition: keep - below the bar (live with)

## Round 2

15. Blocking: Not done: a redirect can make the check report a different screen as clean.  
    Raise: Not done  
    Case: normal use - A listed screen requires sign-in, but its test reaches the sign-in page instead.  
    The [helper contract](/plans/FORGE-RENDER-1.md:90) names a path but does not check which screen loaded. The starter’s [sign-in test](/src/forge/templates/starter/apps/web/e2e/rules/sign-in.spec.ts:50) shows that `/members` redirects to sign-in. The helper can therefore report “members: no problems” after checking sign-in. The planned static-page test does not cover a redirect.  
    Gain 5, Work 2, Harm 3
    Disposition: cut - the helper compares the final page path with the listed path and reports a mismatch as its own `wrong-screen` problem (path check chosen over a marker: no extra field, no knowledge of the markup); `test_2` gets a redirect case; no Done-when line added, only a clause in Done-when 2.

16. Advisory: Not done: a later phone-view answer does not update existing list entries.  
    Raise: Not done  
    Case: normal use - The client initially defers the phone-view answer, then answers yes after several screens are listed.  
    The [plan](/plans/FORGE-RENDER-1.md:91) stores the choice separately as a flag on each screen; the helper does not read the brief. The existing [answer flow](/src/forge/templates/skill.md:793) updates the brief when the client replies, but the plan gives no corresponding update for already-listed screens. They can continue to run at desktop width only.  
    Gain 3, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)

17. Advisory: Not done: a repeated close loses clean-screen results.  
    Raise: Not done  
    Case: normal use - Local tests pass, close waits for another check, and the coordinator closes again on the same files.  
    [Close reuses the passing run](/src/forge/review.py:410) and returns a skipped-test message. It does not replay the clean-screen lines required by [Done-when 1](/plans/FORGE-RENDER-1.md:24). The new output rule preserves problem lines, not clean results from a reused run.  
    Gain 3, Work 2, Harm 2
   Disposition: keep - below the bar (follow-up)

18. Advisory: Plan gap: the single screen list becomes a shared file for parallel parts.  
    Raise: Plan gap  
    Case: normal use - Two independent parts each add a screen.  
    Both must edit the [same array](/plans/FORGE-RENDER-1.md:74). If both name that file in Scope, [plan checking](/src/forge/plan_scope.py:16) refuses the overlap: `e2e` is not an exempt test-directory segment. If they name it only under Tests, concurrent additions at the same array location can conflict at merge.  
    Adds work: coordinate the shared list edits; F 2 x H 2 = 4; 2 x C = 4.  
    Gain 3, Work 3, Harm 2
   Disposition: keep - below the bar (follow-up)

19. Advisory: Scale: one screen list can exhaust the starter’s sign-in limit.  
    Raise: Scale  
    Case: normal use - A Python-backed app checks 31 protected screens whose setup signs in within one minute.  
    The [new list](/plans/FORGE-RENDER-1.md:79) runs preparation once per screen in one test file. The Python starter permits [30 sign-in requests per client and path per minute](/src/forge/templates/starter-python/apps/api/app/core/security.py:17), and its runner resets that limit only [between files](/src/forge/templates/starter-python/scripts/test-browser.mjs:20). Later screens can fail before they are checked.  
    Adds work: avoid exhausting the limit during screen preparation; F 2 x H 2 = 4; 2 x C = 4.  
    Gain 3, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)

20. Advisory: Test: the type-check proof can pass while the screen test fails to compile.  
    Raise: Test  
    The amended [test](/plans/FORGE-RENDER-1.md:102) asserts only that `TS7016` is absent. A declaration with the wrong argument types can instead produce `TS2345`; Playwright can run the JavaScript while that TypeScript error remains, so the stated assertion can pass with a broken client type check.  
    Gain 3, Work 2, Harm 2
    Disposition: cut - `test_1` now asserts that `tsc --strict` exits 0, so any type error fails the test.
