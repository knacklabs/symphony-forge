# The agent works as a forward deployed engineer

## What changes for you

- On an everyday ask, the agent interviews you, and through you the customer, one question at a
  time about what actually happened. Each question says in one line why it matters, until you tell
  it you know. A fix gets at most two questions and a story at most eight. Anything still
  unanswered is written down as unknown.
- On a new project, or an ask no confirmed spec covers, the agent runs gstack's office-hours session
  first instead. The design doc it produces is saved with the project's context notes and fills
  the problem card. If office-hours isn't installed, the agent tells you where to get it and runs
  its own interview. gstack is used for nothing else, and nothing else from it is kept in the repo.
- Either way, the answers become a short problem card in the project's discovery notes: the job,
  today's workaround, what it costs, who feels it, how often, and the evidence.
- A brand-new project starts with discovery. Its discovery notes come with an empty card, and
  `forge next` offers discovery before anything is on the roadmap.
- For the chosen problem, the agent offers two to four options, always including "don't build" and
  the smallest slice. It recommends one using `forge spec payback`, which gives the same answer for
  the same numbers every time. You choose, and your choice and your reason go into the spec.
- Every new spec says how success will be measured: a metric, a baseline, a target and a check
  date. When everything built from that spec has shipped and the date has passed, `forge next`
  reminds you to check, and `forge spec measure` records the result in the spec.

## Why

Most people who run Forge are forward deployed engineers who were never trained in product work.
Their customers often don't know what to build, and no product manager decides for them any more.
So the agent has to act as the engineer's product partner: find the real problem, weigh whether it
is worth building, and check afterwards whether it paid off.

The new Forge doesn't carry gstack. Its office-hours session is still the best way to shape a new
project, or an ask no confirmed spec covers: it is a longer design session that challenges the
premise, weighs alternatives and ends in a design doc, which a short interview doesn't do. So the
agent uses it for exactly that, and a short interview of its own handles everyday asks.

This is also the first story built on the new Forge from start to finish: one cold read, one
approval, and its own tasks, each closed and merged the new way. How long its tasks take starts the
new Forge's cycle-time baseline.

## Done when

1. Discovery goes by size:
   - on a fix or an everyday story, the agent asks one question per turn about what actually
     happened, each with a one-line "Why I ask" until the engineer says they know why. A fix gets
     at most two questions and a story at most eight, and anything unanswered is written as
     unknown;
   - on a new project, or an ask no confirmed spec covers, it runs gstack's office-hours first and
     saves the design doc in `docs/context/`. Without office-hours, it says where to get it and
     runs its own interview instead.
2. The result lands in a problem card in the project's discovery notes, with six fields: the job,
   today's workaround, the cost, who feels it, how often, and the evidence. The chosen card is named
   in the brief and in the spec's Why. A new project's notes start with an empty card, and
   `forge next` on a project with nothing on its roadmap offers discovery first.
3. For the chosen problem, the agent offers two to four options, always including not building and
   the smallest slice. It recommends one by its payback, and writes the human's choice and one line
   of why into the spec.
4. `forge spec payback` answers one of four things: build, smallest slice first, don't build, or
   find out first. It gives the same answer for the same numbers, including at exactly three and
   exactly twelve months and when no value can be estimated. A partial set of numbers is refused,
   naming what's missing.
5. A spec without a complete success measure (a metric, a baseline, a target and a check date) is
   refused when it is saved and when it is confirmed.
6. Once every story from a spec is done and its check date has passed, `forge next` lists the check
   until `forge spec measure` records the result in the spec. The spec stays confirmed.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| PAYBACK | Payback answer | `forge spec payback`, harvested from the earlier FDE work: exact arithmetic, the three- and twelve-month edges, "find out first" with no value, and a refusal naming any missing number. It changes nothing, so it runs anywhere. The guide lists it | 4 | `src/forge/payback.py`, `src/forge/cli.py`, `docs/guide.md` | `tests/test_payback.py` | — | yes |
| MEASURE | Success measure and check-back | `forge spec save` and `forge spec confirm` refuse a spec without a complete Success measure. `forge spec measure` appends the result and keeps the spec confirmed. `forge next` lists a check that is due. The specs page and the guide list the new section and command | 5, 6 | `src/forge/records.py`, `src/forge/cli.py`, `src/forge/nextstep.py`, `src/forge/templates/skeleton/docs/specs/README.md`, `docs/guide.md` | `tests/test_measure.py`, `tests/test_records.py` | PAYBACK | yes |
| DISCOVER | The agent runs discovery | The skill's Discovery section: the asking rules and limits, office-hours for a new project or an ask no confirmed spec covers, problem cards, options priced with `forge spec payback`, the choice written into the spec, and the check-back naming `forge spec measure`. A reference page with the worked example, question bank and call script, which sync ships beside the skill for both hosts. The empty card in a new project's discovery notes, and `forge next` offering discovery while the roadmap is empty | 1, 2, 3 | `src/forge/templates/skill.md`, `src/forge/templates/fde.md`, `src/forge/sync.py`, `src/forge/templates/skeleton/docs/product/DISCOVERY.md`, `src/forge/nextstep.py` | `tests/test_discovery.py`, `tests/test_setup.py` | PAYBACK, MEASURE | yes |

