# The board shows a team what moves, what needs them and when it ships, at a glance

5 parts · Risks: none one-way · New moving parts: a local web server that forge board starts (item 1)

## What changes for you

- `forge board` opens a live page on your laptop. It refreshes by itself, and only your laptop
  can open it.
- The first screen fits a laptop window with no scrolling: what needs you on top, every item in
  flight as a one-line card in five stages (planned, building, review, ready, merged), the
  stories with their parts and owners on the right, and four numbers at the bottom.
- A Team view for the manager and a Me view for a developer: the same screen, filtered to your
  items, with your live runs beside it.
- Click any item to see its detail beside the cards. Its full page shows its history, how long
  each round took, the problems kept for later and, for a story, its plan as a readable document.
- A manager gives a story to a developer from the board.
- Releases shows what the next release carries and past releases. Insights shows the team's work
  per week, with each person as a share of the team, never ranked.
- The page shows no commands. It says unknown where Forge has no record. It reads in light and
  dark.

## Why

The owner found the current board unusable: one long page, mostly a dependency tree, too much
text. On 15 October 2026 the owner approved a new design (the Forge Board Design canvas): a
needs-you strip and a pipeline of one-line cards, detail on demand, Releases and Insights pages,
and assignment on the board. The facts it shows come from the previous story.

## Done when

1. **`forge board` opens a live page on this laptop that refreshes by itself, and only this laptop can open it.**
2. **In a 1440 by 900 window the first screen shows, without scrolling, what needs you, every item in flight by stage, the stories with their parts and owners, and four figures, in about 120 words.**
3. **Clicking an item opens its detail beside the cards, and its full page shows its history, round times, kept problems and, for a story, its plan as a readable document.**
4. **A manager gives a story to a developer from the board, and every teammate's board shows the new owner once that change reaches the default branch.**
5. **Releases shows the next and past releases from the repo's tags, and Insights shows merged work per week with each person as an unranked share of the team.**
6. **The page shows no commands, says unknown where Forge has no record, and reads in light and dark.**

## New and existing repos

- **New repos** (init or adoption): the new page from their first `forge board`. Tested on a
  repo made by `forge init`.
- **Existing repos** (on upgrade to this release): the same page as soon as they run the new
  release; `forge board --json` keeps its shape for the pane and other readers. Pages for
  past work show what the previous story backfilled, and unknown for the rest. Tested on the
  adopted earlier-release fixture moved to this release.

## Risks

Risks: none one-way. The server binds to the local machine only, holds no state of its own and
stops with the command. Assigning runs the previous story's command and goes through the story's
pull request. Every part reverts with its pull request.

## For the builders

### Done-when details

1. `forge board` starts a server on 127.0.0.1 at a free port with a per-run token in the page
   address, opens the browser, and serves the page plus `/board.json` (the same derivation as
   `forge board --json`). The page polls it every 10 seconds while visible. The command stops
   the server on exit. `forge board --json` and `--out` keep working. Tests: the server answers
   only on 127.0.0.1 and only with the token; the JSON matches `forge board --json`.
2. Layout and components follow the canvas: header (Now, Releases, Insights; Team/Me), needs-you
   strip of attention cards, five pipeline columns of item chips with wait strips, a stories
   rail with part bars, owners and story-to-story nesting, and four figures. The stage mapping:
   Planned = unstarted, started, Not started, Waiting; Building = working, fixing, checks failed;
   Review = reviewing, waiting for checks, hotspot; Ready = ready; Merged = a count plus the last
   five. Fixes share the pipeline; an All · Story parts · Fixes switch filters it. Tests: a browser
   check at 1440 by 900 on the client-sized fixture with no vertical scroll, and a word count.
3. The drawer (480 px) and the full item page (tabs Overview, Plan, Rounds, Known issues). Plan
   renders `plans/<KEY>.md` from title to "## For the builders", with that section folded; the
   page reads the file from git. Tests: open a part, a fix and a story; the plan renders headings,
   lists and the folded section.
4. The Assign control on a story and in its drawer calls the server, which runs `forge assign`.
   Tests: assign from the page in a test repo and read the Developer column.
5. Releases: next release (items since the last tag, readiness from Forge's facts only), past
   releases, known issues by file. Insights: lifetime figures, merged per week stacked by person
   in alphabetical order, a row per person with open items and stories owned. Tests: a repo with
   tags and one without.
6. No command text anywhere; unknown shown as the word; light and dark tokens from the design
   language; keyboard reachable; AA contrast. Tests: a page scan for command text and an axe check.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing | Developer |
|---|---|---|---|---|---|---|---|---|
| SERVER | The local live page | server, token, `/board.json`, refresh, the page shell and design tokens | 1, 6 | src/forge/board_server.py, src/forge/board_app/shell.html, src/forge/board_app/tokens.css, src/forge/board.py | tests/test_board_server.py | | yes | |
| NOW | The first screen | needs-you strip, pipeline, stories rail, figures, Team and Me | 2 | src/forge/board_app/now.js, src/forge/board_app/now.css | tests/test_board_now_screen.py | SERVER | yes | |
| DETAIL | Drawer and full item page | drawer, item page tabs, plan rendering | 3 | src/forge/board_app/item.js, src/forge/board_app/item.css | tests/test_board_item_page.py | SERVER | yes | |
| PAGES | Releases and Insights | the two pages | 5 | src/forge/board_app/releases.js, src/forge/board_app/insights.js | tests/test_board_releases_insights.py | SERVER | yes | |
| ASSIGNUI | Assign on the board | the Assign control and its server route | 4 | src/forge/board_app/assign.js, src/forge/board_server.py | tests/test_board_assign_ui.py | NOW, DETAIL | yes | |

New moving parts: a local web server started by `forge board`, bound to 127.0.0.1 (item 1)

## Notes

- Waits for FORGE-BOARD-3 for owners, round times, known issues and releases; until those
  land, those regions show unknown.
- The old HTML board and its renderers are removed in SERVER once the new page serves the same facts.
- Design reference: the Forge Board Design canvas (design language, Now team and me views,
  drawer, full item page, Insights, Releases).
