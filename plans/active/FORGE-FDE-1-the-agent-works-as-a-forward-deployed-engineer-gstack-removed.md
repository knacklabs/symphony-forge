# The agent works as a forward deployed engineer; gstack removed

## What and why

Most people running Forge are forward deployed engineers who were never trained in product work, and
their customers often don't know what to build. There is no product manager deciding anymore. Forge
handed discovery to gstack's office-hours skill, a large third-party bundle it otherwise barely uses,
which also forces a direnv setup step. We teach the agent to act as the FDE's product partner itself,
and remove gstack and direnv.

## What changes for you

- On a new ask, the agent interviews you (and through you, the customer) one question at a time about
  what actually happened: the job, today's workaround, what it costs, who feels it, how often, and
  the evidence. Each question says in one line why it matters, until you tell it you know. A quick fix
  gets at most two questions; a story at most eight, and anything still unknown is marked unknown.
- It writes the answers as a short problem card, offers two to four options (always including "don't
  build" and the smallest testable slice), and recommends one using `forge payback`. You choose, and
  your choice and reason go into the spec.
- Every new spec states how success will be measured, with a baseline, a target and a check date.
  When every story from that spec is done and the date passes, `forge next` reminds you to check,
  and `forge spec measure` records what you measured in the spec itself.
- For UI ideas it prototypes with impeccable, which Forge now treats as a required skill at a pinned
  version: `forge doctor` checks it and `forge doctor --fix` installs it for Claude and Codex.
- Setup gets simpler: no gstack, no direnv. Client repos keep any gstack files they already have.

## Done when

- A vague ask turns into one-question-at-a-time discovery that fills a problem card and stops at the
  question limit, with the chosen card named in the brief and spec.
- `forge payback` gives the same answer for the same numbers, including the 3- and 12-month edges and
  the unknown-value case.
- A new spec can't be confirmed without a complete success measure; a spec's check shows in `forge next`
  once all its stories are done and its date has passed, until its result is recorded.
- `forge doctor` passes without gstack or direnv, and gstack is gone from Forge's own code, settings,
  docs and tests; this repo's old gstack notes are archived and summarised.
- `init`, `adopt` and `upgrade` stop adding gstack lines and leave clients' existing ones alone.

## Risks

- Cost figures end up in client repos; the agent uses rounded rates, never real salaries.
- The skill file is read every session; the FDE part stays around 70 lines, with examples in a
  separate reference file.
- The quality of discovery depends on the agent following the skill; a scripted walkthrough in a
  throwaway client checks it before shipping.

## What I need from you

Nothing beyond approving this plan.

---

## Technical approach

- Skill: ~70-line FDE section in `factory/skills/forge.md`: asking rules (one per turn, past events,
  no solutions during discovery, neutral options for facts, recommended-first for decisions, "Why I
  ask" until the FDE opts out); depth (Lite: two questions; story: eight; unanswered fields written as
  unknown and priced as guessed); problem cards (add `## Problems` to an existing DISCOVERY.md on first
  use; name the chosen card in the Brief's problem and the spec's Why); options and the human's choice
  written into the spec's Behaviour; `forge payback`; success measure; check-back. New projects get
  the `## Problems` template; adopted projects with an existing DISCOVERY.md get it on first use. New
  `factory/skills/fde-reference.md` holds the examples, question bank, call script and bad-to-better
  questions. The discovery intent row points at the skill.
- DISCOVERY template (`scaffold.py`): `## Problems` with one `###` card per pain and the six fields.
- Customer notes: the agent writes what the notes show into the cards and runs
  `forge context mark <note> harvested` with DISCOVERY.md as the output.
- `forge payback` (new small module and command): inputs hours per month, people, hourly rate,
  revenue per month, incident cost and monthly chance, confidence (measured/estimated/guessed), build
  days and day rate; output the payback months and one of build / smallest slice first / don't build /
  find out first, with exact boundaries (<=3, >3 and <=12, >12).
- Specs: `specs.py` confirm requires `## Success measure` with metric, baseline, target and an ISO
  check date for specs confirmed after this change; `griller.md` flags a missing or empty one;
  `spec save` help and `docs/specs/README.md` list the new section.
- Check-back, computed with nothing stored ahead: `forge next` lists a spec with a success measure
  when every roadmap story linked to it is done, its check date has passed and its Success measure has
  no `- Result:` line; `forge spec measure <slug> --result "<text>"` appends
  `- Result: <text> (YYYY-MM-DD)` to that section. `forge pr-link`, the PR-link workflow, outcomes,
  the deferral ledger and its audit are untouched. Payback prices build options only; "don't build"
  and "find out first" are listed without it.
- `harness.yaml`: discovery owner → Forge skill; impeccable in the prototype allowlist; gstack
  precedence tier and disabled list removed.
- gstack removal (code): delete `forge_cli/gstack.py` and its subcommand; doctor gstack checks and
  the direnv requirement (Forge reads `.envrc` directly); impeccable becomes a required skill at a
  pinned version that doctor checks for Claude and Codex and `doctor --fix` installs;
  adopt/upgrade/scaffold gstack ignore and `.envrc` additions (whichever upgrade code exists when this
  task runs); every `.gstack/` path token (`pre_tool_use.py`, `repo_kind.py`, `stages.py`,
  `check_refactor_delta.py`, `check_repo_budget.py`) where it still exists; this repo's
  `.gitignore`/`.gitattributes`/`.envrc` lines; tests (rewrite the two mixed `.envrc`/`.gitattributes`
  tests).
- gstack removal (docs): WORKFLOW, README, getting-started, ROLES, living specs, constitution README
  precedence, install skills; move `.gstack/projects/knacklabs-symphony-forge/` to
  `docs/context/gstack-archive/`, summarise its decisions and learnings in
  `docs/memory/gstack-history.md`, and mark the archive files harvested with that note as output.

## Task decomposition

The owner chose two tasks. FDE first, then GSTACK (both touch `harness.yaml`, `scaffold.py` and the
skill). Each ships its own pull request.

| Label / exact task ID | What it delivers | Depends on | user_facing |
|---|---|---|---|
| Skill / FDE | FDE skill section, reference file, DISCOVERY template, discovery owner and impeccable in `harness.yaml`, `forge payback`, success-measure validation, griller line, spec help and README, computed `forge next` check, `forge spec measure` | none | false |
| Removal / GSTACK | gstack command, doctor checks, direnv requirement, impeccable required and installed at a pinned version, adopt/upgrade/scaffold additions, path tokens, repo config lines, docs, living specs, install skills, tests; archive, summary note and harvest marks | FDE | false |

## Verify plan

Each task: focused tests, `forge task close` (full suite plus one three-lens review), the CI-only
checks, green CI. Tests cover `forge payback` at 3, 12 and unknown value; success-measure refusals
(missing, empty field, bad date) and acceptance with only the status changed; the pr-link check date,
the computed `forge next` listing and `forge spec measure`; doctor passing without gstack or direnv; a repo-wide
search finding gstack only in history and the archive; adopt/upgrade leaving client lines alone. Before
the story ships, a scripted walkthrough in a throwaway client runs discovery on a vague ask and
checks: one question per turn with "Why I ask", neutral options for facts, the stop at the limit, a
filled problem card named in the brief and spec, and the recorded choice.
