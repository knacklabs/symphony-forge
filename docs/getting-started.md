# Getting Started with Symphony Forge

Symphony Forge is a dual-runtime harness plus doc-driven factory for building
agent-ready software. Either Claude Code or native Codex coordinates the same
phase engine. Claude uses `codex-plugin-cc`; native Codex assigns bounded task
work to role-based host subagents. This page is the one blessed path from empty
directory to first feature PR.

The user and host choose the main coordinator model and reasoning. Native role
routing uses Luna/max for routine implementation, automated tests, diagnosed or
review fixes, documentation edits, and mechanical refactors; Sol/medium for
read-heavy exploration and dependency tracing; and Sol/high for planning,
decomposition, difficult diagnosis, independent grills, and final functional
checks. Formal code review remains exclusively the unchanged, externally
maintained Autoreview skill and may use its own internal Codex or agent calls.
No Forge or native lane selects Luna/low.

**You drive it with sentences, not commands.** Every step below leads with
what you SAY to Claude Code (or Codex); the command underneath is what the
agent runs for you — the deterministic contract, and your fallback in
degraded mode. The only commands a human ever types personally are the
one-time clone and `decision accept` (confirming decisions is deliberately
human-only).

Lost at any point, in any phase? Say **"what's next?"** — the agent runs
`./forge next` and walks you through the exact next actions.

## The gates at a glance

You never memorize these — the command you're about to run refuses and tells
you what's missing. But this is the shape of the whole system:

```text
prototype ▶ spec grills ▶ CONFIRMED SPECS ▶ derived roadmap ▶ sign-off grill
  ▶ SIGN-OFF ▶ roadmap+team ▶ story plan ▶ one cold grill + dispositions
  ▶ native approval of the exact final digest ▶ decompose (creates the task tracker)
  ▶ per leaf: JIT task plan ▶ one cold grill + dispositions ▶ native approval
  of the exact task digest ▶ prepare (`forge delegate`) ▶ native role subagent
  or Claude plugin companion implements
  ▶ commit ▶ task proof ▶ `forge task close` runs ONE combined three-lens
  task review ▶ delegate fixes and rerun close until clean ▶ functional
  proof (if user-facing) ▶ rerun close to reuse the selected review and seal
  the stage ▶ task PR readiness
```

- **Grills** are adversarial gaps/contradictions passes: each spec
  confirmation, sign-off, and every plan approval (`/grill-me`) require the
  relevant fresh pass.
- One **task gate** is always armed: product edits follow an approved plan and
  current task scope. In an active stage, `forge delegate` prepares the canonical
  implementation brief. Lite allows only its bounded authorized writes;
  degraded mode allows direct writes only during a companion outage. Quickfix
  records files touched by an otherwise authorized write and does not grant
  write authority.
  Native Codex then uses a role-based host `spawn_agent`; Claude launches its
  protected plugin companion. Raw/direct/nested `codex exec` and direct plugin
  shell launch are off-contract and hook-denied in both runtimes.
- Every artifact is **attested**: `generated_by` on the allowlist,
  `skills_used` mandatory on user-facing work, commit-stamped and fresh.
- The **ship gate** additionally demands orchestrator guidance on every
  recorded assumption and (for user-facing tasks) a functional check.
- **Hygiene runs continuously**: secrets/oversize refused at the context
  inbox, repo budgets in CI, decision lifecycle + prototype isolation linted.
- **The repo learns**: recurring review-finding classes surface via
  `forge findings patterns` (3+ hits ⇒ a refactor story, not a fourth
  patch); lessons ledger in `plans/lessons.jsonl` (`forge lesson relevant`
  before work, `forge lesson add` after repeated failures); deferred scope
  keeps a revisit trigger (`forge defer`).

---

## 1. Get the harness (once per machine)

Clone it wherever you keep repos — `./setup` records the location for the
bootstrap skills:

```bash
git clone git@github.com:knacklabs/symphony-forge.git
cd symphony-forge
./setup
```

