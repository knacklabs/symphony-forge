# The board shows a team what moves, what needs them and when it ships, at a glance

6 parts · Risks: none one-way · New moving parts: a local web server that forge board starts (item 1)

## What changes for you

- The board opens as a live page on your laptop. It refreshes by itself, and only your laptop
  can open it.
- The first screen fits a laptop window with no scrolling: what needs you on top, the items in
  flight as one-line cards in five stages (planned, building, review, ready, merged), the
  stories with their parts and owners on the right, and four numbers at the bottom. A stage
  with more cards than fit shows a count of the rest.
- A Team view for the manager and a Me view for a developer: the same screen, filtered to the
  items you own or started, with your live runs beside it.
- Click any item to see its detail beside the cards. Its full page shows its history, how long
  each round took, the problems kept for later and, for a story, its plan as a readable document.
- A manager gives a story to a developer from the board. If Forge refuses, the board says why.
- Releases shows what the next release carries and past releases. Insights shows the team's work
  per week, with each person as a share of the team, never ranked.
- The board's own words show no commands, say unknown where Forge has no record, work from the
  keyboard, and read in light and dark.

## Why

The owner found the current board unusable: one long page, mostly a dependency tree, too much
text. On 15 October 2026 the owner approved a new design: a needs-you strip and a pipeline of
one-line cards, detail on demand, Releases and Insights pages, and assignment on the board. The
approved design is the source of truth for how each screen looks. The facts it shows come from
the previous story.

## Done when

1. **The board opens a live page on this laptop that refreshes by itself, and only this laptop can open it.**
2. **In a 1440 by 900 window the first screen shows, without scrolling, what needs you, the items in flight by stage with a count where a stage is too long, the stories with their parts and owners, and four figures, in about 120 words.**
3. **Clicking an item opens its detail beside the cards, and its full page shows its history, round times, kept problems and, for a story, its plan as a readable document.**
4. **A manager gives a story to a developer from the board, the board says why when Forge refuses, and every teammate's board shows the new owner once that change reaches them.**
5. **Releases shows the next and past releases from the repo's tags, and Insights shows merged work per week with each person as an unranked share of the team.**
6. **The board's own words show no commands, say unknown where Forge has no record, work from the keyboard, and read in light and dark.**

## New and existing repos

- **New repos** (init or adoption): the new page from their first board. Tested on a repo made
  by `forge init`.
- **Existing repos** (on upgrade to this release): the same page as soon as they run the new
  release; the board's JSON keeps its shape for the pane and other readers. Pages for past work
  show what the previous story backfilled, and unknown for the rest. Tested on the adopted
  earlier-release fixture moved to this release.

## Risks

Risks: none one-way. The server binds to the local machine only, holds no state of its own and
stops with the command. Assigning runs the previous story's command and goes through the story's
branch. Every part reverts with its pull request.

## For the builders

Design: the approved artboards are in `docs/board-design/` (Main = design language, Manager =
Now team view, Developer = Now me view, Drawer, Item = full page with the Plan tab, Insights,
Releases). Each has a 1440 by 900 reference image beside it (`<name>.png`); `support.js` there
renders the `.dc.html` sources in any browser, so the images can be regenerated with headless
Chrome. They are the source of truth: tokens, type scale, spacing, components and layout come
from them. Acceptance for items 2, 3 and 5: screenshots at 1440 by 900 of each screen on the
client-sized fixture, set beside the matching artboard in the pull request, with every
difference listed. Sample data in the artboards is not a requirement; Forge's facts are.

### Done-when details

1. `forge board` starts a server on 127.0.0.1 at a free port, with a per-run token in the page
   address, opens the browser, and stops the server when the command ends. Routes: the page,
   `/board.json`, `/plan/<KEY>` (added in SERVER), `/assign` (added in ASSIGNUI). Every route
   checks the token. `/board.json` is the untrimmed derivation (the one the HTML board uses
   today), built fresh on every request with no cache kept between requests; the server fetches
   from the remote at most once a minute. The page polls every 10 seconds while visible. The page
   sends a Content-Security-Policy that allows only its own scripts and styles. `forge board --json`
   and `--out` keep working. Tests: the server answers only on 127.0.0.1 and only with the token;
   a change to the repo between two polls appears in the second; a teammate's pushed assignment
   appears after the next fetch.
