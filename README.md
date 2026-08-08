# Symphony Forge

KnackLabs's process harness for building applications with **Claude Code coordination** and **Codex execution** — from discovery and client sign-off through scaffolding, per-feature delivery, and a self-evolving record of every decision.

## Quick Start (devs)

Everything is conversation — setup included. In any Claude Code session, say:

> **"Clone the KnackLabs harness from `github.com/knacklabs/symphony-forge` and run its setup."**

(One time per machine. Prefer a terminal? `git clone git@github.com:knacklabs/symphony-forge.git && cd symphony-forge && ./setup` does the same.)

Then, in a session opened in that clone:

> **"Set up a new KnackLabs project called my-app"**

The bootstrap skill updates the harness, checks your machine and installs any missing tooling (only logins stay yours), scaffolds the new repo, asks which GitHub org/repo should own it and pushes it there, then hands you off to work in the new repo. From then on, **ask "what now?" in any phase** — the agent reads the project's recorded state and walks you to the exact next action (Codex sessions get the same answer via `AGENTS.md`). Every step's underlying command lives in [Getting Started](docs/getting-started.md) — the deterministic contract, not something you type.

## Template, Not Fork — how client repos relate to this one

The harness is a **dependency you vendor, not an ancestor you fork**. The
only thing anyone ever clones is this repo, once per machine, as a tool —
your application is born as its own repo with its own history:

```text
this repo (cloned once, per machine)             your app repo (its own repo, its own history)
┌─────────────────────────────┐  "set up a new  ┌─────────────────────────────┐
│ the generator + upgrader —  │   project…"     │ born fresh — ZERO git       │
│ agents run it when you ask  │ ───────────────▶│ relation to the harness     │
│                             │  copies ONLY    │ app code, plans, decisions, │
│ improves over time…         │  machinery      │ evidence: all yours         │
└─────────────────────────────┘ ───────────────▶└─────────────────────────────┘
                                 "update my-app
                                  to the latest
                                  harness"
```

- **Create**: open Claude Code in the harness clone and say *"Set up a new
  KnackLabs project called my-app."* The agent checks your machine, scaffolds
  a fresh git-initialized repo beside the harness, asks which GitHub org/repo
  should own it, pushes it there, and tells you to open future sessions in
  the new repo. The app is built *inside that repo* — the harness clone is
  never where app code lives.
- **Upgrade**: when this template improves, nothing is merged or pulled into
  the app. Say *"Update my-app to the latest harness."* The installed
  `knacklabs-upgrade-project` skill verifies and updates the harness clone,
  audits the clean client, rewrites ONLY the machinery, repairs tooling, and
  walks you through reviewing the diff. It then backfills project contracts,
  guides pending-story re-authoring with `forge roadmap fill`, re-verifies,
  and reports `forge next`; app code, completed stories, plans, docs, and
  evidence remain yours.
- **Never**: don't fork this repo (shared history means every upgrade becomes
  a merge into your app code, and the harness's own run state collides with
  yours) and don't use GitHub's template feature (clean copy once, but NO
  upgrade path ever — and it drags this repo's plans, history, and evidence
  along). If an agent proposes either, that's a bug — the skills forbid it.

Sentences are the whole interface: the skills route what you say to
deterministic commands, and [Getting Started](docs/getting-started.md) lists
those commands under every step — as the contract and the fallback, not as
something you type.

## The Lifecycle

```text
0a discovery ──▶ 0b prototype+specs ──[SPEC GRILLS]──▶ 0c derived roadmap ──[GRILL]──▶ CLIENT SIGN-OFF ──▶ roadmap + team
                                                                                       (hard gate)                 │
      ┌───────────────────────────────────────────────────────────────────────────────────────────────────────┘
      ▼
  per feature (own branch):
  intake ▶ PLAN MODE (forced) ▶ [GRILL] ▶ plan save ▶ decompose ▶ per stage: implement+test ▶ local review ▶ commit ▶ verify ▶ review ▶ [assumptions guided] ▶ PR
             (Claude)                     (+ surfaces)  (stages)          (Codex, attested)   (until clean)                  (ONE autoreview)     (ship gate)
```

- **Before sign-off**: discovery and prototyping are lightweight; capability
  specs are saved and grilled as they emerge, then the roadmap is derived from
  the confirmed set. The prototype remains the permanent UX reference.