## 2. Check your machine

Say: **"Set up my machine for KnackLabs projects."**

```bash
./forge doctor --fix
```

`--fix` auto-installs everything installable (Codex CLI via npm,
codex-plugin-cc via the `claude plugin` CLI, gstack and autoreview from their
GitHub repos, mattpocock/skills — grill-me mirrored into `~/.codex/skills` too
— emilkowalski/skills, Anthropic's frontend-design via the `skills` CLI, and
ponytail cloned into BOTH `~/.claude/skills` and `~/.codex/skills` so Claude and
Codex each load it). On Windows it also
installs Git for Windows and Python 3.10+ through winget in user scope; Forge
does not elevate itself, though an installer may show its own Windows prompt.
See [Windows support](windows.md) for the native flow and WSL2 escape hatch.
Only logins (`codex login`) stay manual.
Re-run until it says `ready`.

## 3. Create your project

Say: **"Set up a new KnackLabs project called my-app."** (the `knacklabs-new-project`
skill installed by `./setup`)

```bash
./forge init --name my-app --target ../my-app
cd ../my-app
```

This scaffolds a complete, git-initialized repo: dual-runtime adapters
(`.claude/`, `.codex/`), shared agent assets (`factory/`, including the
artifact schemas under `factory/schemas/`), the vendored engineering
constitution, the phase manifest + skill allowlist (`harness.yaml`), doc
contracts, and an armed sign-off gate. It refuses a target containing files
it would overwrite (listing them); a non-empty target with no collisions is fine.
It also creates `.factory/record-origin.json`, which records the date, current
commit, and number of commits that existed before Forge began keeping the
project record. The file is written once and is not moved forward later.

The new repo has ZERO git relation to the harness (the machinery is a
vendored copy — see "Template, Not Fork" in the README). Give it its own
home and build the application inside it:

```bash
gh repo create knacklabs/my-app --private --source . --push
# or: git remote add origin git@github.com:<org>/my-app.git && git push -u origin main
```

> Do NOT fork the harness and do NOT use `gh repo create --template` for
> client projects. A fork makes every future harness upgrade a merge into
> your app code; a template copy has no upgrade path at all — and both drag
> along the harness's own plans, run state, and history. `forge init` +
> `forge upgrade` is the only supported pairing: init creates the repo,
> upgrade refreshes machinery-only, app code is never touched.

> **Once per machine per repo:** run `direnv allow` inside the project.
> That activates `.envrc`, which pins `GSTACK_HOME` to the repo's `.gstack/`
> — every gstack output (office-hours design docs, decisions, learnings)
> lands IN the repo, committed and shared, instead of a personal `~/.gstack`.
> Append-only Forge ledgers use one record per file. Remaining legacy JSONL
> stays readable and uses Git's built-in `union` driver; no custom merge driver
> is registered. Old history on your machine? Say **"migrate my gstack
> history"** (`./forge gstack migrate`).

## 4. Discovery and prototype (phases 0a / 0b — lightweight on purpose)

Say: **"Let's run office hours on this idea."** (gstack `/office-hours`) and
fill `docs/product/DISCOVERY.md` and `docs/product/BRIEF.md` from it.
Prototype freely — no `.factory` ceremony before sign-off; the prototype is
preserved under `prototype/` afterwards as the forever UX reference.

As capabilities emerge, save each one as a draft spec, grill the exact file,
then confirm it:

```bash
./forge spec save billing --from /tmp/billing.md
python3 factory/scripts/record_grill_from_json.py --gate spec \
  --input /tmp/spec-grill.json --input-digest docs/specs/billing.md
./forge spec confirm billing
```

Capture every client decision as you go — say: **"Record that as a
decision."**

```bash
./forge decision new <slug>
```

## 5. Derive the roadmap, grill, then record client sign-off

After every spec is confirmed, say **"Build the project roadmap."** The
docs-decomposer derives spec-linked epics and stories:

```bash
./forge roadmap derive --input /tmp/roadmap.json
```

