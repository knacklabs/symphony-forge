# WORKFLOW.md — Symphony-Style Codex Factory

## Source of Truth
- The repo owns workflow policy, prompts, run artifacts, plans, and decisions —
  it is the canonical state.
- An external tracker (Linear, GitHub Issues, Jira) is OPTIONAL: when one is
  used, roadmap stories are mirrored into it. Decomposition and task state
  remain in the repo under `.factory/stories/<key>/decomposition.json` and
  `plans/`; `.factory/decomposition.json` is upgrade-only legacy input.
- GitHub mirrors branch, PR, checks, and review evidence.
- gstack output is PROJECT-LOCAL: `.envrc` pins `GSTACK_HOME` to
  `<repo>/.gstack` (activate with `direnv allow`), so office-hours design
  docs, the decision store, and learnings are committed under
  `.gstack/projects/<slug>/` — shared by every dev, never stranded in a
  personal `~/.gstack`. Machine noise (sessions, analytics, browser profiles)
  is gitignored. Append-only Forge ledgers use one record per file; remaining
  legacy JSONL stays readable and uses Git's built-in `union` driver while it
  lasts. No custom merge driver is registered. History already in a personal
  store: `./forge gstack migrate`.
- Product intent lives in `docs/product/BRIEF.md`.
- Architecture and decision docs live in the repo under `docs/architecture/` and `docs/decisions/`.
- Durable project facts live under `docs/memory/`; SessionStart injects its
  `MEMORY.md` index into both runtimes.
- `docs/decisions/` overrides ambiguous or conflicting architecture guidance.

## Runtime Modes
Either Claude Code or native Codex coordinates the same Forge phase engine.
Claude dispatches protected work through `codex-plugin-cc`. Native Codex uses
the host's role-based `spawn_agent` subagents. Dispatch passes no model or
reasoning override, so the selected configured role's defaults apply. Both
routes preserve the active task, worktree and effective scope and produce the same
`.factory` artifacts, but native delivery deliberately has no Forge-managed
process identity or lifecycle proof.

Hooks resolve the repository from the session's working directory. A session in
another checkout records no native Plan Mode approval, and task gates cannot see
its in-session edits; open a new session in the task worktree for task approval
and in-session edits. The primary checkout on the default branch is the
coordinator's home for coordination work (status, merges, and Lite windows run
by path). Reach other worktrees by absolute path (`git -C <path>` or subprocess
cwd). Never `cd` a session shell to a directory that is not a checkout, because
every hook then refuses every command; if stranded, resume the session from a
checkout.

The main coordinator model and reasoning remain the user's and host's choice.
Decision 0083 routes native roles by work: Luna/max handles routine
implementation, automated tests, diagnosed or review fixes, documentation
edits, and mechanical refactors; Sol/medium handles read-heavy exploration and
dependency tracing; Sol/high handles planning, decomposition, difficult
diagnosis, independent grills, and final functional checks. A difficult
diagnosis returns its resolved edit to the Luna/max execution role. A delegated
or lite thread is the task lead on Sol/medium; it hands edits to Luna/max
subagents. Formal code
review stays exclusively with the unchanged, externally maintained Autoreview
skill, which may choose its own internal Codex or agent calls. No Forge or
native lane selects Luna/low.

### Workflow Modes

- **Full** is the standard workflow: an approved plan proceeds through bounded
  stages, deterministic verification, autoreview, and the remaining gates.
- **Lite** is a human-opened, bounded write window for a small supervised fix:
  `./forge mode lite --by "<name>" --reason "<why>"`. It returns to Full when
  the committed fix is within its file budget, `./forge review --lite` records
  all three clean aspects, and `./forge mode done` closes the window.

## Factory Phases
0a. `discovery` — lightweight problem, stakeholder, and constraint discovery; no `.factory` ceremony required.
0b. `prototype` — prototype freely and save capability specs as they emerge; no `.factory` ceremony required.
0c. `roadmap` — confirm the specs, then derive epics and stories from them.
1. `planning`
2. `decomposing`
3. `awaiting-approval`
4. `implementing`
5. `testing`
6. `reviewing`
7. `functional-check`
8. `pr-ready`
9. `done` or `blocked`

The sign-off gate sits between roadmap derivation and planning, and it fires
ONCE for the project — not once per task. Recording accepted client sign-off
with `python3 factory/scripts/record_signoff.py` requires at least one
confirmed spec, a derived roadmap with at least one story, and every confirmed
spec referenced by a story. It then PINS that record in `harness.yaml`
(`signoff_record:`), and every gate DERIVES sign-off from the committed pin —
so a fresh worktree with no `.factory/` reads the same answer, and nothing
per-task can re-point it. Re-running on a signed-off project is refused;
changing the pin is a reviewed edit. `update_run.py` and `pre_tool_use.py`
refuse phases at `planning` or later until the pin resolves to an accepted,
human-confirmed record. The per-task human gate is plan approval, not a second
sign-off.

