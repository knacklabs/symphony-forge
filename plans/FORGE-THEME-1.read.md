---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-10T17:52:29.996297+00:00
seconds: 694.984
read_hash: fb14604663e7b79c01c04eb14208c7377d93602c
round: 1
passed: no
doc_seen: fb14604663e7b79c01c04eb14208c7377d93602c
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
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
