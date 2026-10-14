# Product

<!-- impeccable:product-schema 1 -->

Scope: the board surface (`forge board`'s page and the Claude Code pane). Written by a builder
from the approved plan (plans/FORGE-BOARD-2.md) and AGENTS.md; no separate interview was held, so
every fact below is inferred from those two documents.

## Platform

web

## Users

- A project manager or team lead who opens the board cold and needs, within a minute: what is in
  progress, what needs a person, what is stuck and why, and when the planned work can go live.
- A developer or coordinating agent on the same team, checking what to pick up next.

## Product Purpose

Forge takes each change from an approved plan to a merged pull request. The board is the one
read-only page that tells a team where that work stands, from the same facts as
`forge board --json` and `forge next`. Success: a first-time viewer answers the four questions
above correctly (target 4 of 4 by 2026-11-15; the October 2026 baseline was 0 of 4).

## Positioning

Every number, state and time on the board comes from Forge's own records in git and the pull
requests, the same on every teammate's machine. Most of an item's time is waiting, and the board
shows it as waiting instead of hiding it.

## Operating Context

- Opened from a terminal with `forge board`, as one static file on the person's own machine.
- Read on a laptop (1440 by 900 is the reference window) and sometimes on a phone.
- The Claude Code pane shows the same summary lines in plain text.

## Capabilities and Constraints

- One self-contained HTML file: no script, no web fonts, no external asset, no image file.
- Read-only: the page changes nothing.
- Unknown is shown as unknown, never as zero or a guess.
- Terms: a story is a planned change written as one short doc (its plan); a part is one piece of
  a story's plan; a fix is a small change on its own.

## Brand Commitments

- Personality: calm, precise, trustworthy. Anti-goal: a generic SaaS dashboard.
- Plain English wherever a person looks: no IDs, hashes or jargon. The one exception is a story's
  own short key, shown small beside its title.

## Evidence on Hand

- Real board data from this repo (`forge board --json`) and a client-sized fixture built by the
  tests. No testimonials, customers or benchmarks exist; none may be invented.

## Product Principles

1. Answer the team's questions first; detail opens in place.
2. One derivation: the page shows what the JSON says and computes nothing of its own.
3. Waiting is a fact worth seeing.
4. Plain words over labels and codes.

## Accessibility & Inclusion

WCAG AA contrast in light and dark themes; colour never carries meaning alone; every drawing has
a text equivalent; native, keyboard-reachable `<details>` for anything that opens.
