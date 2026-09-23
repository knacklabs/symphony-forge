# Forge — harness operations (canonical body, both runtimes)

Canon lives in `AGENTS.md`, `WORKFLOW.md`, and `harness.yaml`. This skill only
routes to it.

**The contract: devs speak intents; you run the mapped command and report its
output.** A dev should never need to type a `python3 factory/scripts/...`
command themselves. Prompts are the interface, recorder commands are the
contract — every artifact you record must match its `factory/schemas/` file,
including `generated_by`. Human-only actions (`decision accept`) need an
explicit human statement — but the human need not type the command: a clear
in-chat confirmation authorizes running it with `--by "<their name>"`.

**Between gates the loop is autonomous (conduct §7).** A clean local review
or a passing gate IS the permission to continue — never stop to ask
"proceed?" after a review, between stages, or across phase transitions.
Report progress and keep driving; stop only for an open signal, a gate
refusal you cannot resolve within the approved plan, a human-only act, or
scope the plan does not cover.

The user and host select the main coordinator model and reasoning. Native
dispatch passes no model or reasoning override; the selected configured role's
defaults apply. Decision 0083 routes routine implementation, automated tests,
diagnosed or review fixes, documentation edits, and mechanical refactors to
Luna/max; read-heavy exploration and dependency tracing to Sol/medium; and
planning, decomposition, difficult diagnosis, independent grills, and final
functional checks to Sol/high. A difficult diagnosis returns its resolved edit
to Luna/max. Formal code review stays exclusively with the unchanged,
externally maintained Autoreview skill, which may choose its own internal
Codex or agent calls. No Forge or native lane selects Luna/low. Native
transport remains process-free: Forge prepares the descriptor and the host
owns subagent lifecycle without process or authorship-attribution proof.

`./forge <cmd>` (from repo root) is shorthand for
`python3 factory/scripts/forge.py <cmd>` — either form works everywhere below.

## Codex native: use host subagents

Under accepted Decisions 0053, 0059 and 0064, the user-facing Codex session is
Main. Main owns intent, the approved graph, scheduling, human questions and the
consolidated result. Current-task work runs through the host's native
role-based `spawn_agent` subagents. Claude keeps its protected
coordinator-and-`codex-plugin-cc` companion route.

- Run `./forge delegate <task-id>` first. In native Codex it validates the
  current task, grill, stage and requested scope, writes the canonical brief,
  records a preparation row (including narrowed scope), and prints dispatch
  information. It does not run `codex exec` or launch a
  child process. Raw/direct/nested `codex exec` and direct plugin shell launch
  are off-contract and hook-denied for general or manual delegation in both
  runtimes. Forge-managed autoreview is an authenticated external black box and
  may invoke Codex or agents internally; this ban does not constrain it.
  Spawn the matching configured role (`worker`, `planner-high`,
  `docs-decomposer`, `functional-checker`, or another defined specialist) with
  that brief and omit model/reasoning overrides so the selected role's
  configured defaults apply.
- Give the subagent bounded ownership: story/task IDs, objective, approved
  contract and scope, dependencies, checks, settled decisions and completion
  criteria. Tell it that other agents share the checkout and it must preserve
  their work. Reuse or follow up with the responsible subagent for corrections
  when the host supports that operation.
- Forge does not register or fence native subagent processes or sessions. It
  adds no PID, ancestry, launch-token, foreground/background, status, cancel,
  resume, or recovery restrictions to host-native collaboration. Use those host
  features normally. Consequently native delivery has no mechanical
  process-attribution claim; correctness is established by the approved task
  scope, inspected diff, tests, deterministic verify, independent review and PR
  gates.
- Run dependency-ready work in parallel only where the approved graph and
  worktree/scope rules permit it. A subagent's completion message is not proof:
  Main inspects the diff and recorded artifacts before advancing the task.
- Keep coordinating until each dispatched subtask completes or has a concrete
  blocker. Resolve matters already covered by the contract without asking the
  user again; escalate only missing authority or a material new choice.

