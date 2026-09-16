# Product Brief

## Summary

Symphony Forge is KnackLabs's process harness for building applications with
either Claude Code or native Codex coordinating and delegated Codex workers executing. It turns in-repo architecture and
decision documents into shipped software through a fixed sequence — discovery,
confirmed capability specs, a derived roadmap, client sign-off, one planned
story at a time, bounded tasks, deterministic verification, one independent
review lifecycle with quality, performance, and security assessments,
and a recorded outcome — and it enforces that sequence in code rather than in
instructions an agent can talk itself out of.

It exists because agentic delivery fails quietly. Work gets done that nobody
planned, tests that were promised are never written, a review is claimed but
never ran, and six weeks later nothing in the repo says why any of it happened.
The harness makes each of those a refusal at the moment it would occur, and
leaves the evidence committed next to the code.

The harness is vendored, never forked: a client repo is born with its own
history and receives the machinery by copy, then upgrades in place.

## Users

- **Developers** running a delivery loop through Claude Code or native Codex, who want
  the next action to be deterministic rather than remembered.
- **Maintainers of this repo**, who dogfood the harness on itself — every gate
  here is exercised by the work that changes it.
- **KnackLabs client projects**, which vendor the machinery and inherit the
  gates without inheriting this repository's history.

## Target Outcome

A team can move from confirmed product intent to a PR-ready application change
through one visible, deterministic path, with every approval, implementation
boundary, verification result, review, and delivered outcome preserved in the
repository and reproducible in a fresh worktree.

## Key Flows

- A developer says "set up a new project"; the harness checks the machine,
  scaffolds a fresh repo with its own origin, and hands off to that repo.
- A developer asks "what now?" in any phase and `./forge next` reads recorded
  state and prints the exact next action, identically in both runtimes.
- A capability is captured as a spec, grilled, and confirmed; the roadmap is
  derived from confirmed specs; the client signs off once, and that sign-off
  gates every later phase.
- One roadmap story is planned, grilled, and approved, then decomposed into
  bounded dependency-aware tasks; each task owns a worktree, is delegated with
  a composed brief, implements and tests its change, runs deterministic
  verification, and loops through independent review and fixes until clean.
- Verification, tests, one review lifecycle with three assessments, and an outcome are recorded through
  schema-validated commands, and `pr_ready` refuses until all of them exist.
- Dependency-ready stories fan out into separate worktrees; their roadmap
  status flips converge deterministically on merge.
- An existing repo is adopted into the harness, or a client repo is upgraded to
  a newer harness version, without either forking this one.

## Domain Concepts

- **Capability spec** — what a capability does and how it is judged, confirmed
  before any roadmap exists.
- **Epic / story / task** — a business outcome area, one deliverable capability
  owning a worktree, and one bounded implementation step inside it.
- **Plan** — the approved, grilled argument for one story, attesting every
  active decision.
- **Decomposition and stages** — the immutable task contract and its mutable
  execution twin.
- **Gate** — a refusal in code: sign-off, plan approval, decomposition, verify,
  tests, review, outcome.
- **Grill** — an interrogation of a handover before it becomes the contract
  downstream work builds on, bound by digest to the exact artifact.
- **Decision record** — a durable, human-confirmed choice; the active corpus is
  attested by every plan.
- **Evidence** — the recorded proof under `.factory/`, archived per story at
  ship, written only by the recorder scripts.
- **Signal** — a contradiction, confusion, blocker, or scope change a worker
  raises before it guesses.
- **Lesson, assumption, deferral, quickfix** — the four ledgers that keep what
  was learned, assumed, parked, and patched.

## Constraints

- Two runtimes must stay in lockstep: the same contract in `AGENTS.md` and its
  Claude adapter, verified by `check_dual_runtime.py`.
- Claude Code or native Codex coordinates; only an admitted delegated Codex worker writes product. Review is one autoreview operation run by
  the orchestrating session, never a nested reviewer.
- The vendored gate surface is frozen between vendorings and hash-checked, so
  client repos cannot drift from the machinery they were given.
- Evidence enters `.factory/` only through recording commands that validate
  against `factory/schemas/`, including a pinned `generated_by`.
- The planning lock is always armed. Full work requires an approved plan and
  decomposition; bounded ledgered quickfix and Lite windows are the other
  planning-lock exits. The degraded window is the separate five-file delegated-
  writer outage valve.
- One story is planned at a time; each task owns a worktree, and dependency-ready tasks may overlap only with disjoint protected scopes.
- The board is read-only and derives everything from committed artifacts; it
  never approves.
- This repository stays independent of any client source repo.

## Out of Scope

- Being a framework, runtime, or application template — the harness ships
  process machinery, not product code.
- Hosting, CI, or deployment infrastructure for client applications.
- A hosted service, database, or multi-user server; the board is localhost and
  file-backed.
- Replacing human judgement at the gates that require it: decision acceptance,
  client sign-off, and plan approval remain human acts.
- Supporting agent runtimes beyond Claude Code and Codex.
