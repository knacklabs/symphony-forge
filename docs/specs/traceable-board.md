---
slug: traceable-board
title: The board is complete, JIT-planned, and always backtrackable
status: confirmed
---

# The board is complete, JIT-planned, and always backtrackable

> Design captured 2026-08-07 from a working session with vrknetha. This is
> epic-sized; it decomposes into the stories in "Decomposition" below. One open
> detail is flagged inline (story-grill scope).

## Why

Four gaps, in the order they hurt:

1. **Speculative task contracts produce wrong code.** Today a story is planned
   and grilled ONCE, then `record_decomposition` writes every task's contract
   upfront (decision 0007, "immutable decomposition"). Later tasks depend on
   what earlier tasks actually built — which the upfront contract cannot know.
   The agent implements task N from a contract written before tasks 1..N-1
   existed, fills the unknowns by ASSUMING, and the assumption ships as an
   incorrect implementation. Grounding each task in the real prior state, JIT,
   is the fix.
2. **The board can rot, so agents cannot backtrack.** The provenance chain
   (spec→story→plan→decomposition→stage→evidence→outcome) stops one step short
   of the PR. `forge pr-link` is voluntary, ungated, and unconsumed; a PH-5
   audit found 30 of 36 merged PRs untraceable in-repo. If the board is not
   updated religiously, there is no durable record to reconstruct what shipped.
3. **Ad-hoc requests get lost.** A dev says "what about X" mid-flight and it
   evaporates into chat because the only story-shaped capture demands full
   acceptance criteria at capture time.
4. **Epic/story/task/PR/ticket mapping is ambiguous.** WORKFLOW.md even invites
   the confusion ("task state is mirrored into the tracker"), leaving "is a task
   a ticket?" unanswered.

Because the harness is vendored, every client inherits all four.

## Behaviour

**Determinism is non-negotiable (decision 0001).** Every rule below is enforced
by a deterministic gate — a script, a schema-validated recorder, or a CI check
that REFUSES to proceed — never by agent discipline or memory. The agent authors
content (plans, grills, task contracts); the gates guarantee the content exists,
is fresh, and is digest-bound before the next step runs. A rule that cannot be
made a deterministic gate is a warning, not a rule.

### One anchor: ticket = story = PR = plan (1:1)

The roadmap item IS the ticket; its `key` is the ticket id. The **in-repo
roadmap is the source of truth** (no external tracker in this capability). One
story → one branch (`feat/<key>-<slug>`) → one PR → one plan → one recorded
review. **Tasks are never tickets** and never their own PR — they are the
story's internal stages. **Epics are grouping only** (an optional tracker
parent), never PR-bearing.

| Level | Ticket | Branch | PR | Plan | Grill | Shown on board |
|---|---|---|---|---|---|---|
| Epic | grouping only | — | — | — | — | as a group header |
| **Story** | **the ticket, 1:1** | one | **one** | one | breakdown grill | the card |
| Task | — | — | — | JIT contract | per-task JIT grill | under its story |

### Task list upfront, task detail just-in-time

- **The task breakdown is created upfront at decomposition** — the list: which
  tasks, in what order, their dependencies and one-line objectives — tied to the
  story and **shown on the board** so the whole shape is visible before work
  starts.
- **Each task is planned AND grilled just-in-time, when it is reached.** Its
  detailed contract (write_scope, acceptance, tests, approach) is written
  against the ACTUAL repo state after the prior tasks and grilled to catch
  assumptions, BEFORE implementing. The refinement is recorded as a stage
  contract change (decision 0023 already tracks this) and surfaced in the UI.
- **The JIT grill is a deterministic gate, not a suggestion.** A stage's
  implementation delegation is REFUSED without a fresh, digest-bound per-task
  grill for that task — exactly as `plan save` refuses an ungrilled plan and
  `stage done` refuses a missing write launch. No grilled task contract, no
  implementation. This is what makes JIT planning enforced rather than
  hoped-for.
- **Two grill points, kept deliberately, because they catch different
  failures:** the story-level plan-grill (which already grills the breakdown as
  part of the plan) validates the decomposition — are these the right tasks?
  does the shape cover the story? is it too big to split? — and the per-task
  JIT grill validates each task's details against the real prior state (no
  speculative assumption). Dropping the story-grill would leave the
  decomposition itself unchecked; the per-task grill is the single new mechanism
  added on top.
- The split rule keeps this bounded (~5 tasks/story), so it is a handful of
  quick task-grills, not dozens.

### Creation timing

- **At sign-off:** all epics + stories exist — `roadmap derive` produces them
  from confirmed specs, and the sign-off gate already requires a derived
  roadmap. Sign-off is the go-ahead on that ticket set, not the trigger to
  invent it.
- **When a story is planned:** its task list is created at decomposition;
  each task's detailed contract is planned+grilled JIT as it is reached.

### Split a story into sibling stories

Default is decompose-into-tasks; split only when a rule trips:
1. **Independence (hard):** two task-subsets with no dependency edge AND disjoint
   write scopes — i.e., they could run in parallel — ARE two stories (the
   harness forbids intra-story parallelism, so parallelizable ⇒ split).
2. **Reviewability (bounded):** more than ~5 tasks, or a diff that will not fit
   one review sitting / one PR ⇒ split or state a reason. The story grill asks
   this explicitly.