New moving parts: gstack's office-hours skill, run by the agent (never by Forge's code) for a new project or an ask no confirmed spec covers, and optional, since without it the agent runs its own interview (Done when 1)

## Risks

- Cost figures end up in client repos. The agent uses rounded rates, never real salaries.
- office-hours is a third-party skill that can change or go away. Forge's code never calls it and
  nothing reads its format: the agent copies the design doc as it is, and without office-hours it
  runs its own interview.
- The skill is read in every session. Its Discovery section stays short, and the examples, question
  bank and call script live in a reference page the agent opens only when needed.
- Good discovery depends on the agent following the skill. DISCOVER's functional check walks a
  vague ask and a new-project ask through a throwaway project.
- Recording a result edits a confirmed spec. `forge spec measure` only appends the result line and
  keeps the spec confirmed, and it refuses a spec whose text changed since it was confirmed.
- This is the new Forge's first real story. Problems it finds in Forge itself are fixed as their own
  fixes, never worked around inside this story's tasks.
- The code to harvest lives only on a local branch, not on GitHub. It must be kept until PAYBACK and
  DISCOVER merge.

## Notes

- **Key and spec.** The key is FORGE-FDE-1. The spec is `docs/specs/fde-discovery.md`, amended with
  this story (the command names, office-hours for a new project or an unspecced ask, discovery by
  size, and "gstack stays, only for office-hours"), then saved, read once and confirmed in its own
  fix. Its success measure changes to the share of specs whose Why names a problem card, checked on
  2026-12-15. Its one cold read runs on the other model family from the coordinator's (Codex when
  Claude coordinates), with the models in `forge.toml`'s `[models.grill]`. Decision 0089
  ("discovery without gstack") is narrowed, not replaced: gstack stays only for office-hours, and
  the amended spec says so (owner decision, 2026-09-26, recorded in the spec rather than a new
  decision).
- **Order.** The three tasks run one after another, because each pair shares a file. PAYBACK and
  MEASURE both add a command row and a guide line, and MEASURE and DISCOVER both change
  `forge next`. DISCOVER writes all the skill text last, so every command it names already exists.
  PAYBACK pins the payback flags and output, and MEASURE pins the Success measure format and
  `spec measure`. MEASURE also pins the shared `forge next` seam: a due check is listed before the
  discovery prompt, with one test crossing both.
- **Choosing among options.** Each option that builds something gets its own `forge spec payback`
  line. The agent recommends the option with the fewest months among those answering "build" or
  "smallest slice first"; a tie goes to the smaller build. If none does, it recommends "don't
  build", or "find out first" when an option's value can't be estimated. PAYBACK's reference
  examples pin this.
- **Harvest** from branch `feat/FORGE-FDE-1-FDE` (local only, head `a529a1ee`):
  - `factory/scripts/forge_cli/payback.py` becomes `src/forge/payback.py`. Keep the pure function,
    the `Fraction` arithmetic, the exact boundaries and the display rounding. Its error messages move
    into the module's refusal table, one test each.
  - `factory/skills/fde-reference.md` becomes `src/forge/templates/fde.md`: the worked example, the
    question bank, the customer call script and the bad-to-better questions. `./forge payback`
    becomes `forge spec payback`, and links point at `SKILL.md`.
  - The FDE section of `factory/skills/forge.md` goes into `src/forge/templates/skill.md`, merged
    with the skill's existing "Challenge first" and "Check-back" text, never duplicating it.
  - `success_measure` and `success_measure_problems` from `specs.py` go into `records.py`, and
    `cmd_measure` becomes `records.spec_measure`.
  - The card shape comes from `scaffold.py`, and the due check from `phase.py`.
- **`forge spec payback`** (`payback:payback`, changes nothing, so no pin check):
  - Flags: `--build-days` and `--day-rate`, and one or more value groups:
    - `--hours-per-month`, `--people` and `--hourly-rate`;
    - `--revenue-per-month`;
    - `--incident-cost` and `--incident-chance` (0 to 1).

    The groups given add up. `--confidence measured|estimated|guessed` weighs the value by 1, 1/2
    or 1/5, and defaults to guessed.
  - It prints one line: `find out first` when no value group is given, and otherwise
    `build: <m> months` (three or less), `smallest slice first: <m> months` (more than three, up to
    twelve) or `don't build: <m> months` (more than twelve). Zero value prints
    `don't build: no monthly value`. Months are compared exactly and shown to one decimal. Every
    answer exits 0.
  - It refuses a partly given group, value without the build numbers, and a negative or non-number
    input, each naming the flag.