First say: **"Grill the handover."** The agent interrogates DISCOVERY, BRIEF,
confirmed specs, the derived roadmap, decisions, and prototype notes — one question at
a time, findings resolved into doc edits or decision records — and records
the verdict (`record_grill_from_json.py --gate signoff`).
**`record_signoff.py` refuses without a fresh, passing grill** (fresh =
product docs unchanged since it ran).

Then say: **"The client signed off."** The agent drafts the record; the accept
is the human's decision, not their keystroke — an explicit chat confirmation
("accepted") lets the agent run it with their name:

```bash
./forge decision new client-signoff
./forge decision accept client-signoff --by "<human name>"   # human-confirmed
python3 factory/scripts/record_signoff.py
```

Every phase from `planning` onward is refused until this is recorded.

## 6. Generate the workspace

Say: **"Scaffold the workspace."** The agent hands
`harness/nestjs-react/SCAFFOLD_PROMPT.md` to Codex to generate the nx
workspace per `harness/nestjs-react/conventions/` and `constitution/`.

## 7. Review, assign, and view the derived roadmap

The PM reviews coverage and the EM distributes the already-derived stories.
Optionally define the team first so assignment is checked and skill-matched:

```bash
./forge team set alice --role dev --skills frontend
./forge team set bob --role dev --skills fullstack
./forge roadmap assign ENG-101 --to alice
./forge roadmap list                               # grouped by epic, shows @assignee
./forge board                                      # read-only live lifecycle view
```

The board opens on **Overview**, which answers what the project is, what can
start now, what each epic delivers, and where each story sits. When the repo
has a record-origin marker, Overview also says where the Forge record begins
and how many commits precede it; an older repo with no marker makes no claim.
To inspect a different initialized example repo, point the same board command
at it:

```bash
./forge board --repo <example>
```

The checked-in source at `factory/board/example/` is the smallest readable
brief, confirmed spec, and roadmap that the production capture validators
accept. It is intentionally a data-only validation example. The current board
server reads its page from the `--repo` target, so pass a full initialized repo
to the command above; direct serving of the data-only bundled tree is deferred
until the page resolver changes.

`plans/roadmap.json` is the durable backlog: intake marks items active,
`pr_ready.py` marks them done with history links, assignments survive
re-imports, and "what's next?" always knows the next story (and nags the EM
about unassigned ones). Refine it by PR as planning teaches you more.

To read the committed project record by story, event type, or date, say
**"Show me the project history."** The agent runs `./forge history`; events
without a story are shown as unattributed instead of being hidden.

## 8. The feature loop

Start each feature with: **"Start the next story on the roadmap."**

```bash
git worktree add ../ENG-123 -b feat/ENG-123-build-billing-dashboard
cd ../ENG-123
python3 factory/scripts/intake.py --issue ENG-123 --title "Build billing dashboard"
```

Story intake creates the shared contract in an isolated planning worktree.
Each leaf task then owns its worktree, branch, proof, and PR. Dependency-ready
tasks may advance together when their scopes are disjoint, and dependency-ready
stories may also advance in parallel. Story evidence ships in place under
`.factory/stories/<key>/`.

1. **Plan (mandatory — enforced)** — say: **"Plan this task."** and switch to
   PLAN MODE (shift+tab). While the task is unplanned, the hook blocks
   product-code edits and writing Codex delegation, so there is no way to
   "just start coding". Plan per `factory/prompts/planner.md`. Claude delegates
   read-heavy exploration via the Sol/medium `explorer` role (read-only); raw
   `codex exec` is blocked. Native Codex spawns the configured Sol/high
   `planner-high` role without a model or reasoning override. New decisions get
   records. **Before approval, one independent cold grill is mandatory** — say:
   **"Grill me on this plan"** (`/grill-me`); the verdict is recorded
  (`python3 factory/scripts/record_grill_from_json.py --gate plan --input
  <grill-json> --input-digest <plan-file>`) with every finding disposed and
  every amendment explained. In native Codex, run `./forge grill run --gate
  plan --file <plan-file>` to prepare one griller descriptor; put the complete
  descriptor and its context metadata in the actual `spawn_agent` message,
  then record the exact returned JSON with `python3
  factory/scripts/record_grill_from_json.py --gate plan --input <grill-json>
  --input-digest <plan-file> --cold-result <path> --preparation-id <id>`.
  Claude keeps its command-managed cold-reader lifecycle. If an already
  approved plan changes before stage start, record its amendment bridge against
  the existing cold proof and return directly to native approval; do not launch
  another cold grill solely for changed bytes. Then say: **"Save the plan."** The save records
   `awaiting-approval`; approve the exact displayed final plan through native
   Plan Mode. There is no board approval, manual approve command, or second
   unchanged save.

