---
slug: fde-discovery
title: The agent works as a forward deployed engineer
status: confirmed
saved: 2026-09-26T09:45:57+00:00
confirmed_by: "vrknetha"
confirmed_hash: 7d0926f3de7fb3ac6471b18691d63c951f6e59c2fb501be2fd78407ffcca4a70
---

# The agent works as a forward deployed engineer

## Why

Forge is mostly run by forward deployed engineers who were never trained in
product work, for customers who often don't know what to build. Until now a
product manager decided what to build; that is no longer true. So the agent
acts as the FDE's product partner: it finds the real problem, weighs whether
it is worth building, and checks afterwards whether it paid off. The new
Forge doesn't carry gstack, but gstack's office-hours session is still the
best way to shape a new project or an ask no confirmed spec covers, so the agent runs it for
exactly that and runs its own short interview for everyday asks. This narrows
decision 0089: of gstack, only office-hours stays.

## Behaviour

**The skill.** The Forge skill gains a Discovery section (about 70 lines or
fewer) and a reference page, `fde.md`, that `forge sync` writes beside the
skill for both hosts. The agent opens the page only when needed (worked
example, question bank, customer call script, bad-to-better questions).

**Discovery by size.** The route follows what the ask is. A new project, or
an ask that no confirmed spec covers, starts with gstack's `/office-hours`;
this wins over the other two. An ask that a confirmed spec covers is a
story, and one that corrects shipped behaviour is a fix; both get Forge's own
interview: a fix asks at most two questions and a story at most eight. When
the limit is reached, missing answers are written as "unknown" and the
payback rule treats them as guessed, so questioning never loops. The agent
saves the design doc office-hours produces, unchanged, in `docs/context/` and fills the problem card from it, writing any field the
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
with one card per pain (a `### <short problem title>` heading each) holding
six fields: `- Job:`, `- Workaround:`, `- Cost:`, `- Who:`, `- How often:`
and `- Evidence:`. The chosen card's heading is named in the Brief's
Summary and in the capability spec's Why. `forge init` writes DISCOVERY.md
with one card whose fields read "unknown", replacing the template's old
`## Problem` section. An existing DISCOVERY.md gets the section on first use;
any text under its old `## Problem` stays where it is and is written into a
card. While nothing is on the
roadmap, `forge next` offers discovery first. When the customer doesn't know
what to build, the agent asks about their work and ranks the pains by cost,
or gives the FDE a customer call script. The agent reads the notes the FDE
drops in `docs/context/`, writes what they show into the cards, and leaves
the notes where they are. The new Forge keeps no ledger of those notes; this
repository's older inbox rules go away with the switch to it.

**Options and the choice.** The agent offers two to four options per problem,
always including not building and the smallest testable slice. Each option
that builds something gets its own `forge spec payback` answer. The agent
recommends the option with the fewest months among those answering "build"
or "smallest slice first", a tie going to the smaller build. If none does,
it recommends not building, or finding out first when an option's value
can't be estimated. The human chooses through an option question
(recommendation first); the chosen option and one line of why are written
into the capability spec's Behaviour.

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
inputs always give the same answer. It changes nothing and runs anywhere.
Its flags are `--build-days` and `--day-rate`, plus one or more value
groups that add up: `--hours-per-month`, `--people` and `--hourly-rate`;
`--revenue-per-month`; `--incident-cost` and `--incident-chance` (0 to 1).
`--confidence measured|estimated|guessed` defaults to guessed. It prints one
line: `find out first` when no value group is given, otherwise
`build: <m> months`, `smallest slice first: <m> months` or
`don't build: <m> months`, or `don't build: no monthly value` when the value
is zero. Months are compared exactly and shown to one decimal. It refuses a
partly given group, value without both build numbers, and a negative or
non-number input, each naming the flag.

**Success measure.** Every capability spec confirmed after this change has a
`## Success measure` section with four non-empty fields: metric, baseline,
target and check date (YYYY-MM-DD). `forge spec save` and `forge spec
confirm` refuse a spec without them, so a gap is caught before the cold
read. Specs confirmed earlier are not re-checked until they are saved again.
When several roadmap stories come from one spec, the measure belongs to the
spec and is checked after its last story ships.

**After ship.** Nothing is stored ahead of time: `forge next` lists a spec's
success check when at least one roadmap item names the spec, every such
item's story is done (its story state on the default branch, as landed), its
check date is today or earlier, and its Success measure has no result yet. A
spec no roadmap item names is never due. The agent measures, and
`forge spec measure <slug> --result "<measured result>"`, run in a fix, adds
a `- Result: <text> (YYYY-MM-DD)` line to the spec's Success measure. It
refuses a spec whose body changed since it was confirmed, then refreshes the
confirmed body's hash, so the spec stays confirmed and `forge roadmap add`
still accepts it. That stops the listing. A story added to the spec later
simply postpones the next check until it is done too.

**gstack: office-hours only.** Forge's code never installs, calls or checks
gstack. The agent uses its `/office-hours` skill for a new project or an ask
no confirmed spec covers, and keeps only the design doc it produces, in
`docs/context/`. Nothing else from gstack is stored in a repo.

## Acceptance criteria

- The Forge skill's Discovery section is about 70 lines or fewer, and the
  reference page beside it holds the examples, question bank and call script.
- A vague everyday ask gets one question per turn, each with a "Why I ask"
  line until the FDE says they know why. It stops at the limit (two for a
  fix, eight for a story) and fills a problem card in DISCOVERY.md.
- A new project, or an ask no confirmed spec covers, starts with `/office-hours`. Its design doc
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
  problem card.
- Baseline: 0% of specs today.
- Target: at least 4 of 5 such specs; if fewer than five exist by the check
  date, every one of them.
- Check date: 2026-12-15

## Out of scope

- A harvest ledger or `forge context mark`: customer notes stay where they
  are.
- Any change to UI tooling: impeccable stays the one UI skill, unpinned.
- Deleting gstack stores in migration or the switch: that is their own work.
- Any gstack skill other than office-hours, and a doctor check for gstack.
- Rate settings in `forge.toml`: payback takes rates as flags each time.