Every handover gate is preceded by a recorded GRILL
(`factory/prompts/griller.md`): an adversarial gaps-and-contradictions
interrogation of what one role hands the next. Confirming each spec requires a
fresh pass bound to that spec. Five scopes are enforced: `spec`, `signoff`,
`epics`, `plan`, and `task`. The first four cover capability confirmation,
client→PM context, the derived backlog, and the story plan. The per-leaf
`task` grill introduced by decision 0032 (JIT task planning) interrogates the
just-authored task contract against the real state left by completed stages.
Its verdict lands in `.factory/grills/tasks/<id>.json` and is bound to the
contract digest over `write_scope`, `required_tests`, `verify_commands`, and
`acceptance_criteria`; a write `forge delegate <id>` refuses a missing,
non-passing, or stale record. Other verdicts land in
`.factory/grills/<gate>.json`. All records go through
`record_grill_from_json.py` (schema-validated, `generated_by: griller`).
Findings must resolve into contract/doc edits or decision records before a
`pass` is recordable.

In native Codex, `./forge grill run --gate plan --file <plan-file>` prepares
one self-contained descriptor bound to the exact artifact and returns its
preparation ID; it launches no helper or `codex exec`. Main puts the complete
descriptor, including all context metadata, in the actual message to the
configured `griller` role. It then records that subagent's exact JSON with
`python3 factory/scripts/record_grill_from_json.py --gate plan --input
<grill-json> --input-digest <plan-file> --cold-result <path>
--preparation-id <id>`. A native task grill uses `./forge grill run --gate
task --task <id>` and `python3 factory/scripts/record_grill_from_json.py --gate
task --task <id> --input <grill-json> --cold-result <path>
--preparation-id <id>`; task gates have no `--input-digest`. The recorder
validates the result/preparation binding without PID, session, or
process-lifecycle proof. Claude retains the protected command-managed
cold-reader lifecycle.

## Context Inbox & Doc Upkeep

Unstructured context (client emails, transcripts, notes) goes in
`docs/context/` — dumping is free, tracking is mandatory. `forge.py context
scan` registers files in `docs/context/ledger.json` (CI enforces freshness);
an agent following `factory/prompts/harvester.md` turns pending files into
proposed decision records and BRIEF/architecture edits, then marks them
harvested with their outputs (`--ignored` requires notes). Pending context is
surfaced on four channels: the SessionStart hook count, step 1 of
`forge next`, the daily gardener issue, and — the hard stop — `plan save`
refuses while anything is pending. Broader doc freshness
follows `harness/nestjs-react/conventions/doc-gardening.md` (gardening agent —
convention today, not yet automated).

## Repo Hygiene — garbage cannot become contract

Devs will throw everything at the repo (gstack exhaust, old prototypes, raw
text). The doors check what enters; these mechanisms manage what accumulates:

- **Inbox guards**: `context scan` REFUSES files over 5MB and files with
  secret-shaped content (keys, tokens, credentials) — refused files stay
  unscanned, so the plan gate keeps blocking until they're fixed. The inbox
  itself is append-only by design (raw record); agents work from
  `context list --pending`, never by listing the directory.
- **Decision lifecycle**: statuses are `proposed | accepted | superseded` —
  never deleted, never hand-flagged. Replacing a decision goes through
  `forge.py decision new <slug> --supersedes <old-slug>`, which cross-links
  both records; the linter enforces both pointers resolve, that superseded
  records name their successor, and that ACCEPTED records have real
  Context/Decision/Consequences substance (boilerplate is refused). Agents
  read the live corpus via `forge.py decision list --active`; the retro
  (skill-miner) sweeps active decisions for mutual contradictions and
  proposes supersessions.
- **Prototype isolation**: the linter fails any production code importing
  from `prototype/` — reference forever, imported never is enforced, not
  hoped.
- **gstack noise**: derived caches (`brain-cache/`), per-session churn
  (`timeline.jsonl`), and slug caches are gitignored and excluded from
  `gstack migrate`; only design docs, decisions, and learnings are record.
- **Budget watchdog**: CI runs `check_repo_budget.py` — any tracked file
  over 5MB fails, and `docs/context/`, `.gstack/`, `prototype/` have
  cumulative budgets with early warnings. The budget is the backstop for
  the categories nobody predicted.
- **Ledger compaction**: `forge.py assumptions archive` moves resolved rows
  from finished tasks to `plans/assumptions-archive.md` at milestones;
  rejected skill proposals move to `factory/skills/rejected/` (the miner's
  memory — it must not re-propose them without materially new evidence).

## Evolution Loop

Dev corrections are the harness's training data. At retro cadence, an agent
following `factory/prompts/skill-miner.md` mines recurring patterns (3+
occurrences: fix-after-review commits, repeated blockers, superseded
decisions) into PROPOSALS under `factory/skills/proposed/` — skills, memory
lines, or constitution changes, each with cited evidence. Humans promote or
reject; nothing self-activates. The daily `gardener` workflow opens a
GitHub issue whenever unharvested context or unreviewed proposals exist, and
the SessionStart hook surfaces the same counts at the start of every agent
session. The `/forge` Claude skill routes all of this.

## Recurring Findings — a design signal

Review findings accumulate per task
(`.factory/stories/<issue>/tasks/<task>/reviews/`;
findings are structured `{category, area, summary}` per the review schema).
`./forge findings patterns` clusters them by class; `forge next` and
`pr_ready` surface any class recorded 3+ times. The rule (decision record
`recurring-findings-escalation`): when the SAME class of issue surfaces more
than twice in one area, STOP patching findings individually — recurring
findings are a design signal, not a fix queue.

