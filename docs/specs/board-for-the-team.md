---
slug: board-for-the-team
title: The board tells a team what's happening, what needs them and when it goes live
status: draft
saved: 2026-10-09T15:44:20+00:00
---

# The board tells a team what's happening, what needs them and when it goes live

## Why

A project manager or team lead opening the forge board today can't use it. Two reviews of a real client board (October 2026) found:

- The first screen shows finished work and a narrow map; about half of a laptop screen is empty.
- 119 "Not started yet" story cards come before the four stories actually in progress; open fixes are last.
- Counts mix stories and fixes and contradict the cards ("Waiting for approval: 0" while a card says it waits).
- Nothing says what's blocked, who owns what, what needs a person, or what to look at first.
- There's no pace and no forecast. Counting by hand: 38 planned parts left, while parts finished per week fell from 13 to 4 to 2, and 132 stories have no plan at all.
- Most of an item's time is waiting (CI, the machine's queue, a person's answer), not work, and the board never shows waiting.

The people who open the board and what they need:

| Who | Needs |
|---|---|
| Owner or project manager | Are we on track, when can it go live and how sure, what needs me, what's at risk, what shipped |
| Lead | What can start now, who is free or overloaded, what blocks the most, which plans wait for approval |
| Developer | What's mine, what waits on me, what to pick up next |

## Behaviour

The board answers those in order, on the team's own machines (each person's `forge board` after a fetch, and the Claude Code pane), from the same data as `forge board --json`.

1. **First screen, full width, no scrolling on a laptop:**
   - Number tiles, labelled separately: stories by state (no plan yet, planning, waiting for approval, building, done); parts of planned stories by state; open fixes by state; finished in the last 7 days.
   - **Needs you:** every item waiting on a person (plan approval, a review-loop choice, a merge the human makes, a worker's question, a conflict), oldest first, with how long it has waited.
   - **In progress:** one bar per active story ("5 of 8 parts"), with who started its open parts and the age of the oldest.
   - **Blocked or slow:** stalled items, items looping (fourth round or more, or the same requirement failing again), and the part that blocks the most others, each with its reason and how long.
   - **Pace and go-live estimate:** parts and fixes finished per week for the last six weeks, and a date range for the planned work at recent pace; stories with no plan yet are counted separately and named as the real unknown. Never a single date.
2. **Below the fold:** the dependency map of active stories across the full width (finished parts collapsed to counts, unplanned stories collapsed to one "Backlog (N)" row), then story and fix cards sorted needs-you, blocked, in progress, planned, not started, done, with finished work folded away.
3. **Each item:** where its time went (working versus each kind of waiting, from the time records), one line per review round, and who started it and who approved it.
4. **Words a newcomer understands:** plain labels and a one-line key for the map's shapes and the words part, fix and plan.
5. **After an upgrade,** the agent fills data older items lack from git and GitHub as part of the update; what truly can't be found shows as unknown, never invented.

Options weighed: **Don't build** (the board stays unusable for a team; the owner rejected it); **Smallest slice** (fix the wrong data only: counts and statuses become right, but nobody can see what needs them or forecast; taken as the first part, already in flight); **Rebuild the board around the questions above** (chosen by the owner, 2026-10-09: a project manager must be able to see the total status and estimate go-live). Showing the board to people outside the team's machines (a phone or a client) is out of scope for now.

## Acceptance criteria

1. On a laptop screen the board's first screen, without scrolling, shows the labelled totals, Needs you, In progress, Blocked or slow, and Pace with the go-live range.
2. Every count, status and time agrees with `forge board --json` and `forge next`, and stories, parts and fixes are counted separately.
3. Needs you lists every item waiting on a person with its wait time; Blocked or slow lists stalled and looping items and the part that blocks the most, each with a reason.
4. The go-live estimate gives a date range from recent pace for planned parts and names the stories with no plan as unknown; it never shows a single date.
5. Each item shows where its time went (working versus waiting), one line per review round, and who started and approved it.
6. The page uses the full width of a laptop, reads in light and dark mode, and stacks to one column on a phone.
7. After an upgrade, data older items lack is filled from git and GitHub by the agent as part of the update; nothing is invented.

## Success measure

- Metric: questions a first-time viewer answers correctly within one minute from a real client repo's board page (what is in progress, what needs a person, what is blocked and why, the go-live range for planned work)
- Baseline: 0 of 4 (first-time-viewer review of a real client board, 2026-10-09)
- Target: 4 of 4, each matching the repo's real state
- Check date: 2026-11-15
