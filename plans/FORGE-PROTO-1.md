# A customer signs off a working prototype before any story exists

7 parts · Risks: migrations run when the container starts · New moving parts: one Dockerfile in new client repos

## What changes for you

- A new client project starts the FDE way: the agent first learns the customer's problem, then
  builds the smallest working prototype that tests it, and pushes back on requests the problem
  doesn't need. A salesperson can run this; a developer takes over later with everything in place.
- While the prototype is built, the agent asks the questions that change the build, one at a time,
  with our default and an "Ask the client" option: who signs off, existing systems, sign-in,
  personal data, where it runs, and more. Answers go on one page, each with who said it.
- Before sign-off, a strict review checks the whole prototype and the answers. Then the customer's
  named person signs off.
- No story can be created before that sign-off.
- A new client repo can go live on our deploy platform by connecting it and picking a subdomain.

## Why

Salespeople and developers want a prototype in front of the customer fast but can't tell whether
everything that shapes the build was asked, and today Forge lets stories exist before the customer
has seen anything. This story builds the confirmed spec `docs/specs/prototype-signoff.md`.

## Done when

1. **The spec is confirmed and on the roadmap.** `docs/specs/prototype-signoff.md` is confirmed by
   the owner and on the roadmap as FORGE-PROTO-1.
2. **Stories wait for sign-off.** In a client repo without an accepted client sign-off,
   `forge roadmap add` and `forge story new` (including `--from-fix`) refuse with a plain next step;
   with one they work as today; Forge's own repo is unaffected.
3. **Prototype fixes may be larger.** In a client repo without an accepted sign-off,
   `forge fix start` records the allowance "Prototype before sign-off"; with one it records none;
   a fix keeps the allowance it started with.
4. **The skill runs the FDE route and the twelve topics.** The Forge skill carries the FDE route for
   prototypes, the twelve-topic table with its questions, options, defaults and must-or-may-wait
   column, and the asking rules from the spec, and the synced skill copies match.
5. **One answers page.** `docs/product/BRIEF.md` in a new client repo has an `## Answers` section
   showing the answer, "ask the client" and "later" line formats from the spec.
6. **forge next lists what is still open.** In a client repo without an accepted sign-off,
   `forge next` lists each must-answer topic that is missing, "ask the client", marked later,
   repeated or malformed on the checkout's answers page.
7. **A strict review guards sign-off.** Accepting a client sign-off decision first runs one fresh
   Autoreview on GPT-6 Astra at high effort, with no model fallback, over every product file in the
   checkout together with the answers page and the topic table, and refuses on a blocking finding;
   a must-answer topic that `forge next` would list as open, or one sourced only from our default
   or the agent, blocks; the accepted decision records the reviewed commit.
8. **The sign-off names the customer's person.** A new client sign-off decision asks for the
   customer's named person and role, where (email or call) and when they approved, the demo
   address and the answers page quoted word for word; accepting it refuses when any is missing or
   the quote differs from the reviewed answers page; `--by` names who recorded it, never the
   customer.
9. **Deferred answers come back.** A story's cold read reports `Decide first: <topic>` when a
   Done-when item needs a topic the answers page marks later, and the skill tells the agent to ask
   that one question, record the answer in the finding's disposition and the story's Notes as
   `Decided: <topic>: <answer> (<source>, <date>)`, and have the story's first task update the
   answers page.
10. **A prototype deploys from one Dockerfile.** A new client repo gets a Dockerfile for the fixed
    stack that builds the frontend, serves it from the backend, runs migrations at start-up before
    serving, and answers `GET /health` only once they succeed; the stack conventions pin the build,
    serve, migrate and health commands the app follows, and a conventions page says how to deploy
    it on our platform.
11. **The docs describe the new order.** A decision supersedes 0014's order, and the README and
    guide describe the FDE route: discovery, prototype, review, sign-off, then stories.

## Risks

- Migrations run when the container starts, in production too. A destructive migration would
  change data at start-up. Contained by the standards' add-only migrations rule, one running
  instance, and a failed migration stopping the container before it serves, so the platform keeps
  the previous version.

