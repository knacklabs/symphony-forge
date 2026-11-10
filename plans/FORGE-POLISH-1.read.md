---
reader: codex (gpt-6.1-terra)
read_at: 2026-11-10T17:49:41.634466+00:00
seconds: 692.095
read_hash: 18b7e28836abe24f519fbf73c036fa0e5a65f458
round: 1
passed: no
doc_seen: 18b7e28836abe24f519fbf73c036fa0e5a65f458
spec_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
notes_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
answers_seen: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
conversation: 01a1c689-ebd7-7ec3-848b-4e27b918dfb1
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

1. Blocking: Not done: Several starter controls bypass the shared motion speed and curve.  
   Raise: Not done  
   Case: normal use - Open a dialog or sidebar, or press a checkbox.  
   The [dialog](/src/forge/templates/starter/libs/shared/ui/src/components/ui/dialog.tsx:64) retains `duration-200`, the [sidebar](/src/forge/templates/starter/libs/shared/ui/src/components/ui/sidebar.tsx:232) retains `duration-200 ease-linear`, and the [checkbox](/src/forge/templates/starter/libs/shared/ui/src/components/ui/checkbox.tsx:14) transitions only its shadow. The [plan](/plans/FORGE-POLISH-1.md:70) leaves those overrides in place; its test can pass without checking their motion.  
   Gain 3, Work 2, Harm 3
   Disposition: cut: Done-when 1 and its details now list every motion class in components/ui, change dialog, alert-dialog, sheet and sidebar to the shared speed and curve, move the checkbox transition to a list with scale, name the checkbox tick and sonner as the two left out, and test_1 fails on a literal duration, ease-linear or ease-in-out.

2. Blocking: Not done: The theme rule cannot reduce animations made with the Web Animations API.  
   Raise: Not done  
   Case: normal use - A later screen opens a panel using the Web Animations API, which the [frontend rules](/src/forge/templates/conventions/frontend.md:148) permit.  
   The [plan](/plans/FORGE-POLISH-1.md:75) changes CSS animation and transition durations. That does not change the timing of an animation created by JavaScript, despite the promise that one theme rule covers later screens.  
   Gain 3, Work 2, Harm 3
   Disposition: cut: the plan now says what the one rule covers (style sheet animations and transitions) and what it does not (script animation), adds a frontend rule and a review rule that script animation reads the device setting, and states the limit in What changes for you, Done-when 2 and Risks.

3. Blocking: Not done: The reduced-motion check misses sliding panels made with transitions.  
   Raise: Not done  
   Case: normal use - An earlier-adopted app without a reduced-motion rule adds a panel using `transition-transform`.  
   The [planned check](/plans/FORGE-POLISH-1.md:85) looks for keyframes, `animation:` and `animate-` classes, but deliberately skips transitions. The starter itself uses transitions to move its [sidebar](/src/forge/templates/starter/libs/shared/ui/src/components/ui/sidebar.tsx:232), so this animation passes without the promised refusal.  
   Gain 3, Work 2, Harm 3
   Disposition: cut: the reduced-motion close check is removed. The one rule already shortens transitions, including the sidebar's, and the review reports new motion that ignores reduced motion, so no pattern has to tell a moving transition from a colour change.

4. Blocking: Not done: The pressed-state check misses supported button files and controls.  
   Raise: Not done  
   Case: normal use - A change adds an HTML button or touches the shared select control.  
   The [planned check](/plans/FORGE-POLISH-1.md:84) only checks JSX and TSX and does not name Radix select triggers. Close already accepts [HTML, Vue and Svelte files](/src/forge/ui_checks.py:15), and the starter’s [select trigger](/src/forge/templates/starter/libs/shared/ui/src/components/ui/select.tsx:26) renders a button without an `active:` class. The prescribed scan of the starter must nevertheless report no motion problem.  
   Gain 3, Work 2, Harm 3
   Disposition: cut: the pressed-state close check is removed and becomes a review rule in review.md and brief.md, so the HTML, Vue and Svelte buttons and the select trigger are no longer promised a refusal, and the starter scan no longer claims to pass it.