- First distinguish a recurring **CLASS** (the same failure shape respawning —
  the dangerous signal) from a converging **TAIL** (distinct real findings,
  severity/count trending down — healthy, keep going). Do not over-escalate
  a tail; do not under-escalate a class.
- **CONSOLIDATE** when the churning area is self-contained and the reviews
  have effectively specified the correct invariant: write the invariant as a
  decision record, add a refactor story to the roadmap (`kind: refactor`)
  that audits every site against it in one pass, and pin it with tests.
- **SPLIT OUT** when the churn exists because the item is entangled with
  other subsystems or is cycle-sized wearing a "quick win" label: remove it
  from the current branch and defer it with an explicit revisit trigger
  (`./forge defer add`).
- Set the tripwire in advance ("if round N still churns X, split it") — in
  the plan or the grill's `open_items` — and HONOR it.

## Loop Health — the watchers are watched

The harness is a graph of improvement loops, and a graph of loops fails in
its own way: circularly, every advisory green while nothing touches reality.
The rules below keep it grounded. Every active phase also follows
[`docs/QUALITY.md` bounded recovery](docs/QUALITY.md#bounded-recovery): repeated
unchanged failures require a diagnosed and tested fix before another model run.

- **The audit loop** (decision `loop-health-audit`): `./forge audit` checks
  the improvement loops themselves — RECURRING classes that keep shipping
  past their escalation with no consolidating decision or refactor story,
  open deferrals past 60 days (re-check the trigger), lessons whose
  `applies_to` globs no longer match any tracked file (a rotted sensor), and
  reviews that stopped emitting structured findings (a blind clusterer). It
  runs at ship cadence (`pr_ready` prints the summary; `forge next` surfaces
  the count) and is ADVISORY: audit output routes work to the roadmap or the
  ledgers — it never blocks the ship that happened to trip it.
- **Calendar cadence** for idle repos: the daily `harness-health` workflow
  runs the audit + integrity check and maintains a "Harness health" issue,
  and — when the vendored harness is behind — runs `forge upgrade` on a
  branch and opens the PR. The harness repo is public: no secret, no setup;
  an unreachable harness degrades to audit-only. The ceiling is fixed:
  automation DETECTS and PROPOSES; merging the upgrade and accepting
  decisions stay human. Nothing self-activates.
- **Frozen gates** (decision `frozen-gate-integrity`): an optimizing loop
  must never tune its own held-out set. `forge init/adopt/upgrade` freeze the
  vendored gate surface (`factory/scripts|schemas|prompts`, `forge`,
  `.claude/settings.json`) into `constitution/VENDOR_MANIFEST.json`;
  `check_vendor_integrity.py` compares, the SessionStart hook warns on drift,
  and `pr_ready` refuses it — a tampered gate invalidates every other gate's
  evidence. Fix direction is always outward: re-vendor via `forge upgrade`,
  or upstream the change to the harness. Never patch gate machinery in place.

## Event-Driven Delegation — signals

Delegation is not fire-and-forget. Under Claude, the orchestrator watches
`.factory/signals.jsonl` and the plugin companion job. Under native Codex, it
uses the host's ordinary subagent coordination features; Forge adds no
foreground/background, status, cancel, resume, process, session or PID rules.
A worker raises a
signal the moment it hits a `contradiction` (plan vs decision vs doc),
genuine `confusion`, a hard `blocked`, or a `scope-change` — via
`forge.py signal raise --kind <k> --by <agent> -m "<sentence>"` — and PAUSES
that thread instead of guessing. The orchestrator resolves the event
(`forge.py signal resolve <id> --notes "<answer>"` — an answer, a decision
record, or a plan revision) and resumes the worker with the resolution.

The orchestrator ANSWERS IT ITSELF, records the reasoning in `--notes`, and
resumes — it does not relay the signal to the human — whenever the answer
follows from what is already decided:

- a `review_budget` ceiling reached: raise it with headroom and say why. The
  ceiling stops runaway scope; it is not a statement about what the task must
  do, and it is not a number worth a human's attention.
- `write_scope` one or two files short of what the work mechanically implies —
  a lockfile, a barrel/index file, a generated type, a doc reference to a
  renamed script: extend the scope, name each file and why the work implies it.
- a sandbox or environment block with a documented path (`docs/degraded-mode.md`,
  a binding lesson, a pinned mirror): take that path.
- anything answerable from the contract, the approved plan, the constitution or
  an accepted decision record. Quote the source in the notes.

It ESCALATES to the human only for a decision nobody has made yet: two accepted
decisions that genuinely conflict, a requirement that cannot be met without
changing what the feature DOES, or a scope extension that changes the task
rather than completing it. When escalating, state the options and the
recommendation — never relay the raw signal.

A stop costs the human a context switch and costs the run its momentum, so the
burden is on ESCALATING, never on deciding.
Signals are schema-validated (`factory/schemas/signal.json`, attested
`generated_by`), surfaced by `forge next` and the session-start hook, and
OPEN SIGNALS BLOCK `pr_ready` — an unanswered contradiction cannot ship.
The channel records story and task identity in the append-only signal ledger;
shipping does not erase that history.

## Determinism Contract

The rule that decides deterministic vs non-deterministic, once, so nobody
re-derives it per task:

- **Gates, state transitions, and evidence recording are deterministic** —
  scripts under `factory/scripts/`, never skills, never judgment calls.
- **Content generation (plans, code, tests, reviews, harvests) runs on the
  phase's PINNED skills** — `harness.yaml` is the allowlist, not a suggestion.
  Adopting a new tool is a PR to `harness.yaml` + the artifact's schema (then
  `forge upgrade` propagates it), never a local dev choice.
