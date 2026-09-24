---
slug: fde-discovery
title: The agent works as a forward deployed engineer
status: draft
saved: 2026-09-24T13:43:19+00:00
---

# The agent works as a forward deployed engineer

## Why

Forge is mostly run by forward deployed engineers who were never trained in
product work, for customers who often don't know what to build. Until now a
product manager decided what to build; that is no longer true. Discovery was
handed to gstack's office-hours skill, a large third-party bundle Forge
otherwise barely uses and that drags in a direnv setup step. Decision 0089
makes the Forge skill itself own discovery, and removes gstack and direnv.

## Behaviour

- The Forge skill gains a lean FDE section (about 70 lines) and a reference
  file `factory/skills/fde-reference.md` the agent opens only when needed
  (worked examples, question bank, customer call script, bad-to-better
  questions).
- Depth follows the lane: a fix gets up to two questions, a small story four
  to six, a story the full discovery.
- Asking rules: one question per turn; ask about what already happened, not
  what someone would do; no solution during discovery; praise and promises
  are not evidence. Questions about facts offer neutral choices with no
  recommended answer; questions asking the human to decide put the
  recommended option first. Each question carries one "Why I ask" line,
  dropped for FDEs who show they know it.
- Discovery fills a short problem card in `docs/product/DISCOVERY.md`: the
  job, today's workaround, the cost (time, money or risk), who feels it, how
  often, and the evidence. When the customer doesn't know what to build, the
  agent asks about their work and ranks pains by cost, or gives the FDE a
  customer call script whose notes come back through `docs/context/`.
- The agent offers two to four options per problem, always including not
  building and the smallest testable slice; UI prototypes go to impeccable.
- The payback rule: monthly value (hours × people × rate, revenue, or risk
  reduction) times a confidence factor (1.0 measured, 0.5 estimated, 0.2
  guessed), against build cost. Payback within 3 months: build; 3 to 12
  months: build the smallest slice first; over 12 months: recommend not
  building. Rates are rounded loaded rates, never real salaries.
- Every story spec gets a `## Success measure` section (metric, baseline,
  target, check date); the spec cold read flags a missing one. After ship,
  the outcome states the metric, a dated deferral row brings the check back,
  and `forge next` lists success checks whose date has passed.
- Discovery's owner in `harness.yaml` becomes the Forge skill; impeccable is
  allowed in the prototype phase.
- gstack is removed from Forge: the `forge gstack` command, doctor checks
  that clone and install it, adopt/upgrade/scaffold ignore and `.envrc`
  additions, harness settings, the precedence tier, docs, install skills and
  tests. direnv is no longer required by doctor; Forge reads `.envrc`
  directly. The tracked gstack history in this repo moves to
  `docs/context/gstack-archive/`. Existing client gstack ignore and `.envrc`
  lines are left alone.

## Acceptance criteria

- The Forge skill's FDE section is at most about 70 lines, and the reference
  file holds the examples, question bank and call script.
- Starting discovery on a vague ask produces one question per turn, each with
  a "Why I ask" line, and fills the DISCOVERY.md problem card.
- A story spec without `## Success measure` is flagged by its cold read; with
  one, `spec confirm` accepts it unchanged.
- A shipped story with a success check date in the past appears in
  `forge next`.
- `forge doctor` (fast, full and `--fix`) passes on a machine without gstack
  or direnv and never installs either.
- `forge gstack` no longer exists; no Forge code, config, doc, install skill
  or test references gstack except the archive and history records.
- `init`, `adopt` and `upgrade` no longer add gstack ignore rules or
  `.envrc` gstack lines, and leave existing ones untouched.
- The previously tracked gstack history is readable under
  `docs/context/gstack-archive/`.