2. Shell interfaces, pinned by SERVER with stubs and one test that crosses them:
   `Board.onSnapshot(fn)`, `Board.select(itemId)`, `Board.openDrawer(itemId)`,
   `Board.openItem(itemId)`, `Board.navigate(page)` and `Board.api.assign(key, login) ->
   {ok, message}`. Now screen: header (Now, Releases, Insights; Team and Me); needs-you strip of
   attention cards (verb from the needs-you reason: approve, decide, answer, merge); five
   stages: Planned = unstarted, started, Not started, Waiting, Can start now (tagged "can
   start"); Building = working, fixing, checks failed; Review = reviewing, waiting for checks,
   hotspot; Ready = ready; Merged = a count plus the last five. A stage shows at most six cards,
   then "and N more"; the stories rail shows at most five stories, then "and N more". Each
   "and N more" is a button that opens the full list of that stage or of the stories in the
   drawer area, from mouse and keyboard, so every item stays reachable. Fixes share
   the pipeline; an All, Story parts, Fixes switch filters it. Four figures: merged in the last 7
   days (`counts.finished_last_7_days`), median time of items merged in the last 7 days, the
   share of their time spent waiting for a person, and items with failing checks. Cost stays
   hidden until token records exist. Me = items whose owner or developer login is the viewer, plus
   items the viewer started. Tests: a browser check at 1440 by 900 on the client-sized fixture
   with no vertical scroll, the overflow counts, opening an "and N more" list and reaching its
   last item, a "can start" card, and a word count of about 120 excluding numbers. Figures are
   checked against a fixture with known values: three items merged in the last 7 days taking
   1, 2 and 9 hours show a median of 2 h, and their waiting-for-person seconds give the exact
   share shown.
3. The drawer (480 px) and the full item page (tabs Overview, Plan, Rounds, Known issues). Plan
   shows `/plan/<KEY>`: the doc from its title to "## For the builders", that section folded,
   read from the same ref Forge's story commands read. Markdown renders through an inert
   renderer: all HTML in the doc is shown as text, links are kept only for http and https, and
   nothing in the doc runs. Tests: open a part, a fix and a story; the plan renders headings and
   lists; a plan holding an `<img onerror>` and a `javascript:` link renders them as inert text.
4. The Assign control on a story and in its drawer calls `Board.api.assign`, which posts to
   `/assign`; the server runs `forge assign` and returns its reason: the refusal's first sentence, with any
   `Next:` line and any command text removed. A refusal (for example a story with no plan)
   shows that reason beside the control and changes nothing. Tests: assign
   from the page in a test repo and read the owner; assign a story with no plan and see the
   refusal with no command text in it; a second clone sees the owner after it fetches.
5. Releases: next release (items merged since the last release, from the untrimmed derivation
   so older unreleased items are included), readiness from Forge's facts only, past releases, and
   known issues by file. Insights: merged per week stacked by person in alphabetical order, and a
   row per person with open items and stories owned. Tests: a repo with tags, one without, and an
   unreleased fix merged eight weeks ago that appears in the next release.
6. The board's own text, everything except the rendered plan, has no command text; unknown shows
   as the word; light and dark tokens come from the design language. Every card, tab, switch and
   the Assign control is reachable with Tab, opens with Enter and closes with Escape. Tests: a
   page scan for command text outside the plan tab, an axe check, and a keyboard walk that opens
   a card's drawer, its full page and the Assign control.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| SERVER | The local live page | server, token, CSP, fresh `/board.json`, `/plan/<KEY>`, the shell, design tokens and the pinned `Board` interfaces with stubs | 1 | src/forge/board_server.py, src/forge/board_app/shell.html, src/forge/board_app/tokens.css, src/forge/board_app/app.js, src/forge/board.py | tests/test_board_server.py | | yes | |
| NOW | The first screen | needs-you strip, pipeline, stories rail, figures, Team and Me | 2, 6 | src/forge/board_app/now.js, src/forge/board_app/now.css | tests/test_board_now_screen.py | SERVER | yes | |
| DETAIL | Drawer and full item page | drawer, item page tabs, inert plan rendering | 3, 6 | src/forge/board_app/item.js, src/forge/board_app/item.css, src/forge/board_app/markdown.js | tests/test_board_item_page.py | SERVER | yes | |
| PAGES | Releases and Insights | the two pages | 5, 6 | src/forge/board_app/releases.js, src/forge/board_app/insights.js | tests/test_board_releases_insights.py | SERVER | yes | |
| ASSIGNUI | Assign on the board | the Assign control, `/assign`, refusal messages | 4 | src/forge/board_app/assign.js, src/forge/board_server.py | tests/test_board_assign_ui.py | NOW, DETAIL, FORGE-BOARD-3/ASSIGN | yes | |
| CUTOVER | The old page goes | `forge board` serves only the new page; the old HTML board and its renderers are removed; the coordinator guide, both synced copies, docs/commands.md and docs/guide.md describe the live page | 1, 6 | src/forge/board.html, src/forge/board_visuals.py, src/forge/board_graph.py, src/forge/templates/skill.md, .claude/skills/forge/SKILL.md, .codex/skills/forge/SKILL.md, docs/commands.md, docs/guide.md, tests/ (only tests that cover the removed page) | tests/test_board_guide.py | NOW, DETAIL, PAGES, ASSIGNUI | yes | |

New moving parts: a local web server started by `forge board`, bound to 127.0.0.1 (item 1)

## Notes

- Waits for FORGE-BOARD-3 for owners, round times, known issues and releases; until those
  land, those regions show unknown.
- Deferred from the design: nesting a story under the story it waits on, and lifetime figures
  since adoption; both need facts no Done-when here covers.