- **The only door into `.factory/` is a recorder** (`record_*_from_json.py`,
  `forge roadmap import`) that validates the payload against its
  `factory/schemas/<artifact>.json` — required fields, types, and a
  `generated_by` value inside the pinned allowlist. Nonconforming payloads
  and unpinned generators are refused outright; there is no override flag.
- **Mandatory phase skills are attested, not assumed.** Each schema's
  `required_skills` names the skills a feature type demands (e.g.
  `user_facing` → `emil-design-eng` + `frontend-design` on the testing
  artifact, `review-animations` on review artifacts); the recorder refuses
  the artifact unless `skills_used` attests them. Advisory skills are listed
  in `skills_used` when used. Same trust model as `generated_by`.
- **Prompts are the interface, recorder commands are the contract.** Devs
  speak intents ("start a task for invoices", "is this PR ready?"); agents
  run the mapped deterministic command. Anything an agent cannot route lands
  on `./forge next`.

Attestation trust model: `generated_by` is declared by the recording agent —
falsifiable, but only deliberately, and it leaves an audit trail (same model
as `plan assume` and decision records).

## Gating Model

Gates are deterministic and run at phase transitions (`update_run.py`,
`record_*` scripts, `pr_ready.py`) and in `pre_tool_use.py` — never on prompt
keywords or turn ends. Under decision 0013, the planning lock is **always
armed**: product writes, including heuristic Bash writes, are refused without
one of three legitimate exits: an approved plan, a bounded ledgered quickfix
window (`./forge quickfix start "<reason>"`), or a bounded ledgered lite window
(`./forge mode lite`). Planning surfaces (`plans/`, `docs/`, `.factory/`,
`factory/`, and `prototype/`) and read-only exploration stay open. Everything
downstream remains enforced at the artifact gates.

Decision 0032 adds a deterministic per-task grill to Full-mode execution. For
each pending leaf the prescribed order is author the contract → re-record the
decomposition → pass the digest-bound `task` grill → `forge stage start`
→ `forge delegate`. `stage start` establishes the measured work boundary and
`forge delegate` validates it, refusing a missing, non-passing, or stale
`.factory/grills/tasks/<id>.json`. In native Codex the coordinator then spawns
the matching host role from the prepared brief; in Claude the command launches
the protected plugin companion.

The PR boundary has one client-vendored CI contract:
`.github/workflows/roadmap-gate.yml`. On pull requests it requires every
completed work record to be declared — every `done` roadmap story (a done-flip
or newly-added story with added history) and every added work-window done
record — so a single review-driven effort that spans more than one window stays
fully traceable. On pushes to the repository default branch it runs the full
project audit, keeping audit gaps visible. The harness keeps its own internal
implementations for declaration, PR-link recording, and board completeness;
those workflows remain harness-internal rather than part of the vendored
contract. Stories explicitly marked `predates_outcome_contract` still need
history, but are exempt from the newer outcome and link requirements.

## Task Graph Rules
- The planner owns decomposition.
- Decomposition is capability-driven. Its first recording is the ordered task
  LIST: stable ids, titles, objectives, acceptance intent, and dependencies.
  The task list stays in the repo; only stories are mirrored to a tracker.
- Execution-contract detail is authored just in time for the next leaf task,
  against the actual output of its completed dependencies: write scope, exact
  acceptance criteria, verify commands, required tests, and reviewer focus.
  Re-record the decomposition before grilling that contract. Do not guess
  later-task detail during the initial decomposition (decision 0032).
- Decompose to the FEWEST tasks that each still fit ONE bounded session. This
  is a minimisation, not a balance: start from the minimum — one backend task
  and, if there is UI, one frontend task — and add a task only when something
  FORCES it. Backend and frontend never share a task (disjoint write scopes,
  different reviewer focus, only the frontend is `user_facing`); that split is
  the only free one.
- Every task beyond that minimum must NAME what forces it: the work does not
  fit one bounded session end to end (implement, verify, three-lens review, fix
  the findings), or its diff would outgrow what a reviewer holds at once. "It is
  a clean seam" is not a reason — seams are always available, which is why the
  burden is on SPLITTING and never on merging. Each extra task costs a full
  plan, grill, approval, review and PR, and that cost is paid by a human.
- The floor is real and the grill enforces it: a task that cannot be done in one
  session is refused however convenient the count. Under-splitting fails worse
  than over-splitting — an oversized diff chunks the reviewer, the contract
  verdicts are never emitted, and every contract records `partial`.

## Project Roadmap