```bash
./forge plan save --from <approved-plan-file>
```

2. **Decompose** — say: **"Decompose it."** (`docs-decomposer`; the recorded
   JSON must match `factory/schemas/decomposition.json`, incl. the
   `user_facing` flag):

```bash
python3 factory/scripts/record_decomposition_from_json.py --input /tmp/decomposition.json
python3 factory/scripts/update_run.py --phase implementing --decomposition-status recorded
```

3. **Implement** — say: **"Implement it."** The orchestrator runs
   `./forge stage start <id>` and then `./forge delegate <id>` for one bounded
   task at a time. In native Codex, that command validates the task, prepares
   the canonical brief, and records a preparation row including any narrowed
   scope; the coordinator then spawns the matching configured
   host role without model or reasoning overrides. Routine implementation,
   automated tests, diagnosed or review fixes, documentation edits, and
   mechanical refactors use the Luna/max role. Raw/direct/nested `codex exec` and
   direct plugin shell launch stay off-contract and hook-denied for general or
   manual delegation. Claude keeps its protected
   `codex-plugin-cc` launch. Forge enforces the active task, worktree and
   effective scope but does not restrict native foreground/background, status,
   cancel, resume or other
   host collaboration features, and closeout does not require native process
   proof. Feature type routes the design
   skills, ENFORCED at record time: `user_facing: true`
   tasks MUST load `emil-design-eng` + `frontend-design` and attest them in
   the artifact's `skills_used` — the recorder refuses otherwise
   (`apple-design`/`animation-vocabulary` advisory for motion work); backend
   tasks skip them all. The implementer writes and runs the tests and
   records the artifact itself:

```bash
python3 factory/scripts/record_test_from_json.py --kind automated --input /tmp/automated-test.json
```

The implementer runs focused checks and records them. The coordinator's
`forge task close <task-id>` owns the one canonical full verifier and records
its complete automated evidence before review.

4. **Review** — say: **"Review it."** ONE run of the unchanged, externally
   maintained Autoreview skill publishes a
   validated selected generation containing all three lenses
   (`factory/prompts/reviewer.md`):

```bash
./forge review <task-id>
```

Forge-managed Autoreview is an authenticated, externally maintained black box
and may invoke Codex or agents internally; those internals are its own policy.
The general/manual delegation ban on raw or nested `codex exec` does not
constrain that helper.

`record_review_from_json.py --aspect ...` is reserved for Lite diagnostics and
one-time migration input; fixed lens files are not ordinary task proof.

5. **Functional check** — only when the decomposition says
   `user_facing: true`; the final check uses the Sol/high `functional-checker`;
   record the proof, rerun `./forge task close <task-id>` so the unchanged
   selected review is reused and the stage is sealed, then say: **"Is this PR
   ready?"**

```bash
python3 factory/scripts/record_test_from_json.py --kind functional --input /tmp/functional-test.json
./forge task close <task-id>
python3 factory/scripts/pr_ready.py
```

`pr_ready.py` exits non-zero if any required artifact is missing, unstamped,
or stale. Merge stays manual.

---

## Continuously: the context inbox

