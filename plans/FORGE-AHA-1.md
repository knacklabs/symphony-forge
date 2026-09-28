# The customer gets the aha moment

4 parts · Risks: none · New moving parts: the Agentation feedback toolbar in prototype demo builds

## What changes for you

- Before the first meeting, the agent drafts a one-page brief on the prospect from their website:
  likely jobs, a few guessed problems marked as guesses, their terms, and the first questions to ask.
- In the first conversation the agent keeps the customer's own words and asks for the spreadsheet or
  form they use today (the column headers are enough). The same day it drafts a short recap for the
  customer to confirm: their problem in their words, its cost in their numbers, the one task the
  demo will cover, who signs off, what we still need to know, and the demo date.
- The prototype is filled with realistic sample data shaped from their spreadsheet and labelled in
  their words, so the customer sees their own work, not empty screens.
- In a demo build, anyone can click a part of the screen, type what's wrong and paste it to the
  agent, which knows exactly which element was meant.
- Every demo follows a short script: their workaround today, the same job in the app, the time or
  money it saves in their numbers, then they take the controls. The link is sent after the demo.
- After each demo the agent records what the customer did, what they said and what they asked for,
  and sends a three-line "what changed" note with each new version.
- Prototype changes come back faster: before sign-off their review blocks only on serious problems
  (security, lost data, broken migrations); the full strict review still happens at sign-off.
- Before sign-off, one call reads every assumption back to the customer. Then the agent drafts the
  sign-off email the customer replies to.
- New projects no longer point at a discovery tool Forge removed.

## Why

The owner wants salespeople and customers to reach the "aha" fast. It happens when the customer does
their own weekly job in the app, in their own words, with data that looks like theirs, and hears
what it saves in their numbers. Forge covers building and sign-off records, but almost nothing the
customer sees, and every prototype round waits on a full review.

## Done when

1. **The agent prepares, listens and recaps.** The Forge skill and its FDE guidance tell the agent
   to draft a pre-meeting brief in `docs/context/` from the prospect's website (guessed problems
   marked as guesses), to keep the customer's words in `## Words they use` in
   `docs/product/DISCOVERY.md`, to ask for the customer's current spreadsheet or form and keep only
   its column headers, and to draft a same-day recap in `docs/context/` for the customer to confirm
   (their problem in their words, the cost in their numbers, the demo task, the sign-off person, the
   open "ask the client" questions and the demo date), whose reply is recorded as the source for the
   demo-workflow and sign-off-person answers.
2. **The demo looks like their work.** The stack conventions describe demo data: a loader in the
   app, shaped from the customer's column headers and labelled in their words, holding no real
   personal data, that runs only when `APP_ENV=demo` and `DEMO_DATA=1` are both set and every app
   table is empty, and otherwise refuses and inserts nothing; the testing conventions say shared
   seed data stays out of tests while demo data is allowed on the demo host; the skill tells the
   agent to build it in the prototype's first version and to use the "Words they use" list for
   screen labels.
3. **Anyone can point at the screen.** The frontend conventions add the Agentation toolbar to the
   app only when `APP_ENV=demo`, never in production builds, and the skill tells salespeople to
   click an element, write what's wrong and paste the output to the agent.
4. **Every demo follows the script.** The skill carries the five-step demo script (their workaround
   today, the same job in the app, the saving in their numbers, they take the controls, "what would
   stop you using this?"), says the link is sent only after the guided demo, and tells the agent to
   send a three-line "what changed" note with each new version.
5. **Reactions are kept.** After each demo the skill has the agent ask the salesperson what the
   customer did themselves, what they said word for word, and what they asked for, and write them
   under `## Prototype notes` in `docs/product/DISCOVERY.md`, tagging each request "serves the
   problem" or "after sign-off".
6. **Sign-off is read back and drafted.** Before the sign-off review the skill has the agent hold
   one read-back call that goes through every answer on the answers page (our defaults, the
   agent's guesses and the topics marked later) and settles every open must-answer topic in that
   call; after the review passes, the agent drafts the sign-off email for the reviewed version
   (its demo address, what the app does, the problem and the saving, every answer in plain words
   with the defaults called out, what happens next), whose reply is the approval evidence the
   sign-off decision records.
7. **Prototype changes are reviewed lightly.** In a client repo without an accepted sign-off,
   `forge close` on a fix whose allowance is "Prototype before sign-off" reviews with GPT-6 Sol at
   medium effort and blocks only on P0 findings; tests and CI still gate it; every other item is
   reviewed as today, and the sign-off review stays strict.
8. **No dead end.** A decision replaces `docs/specs/fde-discovery.md`'s `/office-hours` step with
   Forge's own discovery; the skill and FDE guidance no longer send a new project to gstack's
   `/office-hours`, and a test checks the synced copies no longer mention it.

## Risks

Risks: none

## For the builders

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | Prepare and listen | The pre-meeting brief, their words, the spreadsheet ask and the recap in the skill and FDE guidance, and the decision and edits that remove `/office-hours` | 1, 8 | `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `docs/decisions/`, `tests/test_trim_skills.py`, `tests/test_split_ships.py` | `tests/test_aha_prepare.py` | TEMPLATES | yes |
| TEMPLATES | Their words, demo data and pointing | The discovery template's Words they use and Prototype notes formats, and the demo-data, testing and frontend conventions | 2, 3 | `src/forge/templates/skeleton/docs/product/`, `src/forge/templates/conventions/` | `tests/test_aha_templates.py` | none | yes |
| DEMO | Demo to sign-off | The demo script, the what-changed note, reactions, the read-back and the sign-off email in the skill | 4, 5, 6 | `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `tests/test_trim_skills.py`, `tests/test_split_ships.py` | `tests/test_aha_demo.py` | SPEC | yes |
| REVIEW | Light prototype review | The lighter review for prototype fixes before sign-off | 7 | `src/forge/review.py`, `src/forge/close.py` | `tests/test_aha_review.py` | none | no |

New moving parts: the Agentation feedback toolbar in prototype demo builds (Done-when 3)

## Notes

- Opus writes SPEC's, TEMPLATES' and DEMO's text, as the owner asked for skills; a Codex worker
  builds REVIEW. Tests check each instruction and template section through `forge sync` and
  `forge init`, and that the old `/office-hours` route is gone from the synced skill and FDE page.
- TEMPLATES pins the formats SPEC and DEMO write: `## Words they use` with one `- <their word>:
  <what it means>` line each, and `## Prototype notes` with one dated block per demo holding
  `Did:`, `Said:` (quoted) and `Asked:` lines, each request ending in `(serves the problem)` or
  `(after sign-off)`.
- The demo-data loader and the Agentation toolbar are app code each prototype's first version
  builds to the conventions; Forge ships the conventions, not the code.
- REVIEW reads the prototype allowance exactly as FORGE-PROTO-1's GATE records it and passes
  Autoreview `--model codex=gpt-6-sol --thinking medium --max-priority P0`.
- The recap and sign-off email are drafts the salesperson sends; Forge sends nothing.
- Each test file starts with `STORY = "FORGE-AHA-1"`, and its `test_<n>_` names cite the Done-when
  items its task covers.