- **After sign-off**: deterministic gates. Plans live in `plans/`, decisions in `docs/decisions/`, evidence in `.factory/`; the ship gate archives every shipped task's plan + proof to `plans/completed/` and `.factory/history/`.
- **Continuously**: dump raw context (client emails, transcripts, notes) into `docs/context/` — dumping is free, tracking is automatic. Say *"process the context dump"* and an agent scans it into the ledger, harvests it into proposed decisions and BRIEF/architecture updates, and marks each file. You can't miss pending context: it greets every session start, tops every *"what now?"*, raises a daily `gardener` issue, and **blocks plan approval** until harvested or explicitly ignored. Dev corrections get mined into proposed skills that humans promote.
- **The repo learns from itself**: review findings are structured and clustered across tasks — ask *"are we fixing the same thing again?"* and the agent shows which defect classes recur; the same class recurring 3+ times triggers a refactor story + invariant decision, never a fourth patch (decision 0005). Repeated failures become ledgered lessons that resurface before anyone touches the same paths again (decision 0006). Say *"this is out of scope for now"* and the parked scope keeps an explicit revisit trigger instead of vanishing.

Phase ownership — which tool runs which phase — is declared in [`harness.yaml`](harness.yaml).

## The Gates

Every handoff is an artifact plus a deterministic gate. You never operate the
gates — you ask for the next thing, and a skipped gate shows up as the agent
relaying a refusal that names exactly what's missing. The "Enforced by"
column describes that machinery. In lifecycle order:

| # | Gate | Refuses until | Enforced by |
|---|---|---|---|
| 1 | **Specs + derived roadmap** | every capability spec has a digest-bound grill and confirmed status; every derived story links one | `forge spec confirm`; `forge roadmap derive` |
| 2 | **Signoff grill** | an adversarial pass over DISCOVERY/BRIEF/specs/roadmap/decisions is fresh and `pass` | `record_signoff.py` |
| 3 | **Client sign-off** | an accepted `client-signoff` decision names a human, all specs are confirmed, and the roadmap covers them | `record_signoff.py`; every later phase checks the flag |
| 4 | **Roster check** | assignees exist on `plans/team.json` (when a roster is defined) | `forge roadmap assign` |
| 5 | **Planning lock** | product writes have an approved plan or a bounded, ledgered quickfix window | PreToolUse hook (decision 0013) |
| 6 | **Rescue-only invocation** | always: raw `codex exec` is denied in every phase, no escape hatch — `/codex:rescue` is the runtime | PreToolUse hook |
| 7 | **Plan grill** | the draft plan survives `/grill-me` vs the story's acceptance criteria + active decisions — same-issue, fresh, `pass` | `forge plan save` |
| 8 | **Surface Impact** | the plan classifies every surface (runtime/API/data/CLI/UI/docs/tests) — Deferred and Unchanged-by-design rows carry reasons | `forge plan save` |
| 9 | **Pending context** | every `docs/context/` dump is harvested or explicitly ignored (and scans REFUSE secrets/oversize files outright) | `forge plan save`; `context scan` |
| 10 | **Schema + generator + skill attestation** | every evidence payload matches its `factory/schemas/` file: `generated_by` on the allowlist, mandatory design skills attested in `skills_used` on user-facing artifacts | every `record_*` script |
| 11 | **Stage loop** | every decomposition stage ran its loop — order-enforced start, LOCAL autoreview until clean, commit, done | `forge stage start/done`; `pr_ready.py` refuses open stages (decision 0007) |
| 12 | **Assumptions guided** | every `forge plan assume` row for the task is confirmed/promoted by the orchestrator (`fix-needed` keeps blocking) | `pr_ready.py` |
| 13 | **Refactor ratchet** | a `kind: refactor` story shows non-positive net product-source line delta — refactors shrink or hold the line | `check_refactor_delta.py` in `pr_ready.py` |
| 14 | **Frozen gates** | the vendored gate surface (scripts, schemas, prompts, hook config) matches `constitution/VENDOR_MANIFEST.json` — locally edited gates make every other gate's evidence unverifiable; re-vendor or upstream, never patch in place | `check_vendor_integrity.py` in `pr_ready.py` (warned at session start) |
| 15 | **Ship gate** | approved plan, decomposition, verify OK, tests + 3 reviews ≥ 8 with no blockers, functional when `user_facing`, all evidence commit-stamped, same-commit, fresh | `pr_ready.py` — archives to `.factory/history/`, marks the roadmap item done |
| 16 | **Hygiene floor** | decision lifecycle intact (supersede links resolve, accepted records have substance), no prototype/ imports, schemas match harness.yaml, repo within size budgets | `check_dual_runtime.py` + `check_repo_budget.py` in CI |

