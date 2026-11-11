---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-11T02:26:15.914492+00:00
seconds: 287.105
read_hash: b34cc10d461b81ed9ae8cc6a8a35bc07398860c2
round: 4
passed: yes
doc_seen: b34cc10d461b81ed9ae8cc6a8a35bc07398860c2
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: 3bf4d0a6598af721f6e7e7ac0b254f261d74e4a4
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1c68c-71c0-7f11-be78-6c5527a290a1
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

1. Blocking: Plan gap: The first task requires proof from a check that the second task has not built.
   Raise: Plan gap. [The plan](/plans/FORGE-THEME-1.md:99) requires that proof in DESIGN’s pull request, but CHECK follows DESIGN. Forge requires the earlier task to pass review before a later task can build on it ([task.py](/src/forge/task.py:580)).
   Case: normal use - The worker closes DESIGN. Even after CHECK exists, removing the copy after applying the changed colour leaves a non-stock theme, which the proposed rule allows.
   Gain 4, Work 2, Harm 2
Disposition: cut - DESIGN no longer claims a close proof; its proof is the fixture equal to the starter (`test_1`) plus the manual run, and the close proof moved to CHECK's `test_3`, which uses the same fixture as the approved copy.

2. Blocking: Plan gap: The guide does not establish how to select the right client’s design system.
   Raise: Plan gap. [The plan](/plans/FORGE-THEME-1.md:94) says naming the system selects it, but also says the design tool uses a default and leaves selection unresolved ([Notes](/plans/FORGE-THEME-1.md:145)). The current design record retrieves a design link, not a system selection ([design.py](/src/forge/design.py:159)).
   Case: normal use - Sales works with several clients and the agent returns to a client whose system is not the default.
   Gain 4, Work 2, Harm 3
Disposition: cut - the link to the client's design system is written once in `docs/design/design-system.md` in the same change that makes the system, and the agent opens that link before it designs, copies a theme or revises the parts; no reliance on the default system. Whether the design tool can build a canvas from a chosen system stays in Notes as unverified.

3. Blocking: Not done: Item 4 misidentifies which themes are stock.
   Raise: Not done. [The stock rule](/plans/FORGE-THEME-1.md:106) compares declarations in `:root` and `.dark`, but the starter’s font is in `@theme inline` ([index.css](/src/forge/templates/starter/apps/web/src/index.css:40)); the new size, spacing and shadow values also sit in `@theme`.
   Case: normal use - A client changes only the font, yet the check rejects the theme as stock. Conversely, an unrelated layout variable added to `:root` makes the unchanged gray theme pass.
   Gain 3, Work 2, Harm 3
Disposition: cut - the stock rule now reads the starter's contract declarations (every literal value, in every block) and the app is stock only when none of them is changed; a font-only change is not stock, an unrelated `:root` variable changes nothing, and an older file without the 12 new lines is still stock.

4. Blocking: Not done: Item 4 misses screen changes made only in a stylesheet or HTML file.
   Raise: Not done. [The proposed rule](/plans/FORGE-THEME-1.md:106) triggers only for `.tsx` and `.jsx`; the existing design checker also handles CSS and HTML ([ui_checks.py](/src/forge/ui_checks.py:15)).
   Case: normal use - A change edits an existing screen’s CSS while the app still has the gray starter theme and no approved copy. The stock check does not run.
   Gain 3, Work 2, Harm 3
Disposition: cut - a screen change is now any changed file under the app folders with the suffixes and exclusions the existing design checks use (`.tsx`, `.jsx`, `.html`, `.css`, `.vue`, `.svelte`; not tests or `components/ui/`), so a stylesheet-only or HTML change counts; a design canvas under `docs/design/` does not.

5. Blocking: Not done: Item 3 skips existing theme drift during a screen change.
   Raise: Not done. [The plan](/plans/FORGE-THEME-1.md:103) explicitly skips comparison when neither theme file changed, although the approved result says the final check reports each difference. Close supplies the changed-file list from the branch diff ([close.py](/src/forge/close.py:278)).
   Case: normal use - An earlier-adopted app already has a saved theme copy that differs from its app theme; its next screen-only change passes without reporting that drift.
   Gain 3, Work 2, Harm 3
