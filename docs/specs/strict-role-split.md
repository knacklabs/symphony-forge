---
slug: strict-role-split
title: The role split is a gate: coordinators orchestrate, only delegated Codex workers write product
status: confirmed
saved: 2026-09-11T12:14:29+00:00
---

# The role split is a gate: coordinators orchestrate, only delegated Codex workers write product

> Captured 2026-08-11 from operator feedback. Decision 0053 later made the
> coordinator interchangeable while preserving the settled rule: orchestration
> does not grant product-write authority; an admitted delegated Codex worker writes.

## Why

This capability originated when the role split was instruction-only: an approved plan let an orchestrating session edit product and those edits could ride a worker commit. The shipped hook now enforces the boundary. Decision 0053 later made the coordinator interchangeable without changing the rule: coordination does not grant product-write authority; an admitted delegated Codex worker writes within the active task contract.

## Behaviour

The three original boundaries below were grilled and human-settled 2026-08-11. This revision applies Decision 0053 and the current FORGE-COORD-1 contract without reopening them.

`FORGE-COORD-1/NATIVE-FOREGROUND-ACTIVATE` owns the current adapter wording, native admission coverage, and dual-runtime regressions. The dual-coordinator capability owns combined-review packaging and its task allocation; this role-split specification requires only that the active orchestrator launch an independent Codex autoreview and never assess or certify its own implementation inline.

### Write lockout — the hook, always on

- In factory repos the orchestrating session's writes (Edit/Write/Notebook,
  and Bash write-shapes) to **product and canon paths** — code, tests,
  `.github/`, `constitution/`, `factory/` machinery including
  prompts and skills, `AGENTS.md`, `WORKFLOW.md`, vendored adapters — are DENIED even
  under an approved plan and active stage. The ordinary sanctioned path for
  those files is `forge delegate` (Codex); the bounded degraded window below is the outage valve.
- The shared repository path classifier owns exemptions. All `docs/`, `plans/`,
  `prototype/`, and `.gstack/` paths plus the named repository metadata files
  `README.md`, `.gitignore`, `.gitattributes`, and `.envrc` remain orchestration
  surfaces. Protected `.factory/` state changes only through its recorders and
  owning commands; the scratchpad and Git operations retain their existing routes.
- Consequence, deliberate: review findings are re-delegated as follow-up
  briefs on the same stage — mandatory, and mechanically so, since the
  session cannot patch product. No trivial-fix carve-out (grilled: the
  carve-out is the loophole).

### Exploration routing

- Claude coordination uses `/codex:rescue` for delegated read-only discovery.
  Native Codex coordination may explore read-only in its current session; the
  unshipped native explore/background command refuses before dispatch until its
  owning lifecycle task lands. Neither route grants implementation authority.
  Gate reads include verifying a delegated diff and resolving a raised signal.

### Degraded-mode valve — ledgered, never silent

- When the configured delegated-writer path fails after its ordinary repair is attempted (outage or unrecoverable balk-loop), direct
  implementation is allowed ONLY inside an explicitly opened degraded-mode
  window: ledgered like a quickfix with the failure named, closed with the
  work recorded, declared by the PR. The window may claim at most five exact
  locked files, rejects opaque/globbed writes, and can never change the repository-kind
  marker. The write-lockout hook honors a valid open window; everything else refuses.
  Native repair does not require Claude or `codex-plugin-cc`.

## Acceptance criteria

- With an approved plan and active stage, a coordinator Edit to a product/canon
  path is denied with a message naming `forge delegate` and the
  degraded-mode window; a classifiable in-scope edit inside a valid window is
  allowed only within its five-file budget, while a sixth, opaque/globbed write,
  or repository-kind-marker edit refuses. The window rides the PR.
- Tests derive orchestration exemptions from the shared path classifier and
  prove that protected state still changes only through recorders/commands.
- Both adapters and AGENTS.md state the coordinator-versus-delegated-writer routing and the current approved read-only exploration lane.
- A registered live worker with matching task, stage, kind, worktree, and scope may write; unregistered, stale, revoked, wrong-task, wrong-worktree, or out-of-scope writers refuse.
- Init, adopt, and upgrade prove that client-owned product/canon remains locked while vendored harness machinery follows its separate replacement boundary and both adapters retain the same enforcement.
- `docs/degraded-mode.md` documents the window as the single exception.
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
2. **FORGE-COORD-1 / NATIVE-FOREGROUND-ACTIVATE — current coordinator-neutral amendment** — adapter wording, native admission, client-delivery regressions, and the explicit independent-review launch boundary. Combined-review proof format remains owned by the dual-coordinator capability and its approved task contract.
