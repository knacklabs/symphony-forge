# ROLES.md — who does what, and how work hands off

The harness is prompt-first for every role: say the phrase, the agent runs
the command. `./forge next` tags each step with the role that acts —
`[PM]`, `[EM]`, `[dev]`. This page is the map per seat.

The user and host select the main coordinator model and reasoning. Native
dispatch names a configured role and passes no model or reasoning override.
Decision 0079 routes routine implementation, automated tests, diagnosed or
review fixes, documentation edits, and mechanical refactors to Luna/max;
read-heavy exploration and dependency tracing to Terra/high; and planning,
decomposition, difficult diagnosis, independent grills, and final functional
checks to Sol/high. A difficult diagnosis returns its edit to Luna/max. Formal
code review remains exclusively the unchanged, externally maintained Autoreview
skill, whose internal model or agent calls are its own policy. No Forge or
native lane selects Luna/low. The native transport stays process-free: Forge
prepares the descriptor and the host owns subagent lifecycle without
Forge-managed process attribution.

## PM — product manager

Owns the business truth: what we're building and why.

| You do | You say / run |
|---|---|
| Discovery conversation | "Let's run office hours" (gstack `/office-hours`) |
| Product intent | own `docs/product/DISCOVERY.md` + `BRIEF.md` |
| Client decisions | "Record that as a decision" → you are the human who runs `./forge decision accept <slug> --by "<you>"` |
| Capability contracts | save specs during prototyping; each confirmation gets its own fresh spec grill |
| Derived roadmap | review the spec-linked epics/stories produced by `./forge roadmap derive` |
| **Grill before sign-off** | interrogate DISCOVERY/BRIEF/specs/roadmap/decisions for gaps and contradictions; `record_signoff.py` refuses without a fresh pass |
| Client sign-off | the `client-signoff` decision + `record_signoff.py`; the spec/roadmap coverage gate runs now |
| Scope changes later | epics live in `plans/roadmap.json` (`epics` block) — change them by PR |

## EM — engineering manager

Owns the backlog shape and distribution: epics → stories → devs.

| You do | You say / run |
|---|---|
| **Stories (the EM→dev handoff)** | review and distribute the derived roadmap; every story carries its source `spec`, criteria, epic, skill, and order |
| Groom / extend | add a story only with its confirmed `--spec`; edit `plans/roadmap.json` by PR |
| Define the team (optional, recommended) | `./forge team set <handle> --role dev --skills frontend,backend` — makes distribution checkable |
| Distribute | `./forge roadmap assign <KEY> --to <dev>` — validated against the roster; match item `skill` to dev skills (a fullstack dev can take anything; specialists take their lane). Assignments survive re-imports |
| Watch the board | `./forge roadmap list` (grouped by epic, shows @assignee) — `forge next` flags unassigned pending items to you |
| Plan quality | the native Plan Mode approval after `forge plan save` is your review point — approve the exact final digest only when it satisfies the story's acceptance criteria |
| Guide implementation assumptions | `./forge assumptions list --open` → `resolve <id> --status confirmed\|fix-needed\|promoted --notes "..."` — every call the plan didn't cover lands in `plans/assumptions.md`, and `pr_ready` refuses to ship a task with unguided rows |

## dev — developer

Owns one story at a time, on its own branch (see Concurrency in WORKFLOW.md).

| You do | You say |
|---|---|
| Pick your story | "what's next?" — `forge next` names the next pending item (and its assignee); intake creates your branch |
| Plan → implement → ship | the feature loop: "Plan this task" → one independent cold grill with every finding disposed → native approval of the exact final plan → "Implement it" → "Review it" → "Is this PR ready?" — every step is gated and prompt-first (docs/getting-started.md §8) |
| Assumptions | "record an assumption" the moment you make a call the plan doesn't cover |
| Full-stack vs specialist | your roster `skills` say what the EM routes to you; a story's `skill` field says what it needs |

## Handoff summary

```text
prototype ──[spec grills]──▶ confirmed specs ──▶ derived roadmap
         ──[sign-off grill + decision]──▶ PM/EM review + assign ──▶ dev
```

Every handoff is an artifact plus a gate. Plan and task handoffs use one
independent cold grill whose exact input, complete finding dispositions, and
amendments bind the final artifact; native Plan Mode records the human's exact
digest approval. In native Codex, `forge grill run ...` prepares one griller
descriptor; Main sends that complete descriptor and its context metadata in the
actual `spawn_agent` message, then records the exact returned JSON through
`record_grill_from_json.py --cold-result <path> --preparation-id <id>`. Claude
keeps its command-managed cold-reader lifecycle. Other handover grills retain
their owning recorder. Never a conversation that evaporates. Humans accept;
agents do the rest.