## Choose the smallest complete route

Choose from the existing routes before creating workflow state. State the
route and reason in one sentence; developers provide answers and approvals,
not commands or a mode-selection checklist. Reuse applicable authorization
already given in the conversation; never invent an approval or its actor.

| Request and current state | Route |
|---|---|
| Explanation, code lookup, status, or diagnosis without edits | Answer or inspect directly. Use a status command only when its result is needed; do not create an intake, plan, window, or review. |
| Correction within an active approved task | Resume that task and its eligible worker. Keep its accepted scope and approvals; collect all known blockers into one focused fix batch. Never open Lite beside an active stage. |
| Small, understood, supervised fix with no active stage | Prefer existing reviewed Lite when the work fits its five-product-file bound and applicable human authorization. Record the real authorizing actor and reason with `forge mode lite`; focused checks, one independent review pass, `forge mode done`, then the repository's PR/CI flow. A small diff alone does not establish low risk. |
| New capability, unclear acceptance, changed contract, or consequential security/data/migration boundary | Full workflow: resolve the uncertainty, approve the exact story/task, then execute autonomously to PR. |
| Explicit trace-only quickfix or a qualifying companion outage | Use only that existing bounded exception. Quickfix records a write window; it does not establish reviewed completion. Degraded mode retains its outage conditions. |

Lite's recorded authorization, scope bound, review and CI still apply. If the
chosen route is no longer sufficient, preserve the work and use the existing
amendment or Full path; do not silently expand its authority. Do not prompt for
an authorization already provided, or attribute an agent's choice as a native
human approval event.

For an approved Full task, the implementer owns focused checks and a truthful
automated report. Commit the completed product changes, then let ONE
`forge task close <id>` own final task-wide verification, required-test proof,
and independent review. Complete any required functional check and resume
that same close by rerunning `./forge task close <id>` after recording
user-facing functional proof; the unchanged selected review is reused and the
stage is sealed. A passing proof is reused only when its complete command,
environment, tool, distribution, generated-input, and product identities
remain unchanged. Unknown command shapes run again conservatively. Never run standalone full
verification before close or reconstruct close as separate review/stage/PR
commands. Check the complete declared selectors and prerequisites together
before an expensive run; keep build-dependent checks after their prerequisites.

Only P2/P3 findings become recorded follow-ups with a reason and revisit
trigger; they do not start another cleanup/review cycle. When the latest
published head satisfies required proof and CI and merge is authorized, merge
and continue. P0/P1 findings and failed required checks must be resolved first.
Before any review-fix write delegation, triage every actionable P0/P1 defect
finding in the selected generation with `./forge review <id> --triage ...`;
`forge next`, `forge delegate`, and `forge task close` enforce this frontier.
Synthetic partial/missing plan-contract blockers remain acceptance blockers to
implement and re-review, but do not require host defect triage.

## For workflow execution, start here

```bash
./forge next
```

That is the deterministic phase engine — it reads run state, the context
ledger, plans, the roadmap, and artifacts, and prints where the project is and
the exact next actions. Never guess the phase yourself; run it, then execute
or route:

