---
slug: prototype-signoff
title: A customer signs off a working prototype before any story exists
status: confirmed
saved: 2026-09-28T10:20:17+00:00
confirmed_by: "vrknetha"
confirmed_hash: 69bc4fdb3b05cbde845b6b8472cd936e55761276bd39cc3059e7a6a2086dc39f
---

# A customer signs off a working prototype before any story exists

## Why

People who start a client project with Forge, developers and salespeople alike, want a working
prototype in front of the customer fast. Most can't tell whether everything that shapes the build
has been asked: which systems the client already uses, where the app will run, how people sign in,
whether personal data is involved. Today Forge's discovery covers only the business problem (the
problem card), a story's interview stops after eight questions, and nothing asks about hosting,
existing systems or sign-in. Stories can be created before the customer has seen anything:
sign-off is checked only when a story is approved, never when one is created, and decision 0014
even asks for a roadmap before sign-off. Forge also offers no quick way to put a prototype where
the customer can try it.

The owner wants the opposite order, on the FDE route: understand the customer's pain first, build
and show the smallest working prototype that tests it on the fixed stack (backend, frontend,
Postgres), ask every question that changes the build one at a time, have the whole prototype
strictly reviewed, get the customer's sign-off, and only then create stories. The same application
then grows into the production app, without a rewrite.

## Behaviour

**The prototype follows the FDE route.** A prototype starts from FDE discovery as the Forge skill
runs it today: the customer's job, today's workaround, what it costs, who feels it, how often, and
the evidence. The prototype is the smallest working slice that tests the riskiest part of that
problem, not a build of every feature asked for; the agent says so plainly when a request doesn't
serve the problem card, and offers to note it for after sign-off. The salesperson acts as the FDE
at first. When a developer takes over, they become the FDE: the discovery notes, the answers page
and the customer call script carry everything over, and `forge next` tells them where things stand.

**Stories wait for sign-off.** In a client repo, `forge roadmap add` and `forge story new`,
including promotion from a fix, refuse until the repo's client sign-off is accepted. The refusal
says in plain words to build and demo the prototype first, and names the next step. Specs can still
be saved and confirmed before sign-off. Forge's own repo is unchanged, and a client repo whose
sign-off was accepted before this change stays signed off.

**Before sign-off, work is prototype fixes.** In a client repo without an accepted sign-off,
`forge fix start` records the allowance "Prototype before sign-off", so a prototype fix may go over
the fix size limit and change interfaces. Every prototype fix still gets its worker, tests, review
and pull request as today. A fix keeps the allowance it started with; fixes started after sign-off
get none.

**Twelve topics, asked when each first matters.** The Forge skill carries this table. The agent
asks one topic at a time, when it first matters to what is being built, and skips a topic the repo
already answers. Our default, where there is one, is the first option; questions of fact have no
default. Every question also offers "Ask the client", which adds it to the customer call script,
and topics that may wait also offer "Decide later".

| Topic | Question | Options (default first) | Before sign-off |
|---|---|---|---|
| Sign-off person | Who at the customer approves the prototype? | name and role | must |
| Demo workflow | Which one task should the demo let them do from start to finish? | from the problem card | must |
| Users and roles | Who uses it, and what can each kind of user do? | admin and staff; other | must |
| Existing systems | Which systems must this work with? | none; CRM; accounting; email or SMS; payments; company sign-in | must |
| Sign-in | How will people sign in? | email and password; company sign-in (Google or Microsoft) | must |
| Personal data | Will it hold personal, health or payment data, or data that must stay in one country? | none; personal only; regulated | must |
| Production host | Where will the real app run? | our platform; the client's cloud; the client's servers | must |
| Data import | Does data need to come in from today's tools? | no; a spreadsheet; another system | may wait |
| Email or SMS | Which provider sends messages? | none yet; the client's provider | may wait |
| Domain | Which web address? | our subdomain; the client's domain | may wait |
| Backups and uptime | How much downtime or data loss is acceptable? | the platform's daily backups; stricter | may wait |
| Log retention | How long must logs be kept? | the platform's default; longer | may wait |

Anything Forge's standards already decide (logging, security, error handling) is not asked; it
takes our default and appears in the read-back.

**One answers page, each answer with its source.** Answers live in a new `## Answers` section of
`docs/product/BRIEF.md`, one line per topic: `- <Topic>: <answer> (<source>, <YYYY-MM-DD>)`, where
the source is the client, the salesperson, the developer, our default or the agent. An open topic
reads `- <Topic>: ask the client (<who asked>, <date>)` or, for a topic that may wait,
`- <Topic>: later, when <what triggers it>`. The call script in the discovery notes lists every
"ask the client" line; when the answer comes back, the line is replaced with it and its source.

