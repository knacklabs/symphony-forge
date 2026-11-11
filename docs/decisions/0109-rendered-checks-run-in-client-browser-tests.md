---
status: proposed
confirmed_by: ""
date: 2026-11-11
stories: [FORGE-RENDER-1]
supersedes: ""
---

# Rendered checks run in the client's browser tests

## Context

On 5 August 2026, a decision said that no browser is added to Forge's own tools or to a client repo, so that a page's width can be proven without one. That decision was about the board page in Forge's own tests. It said a real need for rendered checks would be a new decision with a named user. The client starter has installed a browser test tool since 27 September 2026, and no decision records that change. On 10 November 2026, the owner chose to show what a changed screen looks like when it closes.

## Decision

Forge ships `.forge/design/render-check.mjs` to every client repo. The agent calls it from the app's own Playwright tests, once for each screen on the render list. It checks overflow, cut text, low contrast and the wrong page, in light and dark, at desktop width and at phone width when the brief's `Phone view` answer asks for it. A problem fails the test, so it stops close. Forge starts no browser, adds no package and makes no model call.

## Consequences

Forge itself still starts no browser. A screen that is not on the list is not checked; review reports it as `Gate: rendered check`. A missing `Phone view` answer means desktop width only and refuses nothing. This decision does not reverse the 5 August 2026 decision for Forge's own tools.