- **Success measure.** A `## Success measure` section with `- Metric:`, `- Baseline:`, `- Target:`
  and `- Check date: YYYY-MM-DD`, none empty, where a field may wrap onto indented lines. One helper
  checks it, called by `spec save` (so a gap is caught before the cold read) and `spec confirm`.
  Specs confirmed earlier aren't re-checked until they are saved again.
- **`forge spec measure <slug> --result "<text>"`** runs in a fix, like the other planning records.
  It refuses a spec that isn't confirmed, one whose body no longer matches `confirmed_hash`, one
  without a complete measure, and an empty or multi-line result. It appends
  `- Result: <text> (YYYY-MM-DD)` to the Success measure, refreshes `confirmed_hash` so
  `roadmap add` still accepts the spec, and commits. A later result just appends another line.
- **A due check in `forge next`** is read from the default branch as landed, like story states. It
  needs all of these:
  - the spec is confirmed, with a complete measure;
  - its check date is today or earlier;
  - it has no `- Result:` line;
  - at least one roadmap item names the spec;
  - every such item's story is done.

  It prints one sentence naming the spec and its metric, then two Next lines: a fix, then
  `forge spec measure`.
- **Discovery first.** When `plans/roadmap.json` has no items, no story or fix is in progress, and
  the discovery notes hold no filled card (every card's fields still read `unknown`), `forge next`
  says to start with discovery as the skill's Discovery section says, and names a fix that fills
  the discovery notes and the brief. Once a card is filled, it names the next planning step
  instead: writing the spec.
- **Discovery section of the skill** (DISCOVER):
  - The asking rules: one question per turn, about past events, no solutions during discovery, and
    praise isn't evidence. Fact questions get neutral choices and decisions get the recommendation
    first. "Why I ask" is added until the engineer opts out. The limits are two for a fix and eight
    for a story, then unknown.
  - Office-hours:
    - It runs for a new project, or for an ask no confirmed spec covers (owner decision).
    - The agent runs `/office-hours`, then copies the design doc it names at the end (gstack keeps
      it under `~/.gstack/projects/<project>/`, as `*-design-*.md`) unchanged into `docs/context/`
      in the discovery fix.
    - It fills the card from the doc, writes fields the doc leaves open as unknown, and names the
      doc in the card's Evidence.
    - Without `/office-hours`, it says the skill comes with gstack (github.com/garrytan/gstack) and
      runs its own interview with the story limit.
  - The card: an existing DISCOVERY.md gets a `## Problems` section on first use. The chosen card's
    heading is named in the brief's Summary and the spec's Why. Customer notes in `docs/context/`
    are written into cards and left where they are.
  - Options and payback: a payback line is shown for every option that builds something, and the
    choice plus one line of why go into the spec's Behaviour.
  - The Check-back section names `forge spec measure`, and the intent table gets rows for payback
    and measure.
  - v1's tests have no line cap on the skill, so none is added. Aim for about 70 lines or fewer.
- **The reference page** is `src/forge/templates/fde.md`. Sync writes it to
  `.claude/skills/forge/fde.md` and `.codex/skills/forge/fde.md`, like the test-audit skill's
  files, so doctor's drift check covers it. `tests/test_setup.py`'s `LISTED` gains both paths.
- **The DISCOVERY template** replaces `## Problem` with `## Problems`, holding one
  `### <short problem title>` card whose six fields read `unknown`.
- **Tests:**
  - Each new test file starts with `STORY = "FORGE-FDE-1"`, and its `test_<n>_` names cite this
    story's Done-when items: `test_payback.py` cites 4, `test_measure.py` cites 5 and 6, and
    `test_discovery.py` cites 1, 2 and 3.
  - `test_discovery.py` checks the synced skill's rules, the shipped reference page, the new
    project's card and the discovery-first line. It also runs the reference page's payback
    examples, which is the test that crosses PAYBACK and DISCOVER.
  - Every existing test fixture that saves or confirms a spec gains a Success measure. That means
    `test_records.py`, plus ADOPT's walkthrough if it saves or confirms a spec.
  - DISCOVER's functional check, in a throwaway client, shows:
    - a vague ask gets one question per turn, each with "Why I ask";
    - fact questions get neutral choices;
    - the questions stop at the limit;
    - a new-project ask goes to office-hours, or to the fallback without it;
    - a filled card is named in the brief and in the spec;
    - the choice is recorded with its payback line.
- **Not in this story:**
  - `forge context mark`;
  - a pinned impeccable version (doctor already checks impeccable where the worker reads skills);
  - a doctor check for gstack;
  - rate settings in `forge.toml` (rates are flags, so there is no new setting);
  - a rules check that a story test's number exists in its story doc;
  - this repo's gstack store, which the switch handles.
