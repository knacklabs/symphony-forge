# Product

<!-- impeccable:product-schema 1 -->

Scope: the board surface: the page that `forge board` serves, the Claude Code pane, and later
Mainline's hosted team board. The owner confirmed the users, the page rules and the scope on
2026-10-14.

## Platform

web

## Users

- **Engineering manager (Owner).** Opens the board once or more each day, often cold. Must see
  in under a minute what is moving, what needs them (approvals, merges, decisions), what is stuck
  and why, when each story goes live, and what each story, task and fix cost in time and money.
  Must see load per person without a ranking of people.
- **Developer.** Opens the board while working. Must see their own items with what happens next,
  their live runs (laptop now, sandbox later), their pull requests and review findings, and who
  works on which files so they do not overlap with a teammate.
- A coordinating agent reads the same facts through `forge board --json` and `forge next`, not
  through the page.

## Product Purpose

Forge takes each change from an approved plan to a merged pull request. The board is where a
team sees that work: what happens now, what waits for a person, what is blocked, what it costs
and when it goes live. Success: a first-time manager answers "what is moving, what needs me,
what is stuck, when does it go live" correctly within one minute, and a developer sees what
happens next on each of their items.

## Positioning

Every number, state and time on the board comes from Forge's own records in git and the pull
requests, the same on every teammate's machine. Most of an item's time is waiting, and the board
shows the wait instead of hiding it.

## Operating Context

- `forge board` starts a small local web server and opens the page in the browser. The page
  refreshes live from the same data as `forge board --json`. Nothing loads from the internet.
- Read on a laptop only (1440 by 900 is the reference window). No phone layout.
- The Claude Code pane shows the same summary in plain text.
- Later, Mainline hosts the same board for a whole team, with every laptop and sandbox run live.
  The design must move there without a rewrite.

## Capabilities and Constraints

- Read-only: the page changes nothing in the repo.
- No commands on the page. Agents run Forge's commands; the board says in plain words what
  happens next, or what a person must decide.
- Local server only, bound to the person's own machine. No web fonts, CDN or external asset.
- The page shows what the JSON says and computes nothing of its own.
- Unknown shows as unknown, never as zero or a guess.
- Facts to show: stage and next step per item, needs-you, blocked or slow with the reason, live
  runs and lanes, review findings, checks, cost and time per story, task and fix (tokens, model
  cost, sandbox minutes, active versus waiting time), releases (what merged since the last
  release, whether the next one can go out, past releases), a go-live forecast per story, and
  deploy history once Mainline deploys exist.
- Dependencies at both levels: which stories wait on which stories, and which parts wait on
  which parts, across stories too.
- Terms: a story is a planned change written as one short doc (its plan); a part is one piece
  of a story's plan; a fix is a small change on its own.

## Brand Commitments

- Personality: calm, precise, trustworthy. Anti-goal: a generic SaaS dashboard.
- Plain English wherever a person looks: no IDs, hashes or jargon. The one exception is a
  story's own short key, shown small beside its title.

## Evidence on Hand

- Real board data from this repo (`forge board --json`) and a client-sized fixture built by the
  tests (`tests/fixtures/board.json`). No testimonials, customers or benchmarks exist; none may
  be invented.
- The earlier card-style board (before 13 October 2026) read better to the owner than the
  current one-long-page board, which is mostly a dependency tree.

## Product Principles

1. Answer each person's questions first; detail opens in place.
2. One derivation: the page shows what the JSON says.
3. Waiting is a fact worth seeing.
4. Plain words over labels and codes.
5. One page per question, not one page for everything.

## Accessibility & Inclusion

WCAG AA contrast in light and dark themes; colour never carries meaning alone; every drawing has
a text equivalent; everything works from the keyboard.