Client emails, meeting transcripts, voice-note summaries, stray docs — drop
them in `docs/context/` the moment you get them. Dumping is free; tracking is
automatic. Then say: **"Process the context dump."**

```bash
./forge context scan                 # register files in docs/context/ledger.json
# agent harvests per factory/prompts/harvester.md:
#   pending file -> proposed decision records + DISCOVERY/BRIEF/architecture edits
./forge context mark <file> --harvested --outputs <paths>   # or --ignored --notes "why"
./forge context list --pending
```

**You will not miss pending context — four surfaces make sure:**
1. every agent session opens with the unharvested count (SessionStart hook)
2. `./forge next` puts "harvest first" as step 1 in any phase
3. the daily `gardener` workflow opens a GitHub issue while anything is
   pending, and closes it at zero
4. `./forge plan save` **refuses** while context is pending — you cannot
   approve a plan over an unread client email

Decisions proposed by a harvest still need a HUMAN accept
(`./forge decision accept <slug> --by "Name"`).

## Keeping your repo honest

Recorders refuse any artifact that does not match its schema in
`factory/schemas/` — wrong shape, wrong types, or a `generated_by` outside
the `harness.yaml` allowlist. Adopting a new tool is a harness PR, never a
local choice (see WORKFLOW.md "Determinism Contract").

CI runs these on every PR (and you can run them any time):

```bash
python3 factory/scripts/check_dual_runtime.py   # reference-not-duplicate + schema/allowlist parity
python3 factory/scripts/check_agents_hygiene.py # AGENTS.md size + links
python3 factory/scripts/check_factory_scaffold.py
```

If `codex-plugin-cc` is unavailable while using Claude, see
`docs/degraded-mode.md`. Native Codex does not depend on that plugin and uses
host subagents; neither route falls back to direct `codex exec`.

## Migrating an existing repo into the harness

Already built a prototype (or an early project) with agents, outside the
harness? Say: **"Migrate this repo into the harness."** (the
`knacklabs-migrate-project` skill installed by `./setup`)

The deterministic core is `forge adopt`, run from the harness clone against a
CLEAN target tree:

```bash
./forge adopt --target ../legacy-repo --name my-app
```

Adopt writes the same create-if-absent `.factory/record-origin.json` boundary
before future work is recorded. Running adoption again can never rewrite that
starting point or make the historical record look more complete than it is.

It vendors the machinery, preserves any pre-existing `AGENTS.md`/`CLAUDE.md`
into `docs/context/migrated-*` (the harvester picks them up), creates
project-owned files only where missing, and never deletes existing work —
every overwrite is a reviewable git diff. The skill then walks the judgment
part: sorting code into `prototype/`, dumping notes into `docs/context/`,
harvesting DISCOVERY/BRIEF and decision records, formalizing a historical
sign-off, and handing off to `./forge next`. Repos that already carry the
harness are routed to `forge upgrade` instead.

## Upgrading a project to a newer harness

Say: **"Upgrade this repo to the latest harness."** (the
`knacklabs-upgrade-project` skill installed by `./setup`)

The skill locates the setup-pinned harness clone, verifies its origin, branch,
and clean state, and stops if its fast-forward-only pull fails. Every periodic
upgrade cycle also requires a clean, committed project baseline. It audits the
project, refreshes machinery with `forge upgrade`, repairs tooling with
`forge doctor --fix`, and pauses for review of the diff.

Harness-owned machinery (`factory/` incl. schemas, adapters, `constitution/`,
contracts) is replaced; project-owned content (`harness.yaml`, `AGENTS.md`,
plans incl. the roadmap, decisions, context, prototype, `.factory/`) is never
touched, and `factory/skills/proposed/` survives the swap. After the review,
the skill backfills deterministic project-level gaps and guides you through
re-authoring incomplete stories one at a time with `forge roadmap fill`.
Completed stories are never rewritten and roadmap data is never bulk-loaded.
It then re-runs verification and audit, reports `forge next`, and leaves the
reviewed upgrade for you to commit as the next cycle's clean baseline.
