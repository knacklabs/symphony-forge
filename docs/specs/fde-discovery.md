---
slug: fde-discovery
title: The agent works as a forward deployed engineer
status: confirmed
saved: 2026-09-24T17:03:49+00:00
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

**The skill.** The Forge skill gains a lean FDE section (about 70 lines) and
a reference file `factory/skills/fde-reference.md` the agent opens only when
needed (worked examples, question bank, customer call script, bad-to-better
questions).

**How deep to go.** Until the three-lane story lands, the route is today's:
a Lite fix asks at most two questions; anything else is a story and gets the
full discovery. The full discovery asks at most eight questions; when the
limit is reached, missing answers are written as "unknown" and the payback
rule treats them as guessed, so questioning never loops.

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
spec's Why. When the customer doesn't know what to build, the agent asks
about their work and ranks the pains by cost, or gives the FDE a customer
call script; the agent reads the notes the FDE drops in `docs/context/`,
writes what they show into the cards, and marks each note harvested with
`forge context mark`, naming DISCOVERY.md as its output.

**Options and the choice.** The agent offers two to four options per problem,
always including not building and the smallest testable slice, and
recommends the one with the best payback. The human chooses through an
option question (recommendation first); the chosen option and one line of
why are written into the capability spec's Behaviour. UI prototypes use
impeccable when it is installed, else plain HTML under `prototype/`.

**The payback rule.** Monthly value = hours saved per month × people ×
rounded loaded hourly rate, or added revenue per month, or risk reduction
(cost of the incident × chance per month). Value × confidence (1.0 measured,
0.5 estimated, 0.2 guessed or unknown). Build cost = estimated build days ×
rounded day rate. Payback = build cost ÷ confident monthly value. Payback of
3 months or less: build. More than 3 and up to 12: build the smallest slice
first. More than 12: recommend not building. If the value cannot be
estimated at all, the recommendation is to find out first (one more
customer conversation), not to build. Real salaries are never recorded.
`forge payback` computes this from the inputs, so the agent never does the
arithmetic by hand and the same inputs always give the same answer.

**Success measure.** Every capability spec confirmed after this change has a
`## Success measure` section with four non-empty fields: metric, baseline,
target and check date (YYYY-MM-DD). `forge spec confirm` refuses a new spec
without them; specs confirmed earlier are not re-checked. When several
roadmap stories come from one spec, the measure belongs to the spec and is
checked after its last story ships.

**After ship.** Nothing is stored ahead of time: `forge next` lists a spec's
success check when every roadmap story linked to that spec is done, its check
date has passed, and its Success measure has no result yet. The agent
measures, and `forge spec measure <slug> --result "<measured result>"` adds a
`- Result: <text> (YYYY-MM-DD)` line to the spec's Success measure, which
stops the listing. A story added to the spec later simply postpones the check
until it is done too. Success checks are not deferrals and never appear in
the deferral ledger.

**Owners.** Discovery's owner in `harness.yaml` becomes the Forge skill;
impeccable is added to the prototype phase's allowed tools. impeccable is a
required skill at a pinned version: `forge doctor` checks that it is installed
at that version for Claude and Codex, and `forge doctor --fix` installs it.

**gstack and direnv removed.** The `forge gstack` command; doctor checks that
clone and install gstack; direnv as a requirement (Forge reads `.envrc`
directly); init/adopt/upgrade gstack ignore rules and `.envrc` gstack lines;
the gstack precedence tier and disabled list in `harness.yaml`; and the
gstack mentions in WORKFLOW, AGENTS, CLAUDE files, README, getting-started,
the Forge skill, install skills, living confirmed specs, and tests. This
repository's tracked gstack history moves to `docs/context/gstack-archive/`
and is recorded as harvested in the context ledger in the same change. Client
repos keep their `.gstack/` data, ignore rules and `.envrc` lines untouched;
the upgrade skill mentions they can archive that history themselves.

## Acceptance criteria

- The Forge skill's FDE section is about 70 lines or fewer, and the reference
  file holds the examples, question bank and call script.
- A new discovery with a vague ask asks one question per turn, each with a
  "Why I ask" line until the FDE says they know why, stops at the lane's
  limit, and fills a problem card in DISCOVERY.md.
- The payback rule gives the same recommendation for the same inputs,
  including the exact 3- and 12-month boundaries and the unknown-value case.
- `forge spec confirm` refuses a new spec whose Success measure is missing or
  has an empty field or a bad date, and accepts a complete one with only its
  status changed.
- Once every story linked to a spec with a success measure is done and its
  check date has passed, `forge next` lists the check until `forge spec
  measure <slug> --result` records the result in the spec; a pending story
  from the spec postpones it; nothing is added to the deferral ledger.
- `forge payback` returns build, smallest slice first, don't build, or find
  out first, and gives the same answer for the same inputs.
- `forge doctor` (fast, full and `--fix`) passes on a machine without gstack
  or direnv and never installs either; it reports a missing or outdated
  impeccable as a required skill, and `--fix` installs the pinned version.
- `forge gstack` no longer exists; in this repository, no code (including the
  `.gstack/` path tokens), config, prompt, skill, living confirmed spec,
  WORKFLOW/AGENTS/CLAUDE/README/getting-started text or test references
  gstack. Decisions, superseded
  specs, plans, `.factory/` records and the archive are exempt as history.
- `init`, `adopt` and `upgrade` add no gstack ignore rules or `.envrc` gstack
  lines and leave existing client ones untouched.
- This repository's former gstack history is readable under
  `docs/context/gstack-archive/` and the context ledger shows it harvested.

## Success measure

- Metric: share of new stories whose confirmed spec carries a complete
  success measure, and FDE-reported confidence in choosing what to build.
- Baseline: 0% of specs today; confidence not measured.
- Target: 100% of specs confirmed after this ships; at least 4 of 5 FDEs
  say discovery helped them choose (one-question check-in).
- Check date: 2026-11-15