`plans/roadmap.json` is the durable, ordered backlog — the role handoff
artifact (see `docs/ROLES.md`). Its epics and stories are derived from
confirmed capability specs before sign-off, never hand-authored. Every story
links its source spec. The roadmap survives every task cycle. Story-scoped
decomposition remains at `.factory/stories/<key>/decomposition.json`, while
the active-story pointer is worktree-local. Items carry `story`,
`acceptance_criteria`, `epic`, `spec`,
`skill` (frontend|backend|fullstack), and `assignee` (set by
`forge roadmap assign`, validated against the optional `plans/team.json`
roster, preserved across re-imports). Item lifecycle: `pending` → `active`
(set by intake) → `done` (set by story closeout, with a link to
`.factory/stories/<key>/`). `forge next` suggests the next pending item
and flags unassigned ones to the EM. Scope changes are PR edits to the
file — future planning refines the roadmap, it does not silently regenerate
it; the per-task plan must satisfy the item's `acceptance_criteria`.
In vendored clients, `.github/workflows/roadmap-gate.yml` arms only when
`constitution/VENDORED_FROM` exists and this roadmap has at least one epic;
an absent or valid epic-less roadmap leaves its gates green, while malformed
roadmap JSON fails the arming step loudly.

## Concurrency — one worktree and PR per task

Hooks use session cwd: task approval and edits need a task worktree session.
Coordinate from the primary checkout; reach other worktrees by absolute path.
Never `cd` the session shell outside a checkout; if stranded, resume there.

Each leaf task owns an isolated worktree, branch, proof set, and PR. A task
starts from refreshed trunk only after its dependency markers are present;
dependency-ready tasks may advance together when their measured scopes are
disjoint. Story evidence remains under `.factory/stories/<key>/` and ships in
place, so closeout creates no archive-move conflict.

Dependency-ready stories may also advance concurrently. `depends_on` edges on
roadmap items are the deterministic separation signal, and `./forge roadmap
parallel` prints that ready story frontier. Each worktree uses a git-local
active pointer while reading the same story-scoped contracts. `./forge roadmap
heal` resolves concurrent roadmap status changes with its done-wins union.

**Tasks inside one story may run in parallel when the plan allows it.** The
order is the task dependency graph (`dependencies` in the decomposition; a task
without an explicit list follows its predecessor), not the list. `forge task
start <id>` opens a task's worktree once every dependency's marker is on the
trunk, and `forge stage start <id>` opens its stage once the dependencies are
done AND its write scope (area prefixes, amendments, the test files it must
create) is disjoint from every stage active in any worktree of the story; an
overlap is refused naming the sibling and the overlap, so the plan splits the
areas or the tasks serialise — never a mid-run question to the human. Each
task worktree has its own delegation lock and its own stage tracker, and it
commits only its own stage record (`.factory/stories/<key>/stages/<task>.json`,
one record per task, decision 0022), so two task PRs never rewrite one shared
file. `forge next` lists every task that can move (the frontier first, then
"also ready in PARALLEL" with the exact command each, then the active stages
per worktree); a task waiting to merge is reported per task. Merge order is the
dependency order: a task cannot `pr-ready` before its dependencies' markers are
on the trunk, and siblings merge only through the trunk (merge the trunk into a
sibling, re-verify, re-review; the human sees only PRs). A worker's
`scope-change` signal that names a path inside a sibling's active scope is
refused with the sibling named: the coordinator re-plans instead of
arbitrating. The per-task brief carries the story's rulings and the sealed
contracts of the tasks it builds on, so a parallel worker never asks what a
sibling settled.

## Stage Loop — defects never enter history

Recording the initial task list also creates `.factory/stages.json` — the
mutable execution twin of the re-recordable decomposition (decision 0007),
one stage per leaf task in execution order. Decision 0032 makes the pre-work
sequence a JIT contract loop for every pending task:

1. enter plan mode (decision 0029; `factory/prompts/planner.md`) and author the
   next task's full contract against the approved plan and the real repository
   state left by completed dependencies
2. re-record the decomposition with that contract, then save the plan-mode
   result at `.factory/stories/<KEY>/task-plans/<id>.md`
3. run `factory/prompts/griller.md` with `--gate task` against that saved
   revision and resolve its findings. Native Codex prepares the griller
   descriptor, dispatches the full descriptor through `spawn_agent`, and
   records the exact returned JSON with
   `python3 factory/scripts/record_grill_from_json.py --gate task --task <id>
   --input <grill-json> --cold-result <path> --preparation-id <id>`; Claude
   keeps its command-managed cold-reader path
4. record the human task-plan approval against the same saved revision;
   changed approval-bound content follows the existing amendment route
5. `forge stage start <id>` (dependency and scope eligibility are derived;
   task-level `--parallel` is refused)
6. `forge delegate <id>` composes and validates the task brief. In native
   Codex it records a preparation row bound to task, worktree, stage, brief
   digest and effective or narrowed scope, prints dispatch information, and
   the coordinator spawns the matching
   configured role without model/reasoning overrides; that role's configured
   defaults apply. It never invokes `codex exec`. Raw/direct/nested
   `codex exec` and direct plugin shell launch remain off-contract and
   hook-denied for general or manual delegation in both runtimes. This ban does
   not constrain the authenticated Forge-managed autoreview black box, which
   may invoke Codex or agents internally. In Claude
   it launches the protected plugin companion. The command refuses a missing,
   failed, or stale task grill