Advisory (surfaced, never blocking): recurring finding classes — *"are we
fixing the same thing again?"* (3+ hits of one class ⇒ consolidate via a
refactor story, decision 0005); ledgered lessons — *"what did we learn about
these files?"*; parked scope whose trigger fired — *"did any deferral come
due?"*; and the loop-health audit — *"are the watchers themselves decaying?"*
(ignored escalations, stale deferrals, dead lessons: `forge audit`, run at
every ship, surfaced by `forge next`, and run daily in CI by the
`harness-health` workflow — which also opens an automated `forge upgrade`
PR when the vendored harness falls behind; merging it stays human).

Human-only, always: **accepting a decision** (sign-off, epics, promotions) —
the one command a person types themselves. The agent drafts the record,
relays the accept command, and waits; it never runs it.

## Who Runs What (skills by stage)

`harness.yaml` is the ALLOWLIST — these are the only pinned tools per stage,
and recorders refuse evidence from anything else (`generated_by` is checked
against `factory/schemas/`). Adopting a new tool = a PR here, never a local
choice.

**Devs only ever say the "You say" column.** The other columns are what the
AGENT invokes and records in response — shown so you know what happens on
your behalf, not for you to type.

| Stage | You say | Skill / agent invoked | Deterministic record |
|---|---|---|---|
| machine setup | "Set up my machine" | `knacklabs-new-project` skill → `./forge doctor --fix` | doctor report |
| new project | "Set up a new KnackLabs project called X" | `knacklabs-new-project` skill → `./forge init` | scaffolded repo |
| existing repo | "Migrate this repo into the harness" | `knacklabs-migrate-project` skill → `./forge adopt` | vendored machinery; old context → `docs/context/` |
| harness refresh | "Upgrade this repo to the latest harness" | `knacklabs-upgrade-project` skill → audit, upgrade, backfill, guided pending-story fill | reviewed and re-verified machinery upgrade |
| any phase, lost | "What now?" | `/forge` skill → `./forge next` | — |
| 0a discovery | "Let's run office hours" | gstack `/office-hours` | `docs/product/DISCOVERY.md`, `BRIEF.md`; design docs + decisions in `.gstack/projects/` (in-repo via `.envrc`) |
| 0b prototype | build freely; save/confirm specs as capabilities emerge | ponytail (lite) allowed | `prototype/` + `docs/specs/` |
| 0c roadmap | "Derive the roadmap" | `docs-decomposer` | `./forge roadmap derive` → spec-linked `plans/roadmap.json` |
| grills (every gate) | "Grill this spec" / "Grill the handover" / "Grill me on this plan" | `griller` contract; `/grill-me` satisfies the plan gate | digest-bound `.factory/grills/` records |
| sign-off | "The client signed off" | none — human confirms `decision accept` (chat confirmation suffices; agent may run it with their name) | `record_signoff.py` → `run.json` |
| workspace | "Scaffold the workspace" | Codex `/codex:rescue` + `SCAFFOLD_PROMPT.md` | nx workspace |
| stories + distribution (PM/EM) | "Review the roadmap", "assign ENG-101 to alice" | `./forge roadmap list` / `assign` / `team set` | derived stories with spec links, criteria, and `@assignee` |
| intake | "Start the next task on the roadmap" | `/forge` → `intake.py` | `.factory/run.json` |
| plan | "Plan this task" | Claude PLAN MODE — forced by the hook (or Codex `planner-high`); exploration ONLY via `/codex:rescue --model gpt-5.6-terra --effort high`, read-only | grilled plan → `./forge plan save` → `plans/active/` |
| decompose | "Decompose it" | `docs-decomposer` | `record_decomposition_from_json.py` (incl. `user_facing`) |
| implement + test | "Implement it" / "work the next stage" | Codex `/codex:rescue --background` per stage (implementer writes the tests); `user_facing` tasks MUST use `emil-design-eng` + `frontend-design` (attested in `skills_used`, enforced by the recorder); each stage ends LOCAL autoreview → commit | `./forge stage start/done` → `.factory/stages.json`; `record_test_from_json.py --kind automated` |
| lessons | "what did we learn about these files?" / "remember this" | none — deterministic ledger | `./forge lesson relevant` / `add` → `plans/lessons.jsonl` (schema-validated, deduped) |
| verify | "Run verify" | none — deterministic script | `verify.py` → `.factory/verify.json` |
| review | "Review it" | **autoreview** (ONE Codex run, three lenses) | `record_review_from_json.py` ×3 |
| functional check | only if `user_facing: true` | `functional-checker` subagent | `record_test_from_json.py --kind functional` |
| ship | "Is this PR ready?" | none — deterministic gate (refuses unguided assumptions, missing/stale evidence) | `pr_ready.py` → archives + roadmap done |
| guide assumptions (orchestrator) | "review the assumptions" | `./forge assumptions list --open` / `resolve` | `plans/assumptions.md` — ship gate reads it |
| context dump | drop files in `docs/context/`, then "scan the context" | `/forge` → `./forge context scan` | `docs/context/ledger.json` |
| context harvest | "Process the context dump" | agent per `harvester.md` → proposed decisions + BRIEF edits | `./forge context mark --harvested\|--ignored` |
| retro / evolution | "Mine for skills" / "are we fixing the same thing again?" | agent per `skill-miner.md` (incl. lessons curation) + daily `gardener` workflow; `./forge findings patterns` flags recurring classes | proposals in `factory/skills/proposed/`; refactor stories (`kind: refactor`, delta-ratcheted) on the roadmap |
| park scope | "this is out of scope for now" | none — deterministic ledger | `./forge defer add --why --trigger` → `plans/deferrals.md`; `forge next` surfaces open triggers |