Disposition: cut - the drift comparison now also runs whenever such a UI file changes, as well as when the theme file or the copy changes; the existing-app screen-only case is in `test_3`.

6. Blocking: Plan gap: A drift waiver cannot identify the value it sets aside.
   Raise: Plan gap. [The waiver format](/plans/FORGE-THEME-1.md:96) names only `theme-drift`, while all token findings point to the same file. The existing waiver mechanism suppresses a rule across a file ([ui-checks.js](/src/forge/templates/design/ui-checks.js:24)).
   Case: normal use - A team accepts one colour exception, then later introduces an unintended difference in another token. The recorded waiver gives the check no way to distinguish them.
   Gain 3, Work 2, Harm 3
Disposition: cut - a drift waiver names its token (`forge-ui-ignore theme-drift --primary: <reason>`) and sets aside that token only, and a second differing token is still refused; `theme-stock` has no token and keeps its rule-level waiver.

7. Blocking: Not done: Item 2 does not create the approved copy when Claude tools return.
   Raise: Not done. [The fallback](/plans/FORGE-THEME-1.md:97) makes a system from the app and switches the source to Claude, but the copy step is tied to the earlier design approval ([plan](/plans/FORGE-THEME-1.md:95)).
   Case: normal use - A design is approved without Claude tools, then the tools return. No copy is created until a later Claude theme change, so intervening app theme changes have no copy to check.
   Gain 3, Work 1, Harm 3
Disposition: cut - the no-tools path now ends with the approved copy: when the system is made after the tools return, the same change saves its `tokens.json` as the approved copy, writes the system link, and removes the not-made-yet line.

8. Blocking: Not done: Item 2 copies font names without ensuring the app can load the fonts.
   Raise: Not done. [The transfer instructions](/plans/FORGE-THEME-1.md:95) write token values into CSS; the starter supplies a system-font list and no client font asset ([index.css](/src/forge/templates/starter/apps/web/src/index.css:40)). The manual proof exercises a colour, not a font.
   Case: normal use - Sales selects a client font that is absent from a viewer’s computer. The copied family name falls back to another font, while the theme comparison passes.
   Gain 3, Work 2, Harm 3
Disposition: cut - the starter loads no font today (checked: no font link, no `@font-face`, a system font list), so the guide now has a fonts step: a font file from the system is copied to the app's public fonts folder with an `@font-face` rule, a hosted family gets its stylesheet link in the page head, and a font the app cannot load is not copied; the token's difference is then set aside with a named waiver and the person is told. One pinned-phrase case in `test_2`; no font check in code, because a font name alone cannot be proven loaded in a few exact lines.

9. Blocking: Plan gap: The brand-guide instructions both require and forbid existing design rules.
   Raise: Plan gap. [The plan](/plans/FORGE-THEME-1.md:93) permits only rules from the frontend convention and the five client facts, but also requires one main action and the looks to avoid. Those rules are in [app-baseline](/.codex/skills/app-baseline/SKILL.md:25), not the named [frontend convention](/src/forge/templates/conventions/frontend.md:1).
   Case: normal use - A new client’s five facts do not independently state those Forge rules, so the builder cannot follow both instructions.
   Gain 4, Work 1, Harm 2
Disposition: cut - fixed by the coordinator: the brand-guide rules now come from three existing sources (the frontend convention, the app-baseline skill and the five facts), and the text no longer forbids the rules it requires.

## Round 2

10. Blocking: Plan gap: The stock-theme test now requires the result that finding 3 rejected.
   Raise: Plan gap. [The new rule](/plans/FORGE-THEME-1.md:111) says an unrelated variable leaves the gray theme stock; [the test case](/plans/FORGE-THEME-1.md:112) says the same screen change passes.
   Case: normal use - A screen change adds an unrelated layout variable while the theme remains gray. The rule and its test require opposite results.
   Gain 3, Work 1, Harm 3