7. the orchestrator inspects the diff and rejects overbuilt code
8. that stage's assumption rows are validated (`forge assumptions list --open`)
9. smallest relevant checks run
10. record the implementer's focused automated-test evidence, including every
    assigned acceptance result and remaining risk, then commit the completed
    product changes. Check all declared selectors and prerequisites together;
    do not run a standalone task-wide verifier before the next step.
11. `forge task close <id>` — one resumable command from a built task to its
    open PR. It requires a clean committed product tree and no open signal,
    window or assumption; derives the product delta (`delta_id`, the hash of
    `base..HEAD` on product paths); runs the declared verify commands and
    required tests; and runs the ONE three-lens review only when no review
    stamp already covers that exact delta. The review runs INSIDE the reviewed
    worktree, read-only (0076): the diff is the subject, and a verdict or
    finding about code the diff does not show -- a callee, a file a contract
    names, the other places a contract covers -- is read there and cited by
    line, never guessed; "cannot verify from the diff" is not a verdict. One Codex helper call publishes one
    immutable raw-plus-three-lens generation, then selects its task-scoped
    pointer last. Before closing the stage, `close` requires complete task-owned
    automated proof and conditional functional proof. For a `user_facing: true`
   task, close stops until functional proof is recorded; record it, then rerun
   `./forge task close <id>` so the unchanged selected review is reused and the
   stage is sealed.

    A run with no blocking (P0/P1) finding stamps the stage; non-blocking
    findings are recorded follow-ups. The coordinator sends all blocking
    findings from the joined round back to Codex in one fix batch (`forge
    delegate <id>`), commits the fix, and reruns `close`; it never asks the
    human who should fix them. Before a write delegation, `forge next`,
    `delegate`, and `task close` all enforce triage of the selected generation's
    actionable P0/P1 defect findings. Synthetic `plan-contract-partial` and
    `plan-contract-missing` rows remain acceptance blockers to implement and
    re-review, but are not host defect triage.
    The coordinator never relays a finding unread: it TRIAGES every actionable
    one first -- opens the cited line and the code it calls, and judges it against
    the mechanism's stated purpose using a file:line it read. An outside-purpose
    finding (e.g. an adversarial shape against a guard documented as a guardrail,
    not containment) is recorded `--not-a-defect` with that reason. For a real
    finding, it searches the repo for every other place the same contract applies.
    Before briefing a second fix round on the same guard, the coordinator first
    asks whether one simpler rule removes the whole class. It records the triage
    (`forge review <id> --triage "<text>" --lens <l> --real
    --evidence <file:line> --instance <file:line> ... [--keep "<what must not
    change>"] --by <agent>`, or `--not-a-defect --evidence <file:line> --reason
    ...`). The fix brief carries the triage beside each finding, and `forge
    delegate` refuses a write launch while any actionable selected-generation
    finding is untriaged. Read-only and print-only previews grant no write
    authority. A finding relayed unread is how
    one class of defect costs one round per file (WF-1 T5: six reviews, eight
    fix rounds; decision 0075). A finding that contradicts an accepted decision,
    a plan section or a sealed contract is not a defect: `forge review <id>
    --reject "<text>" --lens <l> --reason ... --cite
    <decision|contract|section> --by <agent>` records the rejection and the
    settled contract. On the Claude route, a fix that cannot be verified inside
    the plugin companion sandbox uses the bounded degraded route and records the
    host exception. Native subagents use the host environment directly.

    With clean proof and review, `close` measures the task, marks the stage done,
    writes the task marker, pushes, and opens the PR. It stops at the first
    failed step and names the next action; a retry repeats only what the new
    delta invalidated. A done stage whose delta moved reopens itself inside
    `close` with its base, contract and approval intact. Write-scope strays, a
    review-budget overrun and a required-test id that matched no JUnit case are
    measured and recorded, not refused. A delta above twice the declared line
    budget still refuses. Native closeout requires the current preparation row,
    including any narrowed scope, but no launch-process proof. On
    the Claude route, a closed degraded window with at most five in-scope files
    may satisfy the companion-launch requirement when the plugin is unavailable.

   What each closeout record binds to — and so what can stale it:
   the review stamp binds to the product `delta_id` and the substantive
   reviewed meaning. Canonicalized bookkeeping changes, including the
   independently recorded functional continuation, do not stale that meaning;
   a contract, acceptance, security, migration, evidence, review-instruction,
   or product change does. The prepared delegation binds
   the brief and effective scope. Claude additionally records its protected
   companion launch, while native delivery deliberately records no process
   attribution; after stage start the task grill binds to
   objective, acceptance criteria, plan contracts, `user_facing` and the plan
   (`write_scope`, `required_tests` and `verify_commands` are MEASUREMENT
   fields — `stage done` enforces them by measuring and running them, so
   changing them mid-stage re-grills nothing); the plan digest excludes the
   harness-rendered `<!-- forge:contract -->` block, which every task plan
   carries as the rendered, never hand-copied, copy of its contract.
   Scope is widened with `forge stage amend-scope`, and the measure, the
   delegate brief, the grill brief and the review brief all read the same
   effective scope. The explicit verbs remain: `forge review <id>`,
   `forge stage done <id>`, `forge task pr-ready <id>`, and `forge task
   reopen <id> --review-fix`.