## Structure

```text
symphony-forge/
├── factory/                        # Shared substance: prompts, deterministic scripts, proposed skills
├── .claude/                        # Claude Code adapter + /forge skill (thin, linter-enforced)
├── .codex/                         # Codex adapter: config, hooks, agent registrations (thin)
├── .factory/                       # Run state + per-task history archive
├── .github/workflows/              # Scaffold checks, dual-runtime lint, daily gardener
├── constitution/                   # KnackLabs engineering standards — THE single source of truth
├── docs/                           # Contracts, guides, decisions, context inbox
├── harness/nestjs-react/           # Scaffold prompt + stack conventions
├── harness.yaml                    # Phase ownership + skill precedence manifest
├── plans/                          # Task plans + durable ledgers: roadmap, assumptions, lessons, deferrals
├── AGENTS.md                       # The agent contract (both runtimes)
├── CLAUDE.md                       # Import shim: @AGENTS.md + @.claude/CLAUDE.md
└── forge                           # The agents' entrypoint — devs speak; agents run ./forge <cmd>
```

## Why This Shape

- **One canon, two runtimes.** Standards live once (`constitution/`, `AGENTS.md`, `harness.yaml`); `.claude/` and `.codex/` are thin adapters. `check_dual_runtime.py` fails CI on any duplication.
- **Gates at phase transitions — plus exactly one keystroke gate.** Hooks are quiet by default; the deterministic gates (`record_signoff.py`, `record_*` recorders, `pr_ready.py`) do the enforcing. The one sanctioned exception (decision 0004): while a task is unplanned, the hook denies product-code edits and forces PLAN MODE. `/codex:rescue` is the only Codex invocation — raw `codex exec` is denied everywhere.
- **Grill before every handoff.** Sign-off, epics, and every task plan pass an adversarial gaps-and-contradictions interrogation whose recorded verdict the gate checks — stale or blocked grills don't open doors.
- **Evidence is attested, not asserted.** Every artifact carries `generated_by` (allowlist-checked) and `skills_used` (mandatory design skills enforced on user-facing work), stamped to the commit it attests.
- **Decisions are exhaust, never forms.** Planning forces a Decisions section; harvesting turns raw context into records; humans confirm every `accepted`; replacements go through `--supersedes`, and accepted records must have substance.
- **Garbage cannot become contract.** Secret/size guards at the inbox, repo budgets in CI, prototype-import ban, gstack noise gitignored, ledgers compacted, rejected proposals remembered.
- **Evolution is curated.** Recurring corrections become *proposed* skills and constitution PRs; nothing self-activates. The fast loop is deterministic: lessons ledger in, relevance out (decision 0006); the slow loop is structural: recurring finding classes escalate to delta-ratcheted refactor stories instead of endless patches (decision 0005).
- **One owner per phase.** Overlapping skills (gstack `/ship`, ponytail in factory code, nested reviewers) are explicitly disabled in `harness.yaml`.

## Docs

- [Getting Started](docs/getting-started.md) — the blessed path, step by step
- [Roles](docs/ROLES.md) — PM / EM / dev: artifacts, phrases, approvals, handoffs
- [Workflow Contract](WORKFLOW.md) — phases, gates, grills, hygiene, evolution loop
- [Factory Contract](docs/FACTORY.md) · [Quality Contract](docs/QUALITY.md)
- [Constitution](constitution/README.md) — engineering standards index
- [Harness Philosophy](docs/harness-philosophy.md) · [Validation Loop](docs/validation-loop.md)
- [Product Brief](docs/product/README.md) · [Architecture](docs/architecture/README.md) · [Decisions](docs/decisions/README.md)
- [Context Inbox](docs/context/README.md) — dump files here, harvest tracked
- [Degraded Mode](docs/degraded-mode.md) — when codex-plugin-cc is unavailable