5. Blocking: A button with a working pressed style can be refused.  
   Raise: Functional  
   Case: normal use - An adopted React app defines a button’s `:active` style in its CSS file.  
   The [planned check](/plans/FORGE-POLISH-1.md:84) requires the JSX or TSX file itself to contain `active:`. It refuses the button even though its separate stylesheet supplies the pressed state, and tells the worker to add a state that already exists.  
   Gain 3, Work 2, Harm 3
   Disposition: cut: with no close check there is no refusal of a correct button; the review text says it reads the style sheet before it reports a missing pressed state.

6. Blocking: The motion checks also block design work before a story is read.  
   Raise: Functional  
   Case: normal use - An earlier-adopted app without a reduced-motion rule creates an animated HTML design.  
   The [plan](/plans/FORGE-POLISH-1.md:82) adds the rules to the shared script, but [design checking](/src/forge/design.py:124) and the [design renderer](/src/forge/templates/design/support.js:17) also run that script on artboards. They can refuse the design before close, although the plan says the first check comes with the next UI change.  
   Gain 3, Work 2, Harm 3
   Disposition: cut: the plan states that motion-all also runs on design drafts through the plan read and the canvas renderer, as every other rule in the script does, adds no machinery, and says the waiver comment works there; the first-check wording for existing apps now covers only touched UI files.

7. Blocking: Not done: Close skips all three checks when Node is unavailable.  
   Raise: Not done  
   Case: normal use - An adopted Python app with HTML or CSS is closed on a machine without Node.  
   [ui_checks.py](/src/forge/ui_checks.py:19) returns no problems when Node is missing, and the [current worker brief](/src/forge/templates/brief.md:570) documents that skip. The [plan](/plans/FORGE-POLISH-1.md:86) leaves that code unchanged while promising a refusal.  
   Gain 3, Work 2, Harm 3
   Disposition: cut: the plan states that without Node the script prints its one line and skips, as brief.md documents today, promises no refusal there, and the owner text and Risks say so. The promised refusal is now limited to computers with Node.

8. Blocking: Existing apps are told to import state components they do not receive.  
   Raise: Not done  
   Case: normal use - An earlier-adopted app with its own frontend layout adds a data-loading screen.  
   The [plan](/plans/FORGE-POLISH-1.md:79) requires the new shared-package import, but [sync supplies only rules and checks](/plans/FORGE-POLISH-1.md:93). Older apps need not have that package or alias; the [current convention](/src/forge/templates/conventions/frontend.md:36) says they keep their own folders.  
   Gain 3, Work 2, Harm 3
   Disposition: cut: states.tsx is used only where an app has it; an app without it keeps its own markup. The frontend subsection points to the finished files in Forge's starter folder beside the conventions, to copy on a change or request, so no second copy of the source exists. test_5 checks the named starter paths exist.

9. Blocking: The reduced-motion test can pass while the loading placeholder keeps pulsing.  
   Raise: Test  
   Case: normal use - A person enables reduced motion and opens a loading screen.  
   [test_2](/plans/FORGE-POLISH-1.md:75) checks that a media block exists, but not that it shortens animations or applies to the placeholder. The built-CSS assertion also checks only for the media query; the existing [skeleton](/src/forge/templates/starter/libs/shared/ui/src/components/ui/skeleton.tsx:7) keeps `animate-pulse`.  
   Gain 3, Work 1, Harm 3
    Disposition: cut: test_2 now asserts the media block's declarations, and a starter browser test (motion.spec.ts) reads the pulse's computed duration under reduced motion (0.001s) and without it (2s), plus the shared curve and speed; the nightly run requires the spec's case name.

10. Blocking: The state-component test can pass when all three components render nothing.  
    Raise: Test  
    Case: normal use - A screen renders its loading, empty or error state.  
    [test_3](/plans/FORGE-POLISH-1.md:77) checks names and imports, but does not exercise the components, their labels, message, action or retry. The [starter entry point](/src/forge/templates/starter/apps/web/src/main.tsx:8) renders no screen, so its build does not demonstrate those states either.  
    Gain 3, Work 2, Harm 3
    Disposition: cut: a vitest test in the starter (shared-states.test.tsx) renders each state part and asserts role, text, action and the retry call; test_3 checks the files and the roles named in the source. The plan states that the behaviour runs in the starter's own web tests, not in Forge's per-pull-request tests, and lists that in Risks and Not verified.