Disposition: cut - the stock-theme close rule, its code, waiver, test and risk are removed (owner decision, 10 Nov 2026: make it a review rule); Done-when 4 is now a review line, widening `review.md:80`, tested on a new and an earlier-adopted repo.

11. Blocking: Not done: Item 2’s return-to-Claude step fails for earlier-adopted apps.
   Raise: Not done. [The new step](/plans/FORGE-THEME-1.md:102) saves the complete copy and says the app theme needs no edit. But an earlier starter lacks the 12 new names ([plan](/plans/FORGE-THEME-1.md:111)), and the check reports every copy token missing from the app ([plan](/plans/FORGE-THEME-1.md:107)).
   Case: normal use - An earlier-adopted app uses the no-tools path, then creates its Claude system. Saving the copy causes close to refuse the missing theme values.
   Gain 5, Work 3, Harm 3
Disposition: cut - the return-to-Claude step now adds each contract line the theme file lacks (the 12 added lines and the heading rule), with the value the system holds, in the same change; `test_3` has an earlier-adopted case that is refused as missing and then passes.

12. Blocking: Plan gap: The replacement proof requires a changed theme to equal the stock theme.
   Raise: Plan gap. [The new manual proof](/plans/FORGE-THEME-1.md:104) changes a colour, saves that theme, and says `test_1` shows the saved values equal the starter. [Item 1](/plans/FORGE-THEME-1.md:92) also requires the real fixture’s values to equal the starter.
   Case: normal use - The DESIGN worker follows the replacement proof for finding 1. The saved changed colour and the unchanged starter cannot both have the same value.
   Gain 5, Work 1, Harm 2
Disposition: cut - the fixture is saved before any change on the page and equals the starter; the changed-colour run goes only into a scratch app and is not committed.

13. Advisory: Not done: A waiver for one colour value also hides the other theme’s value.
   Raise: Not done. The revised promise says a comment names one value ([plan](/plans/FORGE-THEME-1.md:10)), but the new rule explicitly waives both light and dark for that token ([plan](/plans/FORGE-THEME-1.md:107)).
   Case: normal use - A team accepts a light-mode primary-colour difference; an unintended dark-mode difference for the same token is also hidden.
   Gain 3, Work 3, Harm 3
Disposition: cut - a drift waiver now names the token and the theme (`--primary (light)`), so the other theme and other tokens stay reported; the case is in `test_3`.

14. Advisory: Functional: An imported custom theme is reported as the stock theme.
   Raise: Functional. [The revised stock rule](/plans/FORGE-THEME-1.md:111) treats every missing declaration as unchanged and reads only `index.css`. The starter already uses CSS imports ([index.css](/src/forge/templates/starter/apps/web/src/index.css:1)).
   Case: normal use - An earlier-adopted app keeps its custom colours in a stylesheet imported by `index.css`. Its next screen change is refused as gray even though its theme is custom.
   Gain 3, Work 3, Harm 3
Disposition: cut - the stock-theme close rule this note was about no longer exists.

15. Advisory: Functional: The font instructions misclassify browser-provided font families.
   Raise: Functional. [The new font step](/plans/FORGE-THEME-1.md:100) requires a copied font to come from a system file or hosted stylesheet. The starter itself uses browser-provided families such as `system-ui` and `sans-serif` ([index.css](/src/forge/templates/starter/apps/web/src/index.css:40)).
   Case: normal use - Sales selects a generic family such as `serif` for headings. The guide treats it as unavailable even though the browser can render it without either source.
   Gain 3, Work 3, Harm 2
Disposition: cut - one line in the fonts step: a generic browser family (`serif`, `sans-serif`, `system-ui`, `monospace`) needs no file or link and is copied as it is.

16. Advisory: Functional: A test-helper change can trigger the screen check.
   Raise: Functional. [The revised file filter](/plans/FORGE-THEME-1.md:107) excludes `tests/` and `__tests__/` but omits `test/`; the existing checker excludes all three ([ui-checks.js](/src/forge/templates/design/ui-checks.js:10)).
   Case: normal use - A client edits a React test helper such as `apps/web/test/provider.tsx` while the starter theme is unchanged. Close treats it as a screen change and refuses it.
   Gain 3, Work 3, Harm 2