**A checkpoint before the review.** Before the sign-off review, `forge next` lists every
must-answer topic that is missing or still "ask the client", and the agent walks through them one
at a time. A topic that "may wait" and is marked later does not block.

**A strict review before sign-off.** The sign-off decision is committed as a fix. Accepting it
first merges the default branch into that fix's checkout and runs one fresh review on GPT-6 Astra
at high effort, with no model fallback, over every product file in that checkout together with the
answers page and the topic table. A must-answer topic that is missing, "ask the client", or sourced
only from our default or the agent is a blocking finding, as is a prototype that doesn't match the
answers. Blocking findings refuse the acceptance; any change to the checkout after the review needs
a new one. The accepted decision records the reviewed commit and the answers page it quotes. Later
changes to the prototype do not undo an accepted sign-off.

**The customer's named person signs off.** The sign-off decision names the customer's person,
where they approved (an email or a call, with its date), the demo address, and quotes the answers
page word for word, so every default is read before signing. The salesperson or developer records
it; nobody on our side signs off in the customer's place.

**Deferred answers come back when needed.** A story's cold read reads the answers page. When a
Done-when item needs a topic still marked later, the reader reports `Decide first: <topic>`. The
agent asks the human that one question; the finding's disposition records the answer, the story
doc's Notes carry it as `Decided: <topic>: <answer> (<source>, <date>)`, and the story's first task
updates the answers page. No second cold read is needed. Until then the prototype uses a fake
provider, as the standards already require for external services.

**The prototype deploys to our platform.** Our deploy platform, in our own AWS account, builds a
repo's Dockerfile and provides Postgres: connect the GitHub repo, pick a subdomain, and it
deploys. A new client repo gets one Dockerfile for the fixed stack: it builds the frontend, the
backend serves it, runs its migrations at start-up and answers a health check. The prototype runs
with fake data. Production later runs the same image on the host the answers name, through stories
after sign-off.

## Acceptance criteria

1. In a client repo without an accepted sign-off, `forge roadmap add` and `forge story new`
   (including `--from-fix`) refuse with a plain next step; with one, they work as today; Forge's
   own repo is unaffected.
2. In a client repo without an accepted sign-off, `forge fix start` records the allowance
   "Prototype before sign-off"; with one, it records none.
3. The Forge skill carries the FDE route for prototypes, the twelve-topic table and the asking rules
   above, and the synced skill copies match.
4. `docs/product/BRIEF.md` in a new client repo has an `## Answers` section with the line formats
   above.
5. `forge next` in a client repo without an accepted sign-off lists the must-answer topics that are
   missing or "ask the client" on the answers page.
6. Accepting a client sign-off decision runs the Astra-high review first and refuses on a blocking
   finding; a missing must-answer topic, an "ask the client" one, or one sourced only from our
   default or the agent blocks; the accepted decision records the reviewed commit.
7. The sign-off decision template asks for the customer's named person, where and when they
   approved, the demo address and the quoted answers.
8. A story's cold read reports `Decide first: <topic>` when a Done-when item needs a topic the
   answers page marks later.
9. A new client repo gets a Dockerfile for the fixed stack that builds the frontend, serves it from
   the backend, runs migrations at start-up and answers a health check, and the guide says how to
   deploy it on our platform.
10. A decision supersedes 0014's order, and the README and guide describe the FDE route: discovery,
    prototype, review, sign-off, then stories.

## Success measure

- Metric: on the next client project started after this ships, stories created before an accepted
  sign-off; hours from the first prototype fix merging to the prototype answering on its subdomain;
  must-answer topics found unanswered after sign-off.
- Baseline: stories can be created at any time; there is no prototype deploy path; the topics are
  never asked.
- Target: no stories before sign-off; under 8 working hours to a live prototype; no must-answer
  topic found unanswered after sign-off.
- Check date: 2026-10-31

## Out of scope

- A `forge prototype` or `forge deploy` command, a separate prototype repo or lane.
- A question database, form, or separate deferral ledger.
- Looser standards for prototype code.
- Per-pull-request preview environments, and infrastructure code (such as Terraform) before
  sign-off; the Dockerfile is the only deploy file.
- Changes to our deploy platform itself.
- Choosing the production host; the answers page decides it per customer.

## Roadmap

- FORGE-PROTO-1: A customer signs off a working prototype before any story exists