| `next` says | Do |
|---|---|
| discovery/prototype | gstack `/office-hours` for the discovery conversation; prototype freely |
| roadmap missing | confirm captured specs, run the project-level decomposition (`factory/prompts/decomposer.md`), then `./forge roadmap derive --input <json>` |
| planning | Plan per `factory/prompts/planner.md`. Native Codex spawns the configured Sol/high `planner-high` role without model/reasoning overrides; Claude delegates read-heavy exploration via the Sol/medium `explorer` lane and validation/architecture with Sol/high, read-only — never Claude Code itself, never raw `codex exec` |
| decomposing | run docs-decomposer per task, record with `record_decomposition_from_json.py` (schema incl. `user_facing`) |
| implementing | Follow the one frontier action printed by `./forge next`: enter plan mode and author/re-record the JIT contract; run the task griller; `forge stage start`; or `forge delegate`. In native Codex, send the complete prepared descriptor and context metadata in the actual `spawn_agent` message to the named role, without model/reasoning overrides. The implementer writes and records the tests; user-facing tasks MUST load + attest emil-design-eng + frontend-design in `skills_used` (recorder-enforced; harness.yaml `required_skills`) |
| verifying | For an active task, use its existing `./forge task close <id>` owner; do not start a competing or standalone full verifier. |
| reviewing | Continue the task-close owner and its independent review. Batch blocking fixes, run focused checks, commit, then resume close under `docs/QUALITY.md` bounded recovery. |
| functional-check | only shown when the task is user-facing; run the Sol/high `functional-checker`, record its proof, then rerun `./forge task close <id>` so the unchanged selected review is reused and the stage is sealed |
| harvest pending | follow `factory/prompts/harvester.md` |
| anything with a command | run the command verbatim |

## Route by intent