Disposition: cut - the screen-file rule now excludes `tests/`, `test/` and `__tests__/`, as the existing checker does.

## Round 3

17. Advisory: Not done: Prototype reviews do not receive the new stock-theme rule.
    Raise: Not done. The plan adds the rule to [review.md](/plans/FORGE-THEME-1.md:109), but unsigned prototype fixes use [review-light.md](/src/forge/review.py:344), which says not to audit style.
    Case: normal use - A prototype screen is built on the starter theme without an approved copy. Its reviewer is not given the rule that would report it.
    Gain 3, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)

18. Advisory: Plan gap: Item 4’s test is assigned to two files.
    Raise: Plan gap. [The general test instructions](/plans/FORGE-THEME-1.md:46) place `test_4` in `test_theme_check.py`, while [item 4](/plans/FORGE-THEME-1.md:111) and the DESIGN task place it in `test_theme_guide.py`. Adding both would fail the [one-test-per-rule check](/tests/test_rules.py:49).
    Gain 3, Work 1, Harm 2
   Disposition: keep - below the bar (follow-up)

19. Advisory: Test: The review-rule test can pass with its condition reversed.
    Raise: Test. [Item 4’s test](/plans/FORGE-THEME-1.md:110) pins only `untouched starter theme` and `docs/design/tokens.json`. A prompt telling the reviewer to report the theme only **when the copy exists** contains both phrases but misses the promised no-copy case.
    Gain 3, Work 1, Harm 2
   Disposition: keep - below the bar (follow-up)

20. Advisory: Plan gap: The worker instruction forbids an approved neutral theme.
    Raise: Plan gap. [The review rule](/plans/FORGE-THEME-1.md:109) applies when the approved copy is absent, but the worker is told to build no screen on the starter’s neutral theme without that condition.
    Case: normal use - A client approves the neutral theme and the agent saves its copy. The worker instruction still forbids building the screen with the approved theme.
    Gain 3, Work 1, Harm 2
   Disposition: keep - below the bar (follow-up)

## Round 4

21. Advisory: Plan gap: A trial theme change can replace the approved copy before Sales accepts it.
    Raise: Plan gap. [The feedback loop](/plans/FORGE-THEME-1.md:94) asks the agent to show each revision again, but [the copy rule](/plans/FORGE-THEME-1.md:97) says to copy every later Claude theme change into the app and approved copy. Forge’s current [design source](/src/forge/design.py:159) records a link, not approval of each theme revision.
    Case: normal use - Sales asks for a warmer look after approval and rejects the first revision. The copy rule can make that trial the approved copy before Sales says yes.
    Gain 3, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)

22. Advisory: Plan gap: The guide does not tell the agent to choose a first look for an earlier-adopted stock app.
    Raise: Plan gap. [The owner-facing change](/plans/FORGE-THEME-1.md:8) says the agent decides each client’s theme from five facts. [The guide](/plans/FORGE-THEME-1.md:94) starts an existing client from its current theme but specifies better first values only for a new client.
    Case: normal use - An earlier-adopted app still has the [starter’s neutral colours](/src/forge/templates/starter/apps/web/src/index.css:50). Its first system can be shown in gray without the agent making the promised five-fact choice.
    Gain 3, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)

23. Advisory: Test: The guide test does not pin the new agent-led feedback flow.
    Raise: Test. [Item 2’s test](/plans/FORGE-THEME-1.md:103) lists no assertion that the agent chooses the values, asks only for missing facts, or makes the changes Sales requests. The [existing look test](/tests/test_uistandards_words.py:43) also checks the fact names rather than who chooses the theme.
    Case: normal use - The delivered guide retains the previous instruction for Sales to change values on the page; the listed assertions can still pass.
    Gain 3, Work 3, Harm 3
   Disposition: keep - below the bar (follow-up)