### Ad-hoc capture — one path

`forge roadmap add <KEY> --story --no-spec --reason "<why>"` lands the idea as
visible spec-debt in "Needs spec," unplannable until `spec confirm` +
`link-spec`. Drop the `--ac` requirement on the `--no-spec` path (AC arrive with
the spec). Division of the other inboxes stays: raw client material → context
inbox; "pull this out of my branch" → `defer add`; small+urgent → lite window.

### Enforcement — the backtracking guarantee

`pr_ready` runs BEFORE a PR number exists, so linkage lives in CI:

- **Gate A — PR required-check:** every PR must resolve to exactly one work
  record — branch `feat/<key>-*` or `Ticket: <key|window-id>` in the body — that
  is on the roadmap and flips to `done` INSIDE this PR's diff with
  `.factory/history/<key>/` present (or a window closed + ledgered). Else merge
  is blocked. "Every PR needs a ticket," enforced where PRs exist.
- **Gate B — auto-link on merge + red-main invariant:** a merge workflow runs
  `forge pr-link <key> <PR#>` (linkage by automation, not discipline); main CI
  then fails if any `done` story lacks a `pr-linked` event + an outcome (or
  `predates_outcome_contract`) + a history dir. The board renders from main, so
  it cannot silently rot.
- **Gate C — intake refuses off-board keys:** one-line change (refuse `absent`,
  not only `blocked`), pointing to `roadmap add --no-spec`. Work cannot start
  off-board.

Everything else stays advisory (doctor's legacy reports, unaccepted decisions,
epic hygiene, recurring findings). Hard gates are reserved for the two
invariants: completeness + PR-linkage.

### Board/UI

The board shows **epic group → story card → its task list → each task's status
and its JIT plan/grill as it is reached** — full traceability, no speculative
gaps, and a done story always resolves to its PR.

### Remove, to keep it simple

- Task-state tracker mirroring in WORKFLOW.md "Source of Truth" → mirror
  **stories only** (kills the "are tasks tickets?" ambiguity).
- `--ac` on the `--no-spec` capture path.
- Manual `forge pr-link` → degraded-mode fallback once Gate B automates it.

## Acceptance criteria

- A task is not implemented until its detailed contract has been planned and
  grilled against the repo state left by the prior tasks; that refinement is
  recorded and visible on the board.
- The task breakdown (list, order, objectives) exists and is shown under its
  story from decomposition onward.
- A PR cannot merge unless it resolves to exactly one on-board story (or a
  ledgered window) whose done-flip and history archive travel in the PR's diff.
- Every `done` story on main carries a durable PR link, an outcome, and a
  history dir; a missing one fails main CI.
- Intake refuses a key that is not on the roadmap, naming the ad-hoc path.
- An ad-hoc "what about X" is captured with one command as visible spec-debt,
  with no acceptance criteria demanded at capture.
- The board renders a done story's PR link, and the link survives a clone with
  no remote.
- Every rule in this capability is a deterministic gate (script / recorder / CI),
  not agent discipline — an agent with no memory of the rules cannot weaken any
  invariant.
- A `sanitise` run leaves the repo canonical: no orphaned mode/quickfix windows
  or stale task-scoped `.factory` state, roadmap healed, board completeness and
  PR-links verified; it fixes what is mechanical and reports the rest,
  fabricating nothing.

## Boundaries

- In-repo roadmap only; no external tracker sync in this capability (a separate
  future one).
- This changes decision 0007's immutable-upfront-decomposition toward JIT task
  planning; that shift is deliberate and needs its own decision record.
- Legacy clients are brought up to the enforced bar by the
  `knacklabs-upgrade-project` skill (a story here), not by silent auto-migration.
- No rewriting of history; missing past records are marked, never fabricated
  (inherits `project-record`'s stance).

## Decomposition (epic → stories)

1. **JIT task planning + grilling** — decomposition records the task LIST;
   per-task plan+grill JIT against real prior state; contract-change recording
   (0023); a decision record superseding 0007's immutable stance. (Core loop.)
2. **Enforcement gates A/B/C** — PR required-check workflow, auto-link-on-merge +
   red-main invariant, intake refuses off-board. (CI + intake + gate code.)
3. **Board/UI** — render epic→story→task with per-task JIT plan/grill + the
   done-story PR link.
4. **Ad-hoc + simplification** — `--no-spec` drops `--ac`; remove task-state
   tracker mirroring; manual `pr-link` → fallback.
5. **`knacklabs-upgrade-project` skill + runbook** — machinery upgrade + guided
   doctor-loop re-authoring that backfills legacy clients to the enforced bar.
6. **`knacklabs-sanitise-project` skill (deterministic repo hygiene)** — a skill
   wrapping deterministic `forge` commands to keep a client repo canonical:
   `doctor` (health) + `roadmap heal` (drift) + close/clear orphaned mode/quickfix
   windows and stale task-scoped `.factory` state + verify board completeness and
   PR-linkage + flag secrets/cruft. It fixes what is mechanically fixable and
   reports the rest (never fabricating records); runnable on demand and in CI. It
   is itself deterministic — every action is an existing `forge` command, not a
   judgement call.