| Dev says | Do |
|---|---|
| set up my machine | `./forge doctor` (`--fix` installs the toolchain; logins stay manual) |
| create a new project / build a new app | prefer the `knacklabs-new-project` skill; without it: `./forge init --name <project> --target <dir>`, then IN `<dir>`: commit and push to its OWN origin (`gh repo create <org>/<repo> --private --source . --push`), `direnv allow`, and open future sessions there. Init writes `.factory/record-origin.json` once so history has an honest starting boundary. The app is a fresh unrelated repo — NEVER fork the harness, NEVER `gh repo create --template`, never build the app inside this clone |
| migrate an existing repo / make this repo symphony-forge ready | `knacklabs-migrate-project` skill — core: `./forge adopt --target <repo>` from the harness clone (clean tree; old AGENTS/CLAUDE preserved to docs/context/; repo keeps its own origin — never fork/merge the harness into it). Adopt creates the same record-origin boundary if absent and never rewrites it. |
| update / upgrade an existing project to the latest harness | prefer the `knacklabs-upgrade-project` skill — it verifies and updates the setup-pinned harness, audits a clean committed client, upgrades machinery, repairs tooling, backfills project contracts, guides pending-story re-authoring with `forge roadmap fill`, re-verifies, and hands off through `forge next` |
| sanitise / check the hygiene of this repo | use the `knacklabs-sanitise-project` skill — run `forge sanitise --check` for an on-demand report or plain `forge sanitise` for safe deterministic fixes, then use the named resolve commands for every reported item needing judgment |
| migrate my gstack history / gstack outputs are on my machine | `./forge gstack migrate` — union-merges ~/.gstack/projects/<slug>/ into the repo's .gstack/ (then commit). Going forward .envrc + `direnv allow` keeps gstack in-repo |
| what's left to build / show the roadmap | `./forge roadmap list` (`--pending` for what's next; grouped by epic, shows @assignee) |
| what can run in parallel / fan out the work | `./forge roadmap parallel` — the dependency-ready story frontier. Each leaf task owns a worktree and PR; dependency-ready tasks may advance together only when their measured scopes are disjoint |
| roadmap merge conflict / duplicate items after merging branches | `./forge roadmap heal` — deterministic union (done-wins); mid-merge it rebuilds from the merge stages, then `git add plans/roadmap.json` |
| grill the handover / stress-test before a gate | `factory/prompts/griller.md` — one question at a time vs the actual docs. For a native plan grill, run `./forge grill run --gate plan --file <plan-file>`, put the complete descriptor and context metadata in the actual `spawn_agent` message to `griller`, resolve findings, then record the exact JSON with `python3 factory/scripts/record_grill_from_json.py --gate plan --input <grill-json> --input-digest <plan-file> --cold-result <path> --preparation-id <id>`. For a native task grill, use `./forge grill run --gate task --task <id>` and `python3 factory/scripts/record_grill_from_json.py --gate task --task <id> --input <grill-json> --cold-result <path> --preparation-id <id>`. Claude keeps its command-managed cold reader. Required gates refuse without their fresh pass |
| grill me on this plan | run the one host-specific independent cold grill against the draft plan with `./forge grill run --gate plan --file <plan-file>`, complete its dispositions, and use `python3 factory/scripts/record_grill_from_json.py --gate plan --input <grill-json> --input-digest <plan-file>` for a command-managed result or `python3 factory/scripts/record_grill_from_json.py --gate plan --input <grill-json> --input-digest <plan-file> --cold-result <path> --preparation-id <id>` for the native result before `plan save` — mandatory before `plan save` |
| capture a capability spec | `./forge spec save <slug> --from <draft.md>`; confirmation requires a digest-bound spec grill, then `./forge spec confirm <slug>` |
| here's the derived project backlog | `./forge roadmap derive --input <json>` (pre-sign-off, every story links a confirmed spec) |
| add a story to the roadmap | `./forge roadmap add <KEY> "<title>" --story "As a <user>, I ... so that ..." --ac "<criterion>" --spec docs/specs/<slug>.md --epic <epic> --skill frontend\|backend\|fullstack [--depends-on <KEY>]` — story and at least one criterion are required |
| an ad-hoc ask arrives mid-project with no spec | same command with `--no-spec --reason "<why>"` — it lands in **Needs spec** as visible debt; `plan save` refuses to build it until `./forge roadmap link-spec <KEY> --spec docs/specs/<slug>.md`. Capture is not authorization (0014) |
| define the team / who's on this project | `./forge team set <handle> --role dev --skills frontend,backend` (optional roster; `./forge team list`) |
| assign a story / distribute work (EM) | `./forge roadmap assign <KEY> --to <dev>` — checked against the roster; match story skill to dev skills |
| who does what / role handoffs | `docs/ROLES.md` — forge next tags every step [PM]/[EM]/[dev] |
| start a task / new feature | `python3 factory/scripts/intake.py --issue <KEY> --title "<title>"` — then check `forge.py context list --pending` BEFORE planning |
| save and approve a plan | Run one independent cold grill against the draft and complete its disposition/amendment bridge; then `python3 factory/scripts/forge.py plan save --from <plan-file> --story <key>` once and show those exact final bytes in native Plan Mode. If an already approved plan is amended before stage start, record the bridge against that existing cold proof and return directly to exact native approval; do not launch a second cold grill solely for changed bytes. Successful Claude `ExitPlanMode` binds its exact plan input; Codex uses id `approve_plan_<digest>`, prompt `Approve exact plan digest <digest>?`, and an id-keyed `Approve plan` answer |
| show implementation progress / how far along are we / show the board | `./forge board` — see "Show, don't recite" below. `./forge plan list` is the text fallback |
| review the plan / let me read the plan | present the exact final plan through native Plan Mode; `./forge board` is a read-only status view and never an approval transport |
| I need a small fix without a plan | Apply the route table above. Prefer reviewed Lite for an eligible, authorized standalone fix: `./forge mode lite --by "<authorizing actor>" --reason "<why>"`; close with `./forge mode done` after focused checks and clean required review. Quickfix is the distinct trace-only exception, never a review shortcut. |
| why is my edit blocked | the planning lock is ALWAYS armed (decision 0013): product writes need an approved plan or an open quickfix. `.factory/` is never hand-written; recorded state comes from the record_* scripts |
| record the decomposition | `python3 factory/scripts/record_decomposition_from_json.py --input <json>`, then `update_run.py --phase implementing --decomposition-status recorded` |
| record a decision | `./forge decision new <slug>` — draft only; it is stamped with the active story so the board can show which decisions came out of this work |
| this decision also governs another story | `./forge decision link <slug> --story <KEY>` |
| this decision replaces an old one | `./forge decision new <slug> --supersedes <old-slug>` — never edit/delete the old record by hand |
| what decisions are in force | `./forge decision list --active` — the live corpus (superseded records are history) |
| compact the assumptions ledger | `./forge assumptions archive` — resolved rows from finished tasks move to the archive |
| is the repo getting heavy | `python3 factory/scripts/check_repo_budget.py` (CI runs it too) |
| human confirms a decision | acceptance is the HUMAN's call, not their keystroke: on an explicit in-chat confirmation ("accept <slug>", "approved"), run `./forge decision accept <slug> --by "<their name>"` for them; without that statement, relay and wait |
| made an assumption while implementing | `python3 factory/scripts/forge.py plan assume "<one sentence>"` — lands on the active plan AND as an open row in plans/assumptions.md |
| worker hit a contradiction / is confused / blocked / scope shifted | `./forge signal raise --kind <k> --by <agent> -m "..."` then PAUSE — the orchestrator monitors `.factory/signals.jsonl`, resolves, resumes |
| a worker signal is open (orchestrator) | `./forge signal list --open` → inspect the signal and its worker state → resolve the cause with `./forge signal resolve <id> --notes "<answer>"`. Resume only a live paused worker; otherwise reconcile its result before deciding whether new delegation is needed. Open signals block pr_ready |
| review / guide the assumptions (orchestrator) | `./forge assumptions list --open`, then `./forge assumptions resolve <id> --status confirmed\|fix-needed\|promoted --notes "..."` — pr_ready refuses unguided rows |
| work the next stage / where am I in the task | Run `./forge next` when the frontier is unknown. After implementation, focused tests and truthful implementer test recording: commit product changes → ONE `./forge task close <id>` → functional check if required and resume close → current-head CI and authorized merge. Close owns final verification, review, stage completion and PR preparation (WORKFLOW.md Stage Loop; `docs/QUALITY.md` bounded recovery). |
| delegate this task / hand it to Codex | `./forge delegate <task-id>` — validates the active task, worktree and effective scope, builds the brief, and records the native preparation row including any narrowed scope. Spawn the matching role-based host subagent from its dispatch information without model/reasoning overrides; Forge never calls `codex exec`. Under Claude, the command launches the protected `codex-plugin-cc` companion |
| is Codex stuck? / did it actually do anything | In native Codex use the host's normal subagent status and coordination tools; Forge adds no lifecycle feature locks. Under Claude, `./forge codex status` remains an advisory view of companion jobs and never a gate |
| it only did part of the job | `./forge stage done <id> --incomplete "<what is missing>"` — the stage stays active and the gap enters the timeline |
| are we fixing the same thing again | `./forge findings patterns` — a class at 3+ hits gets a refactor story + decision, never a fourth patch |
| what did we learn about these files | `./forge lesson relevant --files <paths>` — run BEFORE planning/implementing |
| that mistake keeps happening, remember it | `./forge lesson add --topic <slug> --lesson "..." --source <sha/review> --applies-to <globs> --severity low\|medium\|high --by <agent>` |
| this is out of scope for now | `./forge defer add "<item>" --why "..." --trigger "<condition that reopens it>"` — parked scope needs a trigger |
| worth remembering past a compaction (hypothesis, gotcha, in-flight detour) | `./forge note "<one line>"` → .factory/scratchpad.md working notes; the PreCompact hook snapshots deterministic facts above them and PRESERVES the notes. Durable knowledge goes to a lesson/assumption/decision/deferral instead |
| did any deferral come due | `./forge defer list --open` — resolve fired ones back onto the roadmap (`./forge defer resolve <id> --notes ...`) |
| record the test results | `python3 factory/scripts/record_test_from_json.py --kind automated\|functional --input <json>` |
| run verify / does it build | `python3 factory/scripts/verify.py` (never bypass with ad hoc commands) |
| record the review | `./forge review <task-id>` publishes the selected three-lens generation; `record_review_from_json.py --aspect ...` is Lite/diagnostic or one-time migration input only |
| client signed off | `python3 factory/scripts/record_signoff.py` |
| harvest context / process the dump | follow `factory/prompts/harvester.md`, then `forge.py context mark ...` |
| harness status | read `.factory/run.json`; `forge.py context list --pending`; `ls factory/skills/proposed/` |
| what happened / show project history | `./forge history` reads committed events; add `--story`, `--event`, `--since`, or `--until` to narrow them. Unattributed events remain visible, and the board reports `.factory/record-origin.json` as “record begins here; N commits precede it” when that marker exists. |
| record what the story delivered | `./forge outcome set "<what changed and what someone can now do>"` — one paragraph in a reader's language, required before PR-ready; it lands on the roadmap item and in the ship archive |
| is this PR ready | `python3 factory/scripts/pr_ready.py` (never bypass with ad hoc checks) — a bare run lists what is missing, including the outcome |
| what did we ship last month | open the board's **Ship log** (`./forge board`) — PR-ready date, story, outcome and the decisions it created, newest first |
| mine for skills / retro | follow `factory/prompts/skill-miner.md` |
| improve the animations / motion audit | run the `improve-animations` skill (read-only audit → prioritized plans); land its items via `./forge roadmap add` or a task intake — never apply fixes straight from the audit |
| update a client repo to the latest harness | use the `knacklabs-upgrade-project` skill; its deterministic core is `./forge upgrade --target <client-repo>` from the verified HARNESS clone, followed by client audit/backfill, guided pending-story fill, re-verification, and `forge next` |

