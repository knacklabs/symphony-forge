---
slug: fde-discovery
title: The agent works as a forward deployed engineer
status: draft
saved: 2026-09-26T09:38:11+00:00
---

# The agent works as a forward deployed engineer

## Why

Forge is mostly run by forward deployed engineers who were never trained in
product work, for customers who often don't know what to build. Until now a
product manager decided what to build; that is no longer true. So the agent
acts as the FDE's product partner: it finds the real problem, weighs whether
it is worth building, and checks afterwards whether it paid off. The new
Forge doesn't carry gstack, but gstack's office-hours session is still the
best way to shape a new project or a big new idea, so the agent runs it for
exactly that and runs its own short interview for everyday asks. This narrows
decision 0089: of gstack, only office-hours stays.

## Behaviour

**The skill.** The Forge skill gains a Discovery section (about 70 lines or
fewer) and a reference page, `fde.md`, that `forge sync` writes beside the
skill for both hosts. The agent opens the page only when needed (worked
example, question bank, customer call script, bad-to-better questions).

**Discovery by size.** Everyday asks get Forge's own interview: a fix asks
at most two questions and a story at most eight. When the limit is reached,
missing answers are written as "unknown" and the payback rule treats them as
guessed, so questioning never loops. A new project, or a big new idea (an
ask that no existing spec covers), starts with gstack's `/office-hours`
instead. The agent saves the design doc it produces, unchanged, in
`docs/context/` and fills the problem card from it, writing any field the
doc leaves open as "unknown". If `/office-hours` isn't installed, the agent
says it comes with gstack and runs its own interview with the story limit.
Options, payback and the success measure work the same either way.

**Asking rules.** One question per turn; ask about what already happened, not
what someone would do; no solution during discovery; praise and promises are
not evidence. Questions about facts offer neutral choices with no
recommended answer; questions asking the human to decide put the recommended
option first. Each question carries one "Why I ask" line until the FDE
answers that they know why; from then on, only the question.

**Problem cards.** `docs/product/DISCOVERY.md` has a `## Problems` section
with one card per pain (a `###` heading each) holding six fields: the job,
today's workaround, the cost, who feels it, how often, and the evidence. The
chosen card's heading is named in the Brief's problem and in the capability
spec's Why. `forge init` writes DISCOVERY.md with an empty card, and an
existing DISCOVERY.md gets the section on first use. While nothing is on the
roadmap, `forge next` offers discovery first. When the customer doesn't know
what to build, the agent asks about their work and ranks the pains by cost,
or gives the FDE a customer call script. The agent reads the notes the FDE
drops in `docs/context/`, writes what they show into the cards, and leaves
the notes where they are.

**Options and the choice.** The agent offers two to four options per problem,
always including not building and the smallest testable slice, and
recommends the one with the best payback. The human chooses through an
option question (recommendation first); the chosen option and one line of
why are written into the capability spec's Behaviour. UI prototypes use
impeccable, the one required UI skill.

**The payback rule.** Monthly value = hours saved per month × people ×
rounded loaded hourly rate, plus added revenue per month, plus risk
reduction (cost of the incident × chance per month), counting whichever
apply. Value × confidence (1.0 measured, 0.5 estimated, 0.2 guessed or
unknown). Build cost = estimated build days × rounded day rate. Payback =
build cost ÷ confident monthly value. Payback of 3 months or less: build.
More than 3 and up to 12: build the smallest slice first. More than 12:
recommend not building. If the value cannot be estimated at all, the
recommendation is to find out first (one more customer conversation), not to
build. Real salaries are never recorded. `forge spec payback` computes this
from the inputs, so the agent never does the arithmetic by hand and the same
inputs always give the same answer. It changes nothing and runs anywhere. It
takes the rates as flags each time, treats a missing confidence as guessed,
and refuses a partial set of inputs, naming what is missing.

**Success measure.** Every capability spec confirmed after this change has a
`## Success measure` section with four non-empty fields: metric, baseline,
target and check date (YYYY-MM-DD). `forge spec save` and `forge spec
confirm` refuse a spec without them, so a gap is caught before the cold
read. Specs confirmed earlier are not re-checked until they are saved again.
When several roadmap stories come from one spec, the measure belongs to the
spec and is checked after its last story ships.

**After ship.** Nothing is stored ahead of time: `forge next` lists a spec's
success check when every roadmap story linked to that spec is done, its check
date has passed, and its Success measure has no result yet. The agent
measures, and `forge spec measure <slug> --result "<measured result>"`, run
in a fix, adds a `- Result: <text> (YYYY-MM-DD)` line to the spec's Success
measure. That stops the listing, and the spec stays confirmed. A story added
to the spec later simply postpones the check until it is done too.

**gstack: office-hours only.** Forge's code never installs, calls or checks
gstack. The agent uses its `/office-hours` skill for a new project or a big
new idea, and keeps only the design doc it produces, in `docs/context/`.
Nothing else from gstack is stored in a repo. `forge migrate` already moves a
client's office-hours design docs to `docs/context/` and deletes the rest of
`.gstack/`, and the switch does the same for this repository.

## Acceptance criteria

- The Forge skill's Discovery section is about 70 lines or fewer, and the
  reference page beside it holds the examples, question bank and call script.
- A vague everyday ask gets one question per turn, each with a "Why I ask"
  line until the FDE says they know why. It stops at the limit (two for a
  fix, eight for a story) and fills a problem card in DISCOVERY.md.
- A new project or a big new idea starts with `/office-hours`. Its design doc
  is saved unchanged in `docs/context/` and fills the problem card. Without
  `/office-hours`, the agent says where to get it and runs its own interview.
- A new project's DISCOVERY.md starts with an empty problem card, and
  `forge next` offers discovery while nothing is on the roadmap.
- `forge spec payback` returns build, smallest slice first, don't build, or
  find out first, and gives the same answer for the same inputs, including
  the exact 3- and 12-month boundaries and the unknown-value case.
- `forge spec save` and `forge spec confirm` refuse a spec whose Success
  measure is missing or has an empty field or a bad date. Confirm accepts a
  complete one without changing its body.
- Once every story linked to a spec with a success measure is done and its
  check date has passed, `forge next` lists the check until `forge spec
  measure <slug> --result` records the result in the spec. A pending story
  from the spec postpones it, and the spec stays confirmed.
- Forge's code never installs, calls or checks gstack, and no gstack output
  other than office-hours design docs is kept in a repo.

## Success measure

- Metric: share of specs confirmed after this ships whose Why names a
  problem card, and FDE-reported confidence in choosing what to build.
- Baseline: 0% of specs today; confidence not measured.
- Target: at least 4 of 5 such specs; at least 4 of 5 FDEs say discovery
  helped them choose (one-question check-in).
- Check date: 2026-12-15

## Out of scope

- A harvest ledger or `forge context mark`: customer notes stay where they
  are.
- A pinned impeccable version, and installing it from `forge doctor`.
- Any gstack skill other than office-hours, and a doctor check for gstack.
- Rate settings in `forge.toml`: payback takes rates as flags each time.