## For the builders

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | The spec | The confirmed spec and its roadmap item | 1 | `docs/specs/prototype-signoff.md`, `docs/specs/prototype-signoff.read.md`, `plans/roadmap.json` | | none | no |
| GATE | Stories wait | The sign-off gate on roadmap add and story new, and the prototype allowance on fix start | 2, 3 | `src/forge/records.py`, `src/forge/story.py`, `src/forge/task.py`, `tests/test_approval.py`, `tests/test_githooks.py` | `tests/test_proto_gate.py` | none | yes |
| TOPICS | The FDE route and topics | The skill's prototype section, topic table and deferred-answer steps, the answers section in the brief template, the call script in the discovery template, and the cold read's Decide first check | 4, 5, 9 | `src/forge/templates/skill.md`, `.claude/skills/forge/`, `.codex/skills/forge/`, `src/forge/templates/skeleton/docs/product/`, `src/forge/templates/cold-read.md`, `tests/test_trim_skills.py`, `tests/test_split_ships.py` | `tests/test_proto_topics.py` | none | yes |
| NEXT | What is still open | The answers-page parser and forge next's list of open must-answer topics before sign-off | 6 | `src/forge/nextstep.py` | `tests/test_proto_next.py` | none | yes |
| SIGNOFF | Review, then sign-off | The Astra-high review at sign-off acceptance and the sign-off decision template | 7, 8 | `src/forge/records.py`, `src/forge/review.py`, `src/forge/templates/review.md` | `tests/test_proto_signoff.py` | NEXT | yes |
| DEPLOY | One Dockerfile | The fixed stack's Dockerfile in new client repos and the deploy conventions page | 10 | `src/forge/templates/skeleton/`, `src/forge/templates/conventions/`, `src/forge/init.py` | `tests/test_proto_deploy.py` | none | yes |
| DOCS | Say so | The decision superseding 0014's order, and the README and guide | 11 | `docs/decisions/`, `README.md`, `docs/guide.md` | `tests/test_proto_docs.py` | none | yes |

New moving parts: one Dockerfile in new client repos (Done-when 10)

## Notes

- GATE reuses `approval.signed_off(top)` as the one sign-off check; the refusal says: "Stories wait
  for the customer's sign-off. Build and demo the prototype first." with "Next: forge next". The
  allowance text is exactly "Prototype before sign-off", recorded in the fix state's
  `allow_large` field when `fix start` runs.
- TOPICS pins the answers line formats the other tasks read: `- <Topic>: <answer> (<source>,
  <YYYY-MM-DD>)`, `- <Topic>: ask the client (<who asked>, <date>)`, `- <Topic>: later, when
  <trigger>`, under `## Answers` in `docs/product/BRIEF.md`, and the topic names exactly as in the
  spec's table. The must-answer topics are the first seven rows.
- NEXT adds the one answers-page parser to `nextstep.py`, reading the checkout's own
  `docs/product/BRIEF.md`; SIGNOFF imports it. A topic counts as open when it is missing, "ask the
  client", marked later while it is a must-answer topic, repeated, or on a line that doesn't match
  the formats.
- SIGNOFF runs the review only when the accepted decision's slug ends in `client-signoff`. It
  reviews in Forge's review clone against an empty root commit made there, so every product file
  is in the diff (product files: every tracked file except `.factory/`, `plans/` and
  `docs/decisions/`), passing the model the way the existing invocation does
  (`codex=gpt-6-astra`) with high thinking and no fallback, and a test checks those arguments. It
  puts the reviewed commit in the decision's front matter as `reviewed_commit`.
- The sign-off decision's front matter carries `customer`, `approved_via`, `approved_on` and
  `demo`; its `## Answers` section is the reviewed answers page's section, word for word.
- DEPLOY pins the runtime contract in `src/forge/templates/conventions/stack.md` and the
  Dockerfile follows it: the frontend builds with `npm run build` in `frontend/` into
  `frontend/dist`, the backend serves that folder at `/` and starts with `npm run start:prod` in
  `backend/`, migrations run with `npx prisma migrate deploy` before the server listens, and
  `GET /health` answers 200; the platform provides Postgres through `DATABASE_URL`. The
  prototype's own first fix builds the app to that contract.
- The prototype runs with fake data; nothing here writes infrastructure code.
- Each test file starts with `STORY = "FORGE-PROTO-1"`, and its `test_<n>_` names cite the
  Done-when items its task covers.
