---
status: accepted
confirmed_by: "Ravi Kiran Vemula"
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

Forge itself still starts no browser. A screen that is not on the list is not checked; review reports it as `Gate: rendered check`, except in the light review of an unsigned prototype. The check runs wherever the app's browser tests run. Close runs them only when the repo's close command (`fast_test`, else `test`) includes them; when it does not, the check runs only in the full test run, and the worker says so. A sample-data prototype has no rendered check before sign-off; the fix that adds its first tests lists its screens. A missing `Phone view` answer means desktop width only and refuses nothing; a yes is recorded as `desktop and phone`. This decision does not reverse the 5 August 2026 decision for Forge's own tools.
