---
slug: strict-role-split
title: The role split routes task work to Codex workers
status: confirmed
saved: 2026-09-11T12:14:29+00:00
---

# The role split routes task work to Codex workers

> Captured 2026-08-11 from operator feedback. Decision 0053 later made the
> coordinator interchangeable while preserving the settled rule: coordinators
> assign bounded implementation to Codex workers. Native Codex uses host
> subagents without claiming a process-level identity fence.

## Why

This capability originated when the role split was instruction-only: an approved plan let an orchestrating session edit product and those edits could ride a worker commit. Decision 0053 later made the coordinator interchangeable. Claude retains the mechanically admitted plugin-worker boundary. Native Codex now uses role-based host subagents and enforces the active task, matching worktree, and effective scope without pretending Forge can identify which host process authored each byte.

## Behaviour

The three original boundaries below were grilled and human-settled 2026-08-11. This revision applies Decision 0053 and the current FORGE-COORD-1 contract without reopening them.

The task historically named `FORGE-COORD-1/NATIVE-FOREGROUND-ACTIVATE` owns the current adapter wording and dual-runtime regressions; its name no longer creates a native foreground restriction. The dual-coordinator capability owns combined-review packaging and its task allocation; this role-split specification requires only that the active orchestrator launch an independent Codex autoreview and never assess or certify its own implementation inline.

### Writer routing

- In Claude, orchestrator writes to **product and canon paths** remain denied;
  `forge delegate` launches the protected `codex-plugin-cc` worker and the
  bounded degraded window below is its outage valve. In native Codex,
  `forge delegate` validates the task and prepares the canonical brief, then
  Main assigns it to a configured role through host `spawn_agent`. It never
  calls `codex exec`. Raw/direct/nested `codex exec` and direct plugin shell
  launch are off-contract and hook-denied in both runtimes.
- Native Forge hooks enforce plan, active-task, effective-scope and
  protected-state boundaries. They do not require a worker process token,
  session identity, PID ancestry, held launch lock or foreground state. The
  role split is an explicit workflow assignment in native mode, not a
  mechanical claim that Forge can distinguish Main from its subagent process.
- The shared repository path classifier owns exemptions. All `docs/`, `plans/`,
  `prototype/`, and `.gstack/` paths plus the named repository metadata files
  `README.md`, `.gitignore`, `.gitattributes`, and `.envrc` remain orchestration
  surfaces. Protected `.factory/` state changes only through its recorders and
  owning commands; the scratchpad and Git operations retain their existing routes.
- Review findings are assigned as follow-up briefs on the same stage. Native
  Main uses the responsible role-based subagent; Claude relaunches its plugin
  companion. There is no trivial-fix carve-out from task scope or review.

### Exploration routing

- Claude coordination uses `/codex:rescue` for delegated read-only discovery.
  Native Codex may explore directly or use host subagents. Forge imposes no
  native foreground/background, status, cancel, resume or recovery feature
  lock. Neither route changes task scope or protected-state authority.
  Gate reads include verifying a delegated diff and resolving a raised signal.

### Degraded-mode valve — ledgered, never silent

- When the configured delegated-writer path fails after its ordinary repair is attempted (outage or unrecoverable balk-loop), direct
  implementation is allowed ONLY inside an explicitly opened degraded-mode
  window: ledgered like a quickfix with the failure named, closed with the
  work recorded, declared by the PR. The window may claim at most five exact
  locked files, rejects opaque/globbed writes, and can never change the repository-kind
  marker. The write-lockout hook honors a valid open window; everything else refuses.
  Native repair does not require this valve because native delivery does not
  depend on Claude or `codex-plugin-cc`.

## Acceptance criteria

- With an approved plan and active stage, Claude coordinator writes to a
  product/canon path are denied with a message naming `forge delegate` and the
  degraded-mode window. Native Codex permits the active task's effective scope
  without worker-process identity while refusing wrong-task, wrong-worktree,
  out-of-scope and protected-state mutations. A Claude degraded window retains
  its five-file budget and rides the PR.
- Tests derive orchestration exemptions from the shared path classifier and
  prove that protected state still changes only through recorders/commands.
- Both adapters and AGENTS.md state the coordinator-versus-delegated-writer routing and the current approved read-only exploration lane.
- A registered Claude worker with matching task, stage, kind, worktree, and
  scope may write. Native task-scoped writes require no process registration;
  wrong-task, wrong-worktree and out-of-scope changes still refuse.
- Init, adopt, and upgrade preserve client product/canon task-scope enforcement,
  the vendored replacement boundary, native host-role routing, and Claude
  companion admission.
- `docs/degraded-mode.md` documents the Claude companion outage exception.
- A decision record captures the boundary set and its grilled rationale.
- Gate tests pin: deny-under-approved-plan, allow-in-window,
  orchestration-surface exemptions, and the window's ledger record.

## Boundaries

- Decision 0011 as amended by Decision 0053: the active orchestrator directly launches one independent Codex autoreview operation; the orchestrator never performs the assessment inline or self-certifies.
- Reads are not machine-fenced (would break review/verify); the fence is
  writes, where enforcement is clean.
- Client repos inherit the same hook behavior (vendored machinery).

## Decomposition (epic → stories)

1. **FORGE-ROLE-1 — shipped original write lockout + degraded window** — the
   hook change, the window primitive, adapter/AGENTS.md/degraded-mode.md
   updates, the decision record, gate tests. (Single bounded story; its own
   implementation was delegated, dogfooding the rule it landed.
2. **FORGE-COORD-1 / NATIVE-FOREGROUND-ACTIVATE — current coordinator-neutral amendment** — adapter wording, host-native role dispatch, client-delivery regressions, and the explicit independent-review boundary. Combined-review proof format remains owned by the dual-coordinator capability and its approved task contract.
