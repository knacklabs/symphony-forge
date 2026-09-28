# The customer gets the aha moment

2 parts · Risks: none · New moving parts: none

## What changes for you

- Before the first meeting, the agent drafts a one-page brief on the prospect from their website:
  likely jobs, a few guessed problems marked as guesses, their terms, and the first questions to ask.
- In the first conversation the agent keeps the customer's own words and asks for the spreadsheet or
  form they use today (the column headers are enough). The same day it drafts a short recap for the
  customer to confirm: their problem in their words, its cost in their numbers, the one task the
  demo will cover, who signs off, what we still need to know, and the demo date.
- The prototype is filled with realistic sample data shaped from their spreadsheet and labelled in
  their words, so the customer sees their own work, not empty screens.
- Every demo follows a short script: their workaround today, the same job in the app, the time or
  money it saves in their numbers, then they take the controls. The link is sent after the demo.
- After each demo the agent records what the customer did, what they said and what they asked for,
  and sends a three-line "what changed" note with each new version.
- Before sign-off, one call reads every assumption back to the customer. Then the agent drafts the
  sign-off email the customer replies to.
- New projects no longer point at a discovery tool Forge removed.

## Why

The owner wants salespeople and customers to reach the "aha" fast. It happens when the customer does
their own weekly job in the app, in their own words, with data that looks like theirs, and hears
what it saves in their numbers. Forge covers building and sign-off records, but almost nothing the
customer sees.

## Done when

1. **The agent prepares, listens and recaps.** The Forge skill and its FDE guidance tell the agent
   to draft a pre-meeting brief in `docs/context/` from the prospect's website (guessed problems
   marked as guesses), to keep the customer's words in a `## Words they use` section of
   `docs/product/DISCOVERY.md`, to ask for the customer's current spreadsheet or form and keep only
   its column headers, and to draft a same-day recap in `docs/context/` for the customer to confirm
   (their problem in their words, the cost in their numbers, the demo task, the sign-off person, the
   open "ask the client" questions and the demo date), whose reply is recorded as the source for the
   demo-workflow and sign-off-person answers.
2. **The demo looks like their work.** The stack conventions describe demo data: a loader in the
   app, shaped from the customer's column headers and labelled in their words, that runs only when
   `DEMO_DATA=1` against an empty database on the demo host and never in tests, holding no real
   personal data; the testing conventions say shared seed data stays out of tests while demo data
   is allowed on the demo host; the skill tells the agent to build it in the prototype's first
   version and to use the "Words they use" list for screen labels.
3. **Every demo follows the script.** The skill carries the five-step demo script (their workaround
   today, the same job in the app, the saving in their numbers, they take the controls, "what would
   stop you using this?"), says the link is sent only after the guided demo, and tells the agent to
   send a three-line "what changed" note with each new version.
4. **Reactions are kept.** After each demo the skill has the agent ask the salesperson what the
   customer did themselves, what they said word for word, and what they asked for, and write them
   under `## Prototype notes` in `docs/product/DISCOVERY.md`, tagging each request "serves the
   problem" or "after sign-off".
5. **Sign-off is read back and drafted.** Before the sign-off review the skill has the agent hold
   one "here's what we assumed" read-back of every default and open must-answer topic, and after it
   draft the sign-off email (demo link, what the app does, the problem and the saving, every answer
   in plain words with the defaults called out, what happens next) whose reply is the approval
   evidence.
6. **No dead end.** The skill and FDE guidance no longer send a new project to gstack's
   `/office-hours`; discovery is Forge's own, and the synced skill copies match.

## Risks

Risks: none

## For the builders

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | The agent's journey | The skill's and FDE guidance's pre-meeting, recap, demo script, reactions, read-back and sign-off email, and removing the `/office-hours` step | 1, 3, 4, 5, 6 | `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `tests/test_trim_skills.py`, `tests/test_split_ships.py` | `tests/test_aha_journey.py` | none | yes |
| TEMPLATES | Their words and demo data | The discovery template's Words they use and Prototype notes format, and the demo-data and testing conventions | 1, 2, 4 | `src/forge/templates/skeleton/docs/product/`, `src/forge/templates/conventions/` | `tests/test_aha_templates.py` | none | yes |

New moving parts: none

## Notes

- Opus writes both tasks' text, as the owner asked for skills; the tests check that each instruction
  and template section exists in the synced copies and a new repo's files, through `forge sync` and
  `forge init`.
- The demo-data loader itself is app code that each prototype's first version builds to the
  convention; Forge ships the convention, not the loader.
- The recap and sign-off email are drafts the salesperson sends; Forge sends nothing.
- Each test file starts with `STORY = "FORGE-AHA-1"`, and its `test_<n>_` names cite the Done-when
  items its task covers.