`forge next` derives this frontier from the same readiness gate and reports
the next action from contract authoring through implementation, task proof,
review, stage closure and `await-merge`. **Per-task PRs are the standard:** after
a task is built, `forge task close <id>` reviews, closes and ships it as its OWN
PR (marker, push, PR; poll CI to green) — let it merge to the trunk before the
next task starts, never batching a whole story into one PR.
`await-merge` surfaces this in BOTH run-pointer modes (task-level and a stage
running in the story worktree), so the frontier never skips past a done-but-
unshipped task.

When a task was merged to the trunk OUTSIDE this flow — a whole-story PR, or a
direct PR that skipped `pr-ready` — no marker is on the trunk and the frontier
stays stuck at `await-merge` for a task that actually shipped. `forge task
reconcile <id>` is the sanctioned repair: it confirms the task's work is on the
trunk, writes the completion marker, flips the stage done, and records a
`stage-reconciled` event — opening NO new PR (the work already merged). Commit
its marker to the trunk (via the reconcile PR) and the frontier advances. This
is a reconcile, not a shortcut: it refuses when the work is not genuinely on the
trunk, so it can never fabricate a ship.

There is ONE review per task. `./forge review <task-id>` produces
`.factory/stories/<KEY>/tasks/<id>/reviews/*` and the stage's review stamp in the same run (decision 0001 D6:
the recorded review is the only review gate); no separate stage-local review
loop exists, and `record_review_from_json.py --aspect stage-local` remains
only as a manual fallback. `pr_ready.py` refuses while any stage is not done
or its stamp is stale; `forge next` shows stage progress; task and story proof
remain at their scoped `.factory/stories/<issue>/` paths after ship.

The loop is AUTONOMOUS between gates (conduct §7): a clean review IS
the permission to close the stage and ship the task — the orchestrator never
pauses to ask "proceed?" after a review or between stages, and the same
holds across phase transitions (verify → review → functional → pr_ready).
It stops only for an open signal, a gate refusal it cannot resolve within
the approved plan, a human-only act, or scope the plan does not cover.

### Who authors what — no ambiguity once implementation starts

After task-plan sign-off, the division of labour is FIXED, so a task never
stalls on "should I do this or hand it to Codex?":

- **Every product change is assigned to a Codex worker.** In native Codex,
  `forge delegate` prepares the canonical dispatch and Main sends it to the
  matching role-based host subagent. In Claude, `forge delegate` launches the
  protected plugin companion. Every implementation or review-fix batch follows
  the same task contract, then Main re-inspects and re-reviews it. Native mode
  follows this ownership rule without pretending Forge can mechanically
  distinguish Main from a host subagent process.
- **The coordinator's hands do only orchestration:** author task contracts,
  compose briefs, delegate, inspect the bounded diff and focused checks, then
  run `forge task close` — which runs the proof ONCE, records it, reviews and
  ships (0079); the coordinator does not re-run the suite or `verify.py` by
  hand before it — and, when the story reaches a PR, review that PR.
- **Commit is not a human gate.** After inspecting the bounded diff and green
  focused checks, the coordinator commits the product changes. Deterministic
  verify, task test recording and `forge review <id>` follow that commit;
  clean proof permits stage closure and publication (conduct §7 autonomy).
  Continue without asking for another permission to commit.
- **The Claude exception — a logged host-exception.** When a required product
  change is PROVABLY impossible in the plugin companion's environment (no Docker, or
  a folder its sandbox account cannot read, that the change or its verification
  needs — the network and the local database are reachable since decision 0068),
  the coordinator may make the MINIMAL change on the host and MUST record why
  with `forge signal raise ... --kind host-exception` (resolve it once done).
  This is bounded and always ledgered — never the default, never silent.

The point: from sign-off to green tests the coordinator has full, deterministic
visibility of what it does versus what it delegates, and only genuine
human-only acts (decisions, sign-off) or unresolvable gate refusals pause it.

## Task Planning
Story and task plans use the coordinator's native Plan Mode and follow
`factory/prompts/planner.md`. They are briefs for the person approving the work:
plain English first, with a short technical section last. A story plan uses
`What and why`, `What changes for you`, `Done when`, `Risks`, and optional
`What I need from you`, then a divider, `Technical approach`, a concise
`Task decomposition` table, and `Verify plan`. Keep the plain-English portion
to about 25 lines. A task plan uses `What and why`, `Workflow`, `Manual
verification`, `Risks`, then a divider and `Technical notes`. Neither plan
body contains frontmatter, IDs or ID lists, status or date lines, SHAs,
digests, file paths, or scope lists. Mention a decision by title in the
technical section only when it changes the design.

Each plan gets one independent wide cold read at Sol/high. The griller sweeps
every feature the artifact touches and shipped features next to them against
their contracts, checking current behavior, tests, and docs for dead ends,
bypassed or unpassable gates, impractical advice, upgrade data loss, and stale
docs. Every finding cites an exact `file:line`. The coordinator resolves
repository-answerable findings; only genuine human choices go to the human,
as option questions with a recommended option and its reason. The cold proof
binds the exact input it read; `finding_dispositions` maps every finding, and
`amendments` explains every change between that input and the final artifact.
Commit spec, decision, and roadmap changes before launching the grill because
its staleness check compares commit order.