## Show, don't recite

When a dev asks anything status-shaped — "what now", "how far along", "show me
progress", "review the plan", "what can we parallelise" — put it on screen
instead of narrating it:

```bash
./forge board            # serves http://127.0.0.1:8765/ and opens the browser
```

- **Reuse, never duplicate.** If the board is already serving this repo, give
  the URL rather than starting a second one; a busy port means it is running.
- Stories are cards on a swimlane board — epic lanes across the lifecycle
  columns — so progress is read from where a card sits, not from prose.
- The board opens on **Overview**: what the project is, what can start now,
  what each epic delivers, and where each story sits. Use
  `./forge board --repo <example>` for a full initialized example repo. The
  checked-in data-only contract sample is discoverable at
  `factory/board/example/`; production validators exercise it, while direct
  serving waits on the deferred board-page resolver change.
- **Deep-link to the story you are talking about**: `…:8765/#RAIL-3` opens that
  story's drawer with its gate rail, what blocks the next gate, and its
  artifacts (plan, spec, decomposition, evidence).
- Specs, decisions, the plans ledger and quickfix history sit behind the
  **Library** panel in the header — reference material, off the main surface.
- **After saving a plan**, the board may show its readiness, but native Plan
  Mode must display the exact final plan for approval.
- The board is READ-ONLY on purpose. It shows status; it never approves.
  Approval recording comes from the native host completion event.
- Still report the outcome in chat — the board supplements your answer, it
  does not replace it.

## Hard rules

- Start the session inside the worktree being worked. Hooks resolve the repo
  from the session's working directory; a session rooted elsewhere records no
  native approval and gates the wrong repository (WORKFLOW.md Runtime Modes).
- Implementation is delegated to Codex. Native Codex uses role-based host
  subagents without dispatch-time model/reasoning overrides; Claude uses its protected plugin
  companion. See `harness.yaml` for artifact producers; recorders refuse
  artifacts from unpinned generators.
- Review is the orchestrating session's unchanged, externally maintained
  Autoreview skill (0011), looped review → Luna/max Codex fixes findings →
  re-review until clean. Its authenticated internal Codex/agent use is allowed
  and follows its own policy; never review inline or nest reviewers.
- Never set a decision to `accepted`, never flip `client_signoff`, never
  activate a proposed skill without an explicit human confirmation — the
  human decides; a clear in-chat statement lets you run the recording
  command with their name.
- If `check_dual_runtime.py` fails, fix the violation it names before anything else.