Before saving, the planner reviews every active decision. `forge plan save`
records that attestation itself in `.factory/stories/<story>/plan-meta.json`,
without adding decision IDs to the brief. Plan status, dates, and reviewed decisions live in
`.factory/stories/<story>/plan-meta.json`, written only by `forge plan save`.
The saved plan body is shown exactly as saved in native approval, with no Forge
bookkeeping inserted. Claude `ExitPlanMode` binds its exact `tool_input.plan`;
Codex retains the synchronous question id `approve_plan_<digest>` and asks
`Approve this plan?`; the digest travels only in the question id, with the
`Approve plan / Request changes / Stop` choices as recorder details. The human
approval binds the digest of the body the person read. There is no requirements grill, compulsory human round,
`frontier_empty` question, manual `plan approve` / `task approve` command,
board approval, or second unchanged save in the normal flow.

If an already approved plan changes before stage start, record the amendment
bridge against the existing cold proof and return directly to native approval
of the exact amended body; do not launch another cold read solely for changed
bytes. Claude delegates read-heavy exploration through
`/codex:rescue --model gpt-6-sol --effort medium`, read-only, and uses Sol/high
for validation or architecture; it never runs raw `codex exec`. Native Codex
uses the configured `planner-high` role through host `spawn_agent` without an
override; that role's Sol/high defaults apply. Decomposition uses Sol/high,
difficult diagnosis uses Sol/high before its Luna/max fix, and the independent
grill uses Sol/high. Every new decision record is made before decomposition
is recorded. `--story <key>` binds the saved plan to the roadmap; open
contradiction signals or incomplete decision coverage refuse the save.

During implementation, record any call the plan does not cover with
`forge.py plan assume "<one sentence>"` and guide it through
`forge.py assumptions resolve <id> --status confirmed|fix-needed|promoted
--notes "..."`. Assumptions stay in the structured ledger, not in the approved
plan body. `pr_ready.py` refuses to ship a task with unguided (`open` or
`fix-needed`) rows; the session-start hook and `forge next` surface the open
count. Promoted assumptions become decision records. An assumption that would
change scope or acceptance criteria is a report back to the dev, not an
assumption.

## Artifacts
Required run artifacts:
- `.factory/stories/<key>/run.json`
- `plans/active/<issue>-<slug>.md` (the approved plan)
- `.factory/stories/<key>/decomposition.json`
- `.factory/stories/<key>/tasks/<id>/verify.json`
- `.factory/stories/<key>/tasks/<id>/tests.json`
- `.factory/stories/<key>/tasks/<id>/reviews/selected.json`
- `.factory/stories/<key>/tasks/<id>/reviews/generations/<sha256>.json`

Every evidence artifact is stamped with the commit it was recorded at.
`pr_ready.py` refuses unstamped artifacts, artifacts spanning different
commits, and evidence whose proof-type inputs or substantive reviewed meaning
changed. Canonicalized bookkeeping and timestamps preserve immutable original
provenance when those inputs remain unchanged.

On scoped story closeout, `pr_ready.py` writes `shipped.json` in place and
keeps the story plan and evidence at their recorded paths. Legacy unscoped
stories still archive until `forge upgrade` migrates them.

## Execution Order
1. ensure architecture and decision docs are present in-repo
2. complete discovery; prototype freely and save specs as capabilities emerge
3. confirm every spec, then derive the roadmap from the specs
4. record client sign-off
5. plan one roadmap story and record its ordered task list
6. for each leaf task: author its complete contract, re-record the
   decomposition, run one independent cold task grill (native: run `./forge
   grill run --gate task --task <id>`, include the complete descriptor and its
   context metadata in the actual `spawn_agent` message, then record the exact
   result with `python3 factory/scripts/record_grill_from_json.py --gate task
   --task <id> --input <grill-json> --cold-result <path>
   --preparation-id <id>`), record every finding's
   disposition and amendment, obtain native approval of the final task-plan
   digest, start the stage, then delegate it through the canonical host-native
   descriptor; native Codex
   spawns the matching host role and Claude launches the plugin companion.
   `delegate --scope` may repeat to select a proper subset of the approved
   effective scope, while omission uses the full scope
7. after implementation, run `./forge task close <task-id>` as the integrated
   normal operation: it runs the task's tests and deterministic verify, or
   reuses passing receipts only when their complete identities are unchanged;
   unknown command shapes run again conservatively. It runs or safely reuses
   the one complete review and finishes the stage only when that proof is
   clean and current
8. if close reports blocking review findings, delegate the fixes and rerun the
   same integrated close operation; selected proof reuses only while its
   stamp-token delta, complete proof identities, and reviewed-meaning identity
   are unchanged
9. run the Sol/high `functional-checker` when the task has `user_facing: true`
10. after supported functional recording, rerun `./forge task close <task-id>` to
    finish, seal, and open the task PR
11. record the shipped outcome with `./forge outcome set "<what changed>"`, then
    run `python3 factory/scripts/pr_ready.py` for story readiness

## PR Ready Contract
A branch is PR-ready only when:
- plan status is `approved`
- decomposition status is `recorded`
- deterministic verification passes
- automated and functional test artifacts exist with no blockers
- the task's selected review generation contains all three lenses with score
  >= 8 and no blockers
- acceptance criteria have direct evidence
