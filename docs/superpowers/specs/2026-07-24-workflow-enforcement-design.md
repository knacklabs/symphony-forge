# Workflow Enforcement Hardening — Symphony Forge

## Context

Devs (and drifting agent sessions) can skip the factory workflow. Five gaps plus one new flow, all confirmed against the current code:

1. **Bypassable gates** — the planning lock (`factory/scripts/pre_tool_use.py:113-133`) only covers Edit-family tools (a Bash `cat > src/x` or `sed -i` sails through), only arms after client sign-off, and `update_run.py` doesn't enforce phase ordering.
2. **Plan sprawl** — plans have minimal frontmatter and no listing view; hard for an agent to see what's implemented vs pending.
3. **Contradictions** — signals exist (`.factory/signals.jsonl`) but nothing forces a contradiction check against active decisions at plan-save time.
4. **Plan-mode skipping** — no legitimate small-fix path exists, so the lock just isn't armed and devs edit freely.
5. **Memory** — decision 0012 mandates in-repo project memory but Claude's auto-memory still writes to `~/.claude` user-level.
6. **NEW: prototype→specs→roadmap** — devs prototype freely; specs must be generated and saved per capability as they go; epics/user stories are *derived* from specs (never hand-authored); sign-off is refused until specs + derived roadmap exist; after sign-off the loop pulls one story at a time, plans it, ships it.

**Threat model (user-confirmed): agent drift, not adversarial devs.** Enforcement = hooks + deterministic script gates; heuristics are acceptable. User chose: explicit quickfix opt-out, always-armed lock, plan-vs-decisions contradiction gate, in-repo memory dir.

**Enforcement principle (user-added): devs lazily jump straight to generating code instead of thinking aloud. Every commit point — spec confirm, plan save, sign-off — must therefore require a fresh grill pass, so the agent's extraction interrogation cannot be skipped.** Plan save and sign-off already have `require_grill()`; spec confirm gets it too (section D).

All changes are to this template repo (hooks, `forge_cli/`, docs). Branch: `chore/codify-process-rules`.

---

## A. Always-armed lock + quickfix escape hatch (gaps 1 & 4)

**`factory/scripts/pre_tool_use.py`:**
- `planning_locked()` (lines 48-53) becomes: locked unless `plan_status == "approved"` OR an active quickfix window exists. Drop the `issue_key`/`client_signoff` conditions — missing/reset `run.json` now means *locked*, not unlocked. Allowlisted paths (`PLANNING_WRITE_OK` lines 31-34: `plans/ docs/ .factory/ factory/ prototype/` etc.) keep discovery/prototype ceremony-free.
- **Bash write-guard**: while locked and not in plan mode, deny Bash commands that match write patterns (`>`/`>>` redirect, `tee`, `sed -i`, `cp`, `mv`, `touch`) AND reference a path resolving inside the repo outside the allowlist. Heuristic regex + token path-extraction, reusing the existing `Path.resolve()` canonicalization at lines 118-125. `# ponytail: heuristic, defends drift not adversaries — tighten patterns if a real bypass shows up`.
- Deny messages must name both exits: "enter plan mode (shift+tab)" or `./forge quickfix start "<reason>"`.

**New `forge_cli/quickfix.py`** + wiring in `factory/scripts/forge.py` (mirror `forge_cli/signal.py` structure):
- `./forge quickfix start "<reason>"` → writes `.factory/quickfix.json` `{id, reason, started_at, max_files: 25, files: []}` and appends an `open` record to `plans/quickfixes.jsonl` (durable ledger, same JSONL merge-driver treatment as signals).
- While active, `pre_tool_use.py` allows product edits but appends each distinct product file to `quickfix.json.files`; exceeding `max_files` → deny with "scope exceeded — this is not a quickfix, enter plan mode".
- `./forge quickfix done` → appends closure (files touched) to the ledger, removes `.factory/quickfix.json`.
- `session_start.py` surfaces an open quickfix window in its context injection (alongside open signals, lines ~66-74).

**`factory/scripts/update_run.py`** — add a `PHASE_PREREQS` dict enforcing ordering among gated phases (currently missing, lines 51-65 only cover impl-phase entry): `reviewing` requires `.factory/verify.json` ok + `tests.json` present; `functional-check` requires all three `reviews/*.json`; `pr-ready` reachable only via `pr_ready.py`.

## B. Plan structure & visibility (gap 2)

- **`forge_cli/plans.py` `plan save`** (lines 64-71): extend the generated frontmatter to `issue, title, status, saved, story, decisions_reviewed`. `--story <key>` must match a `plans/roadmap.json` item (fail otherwise).
- **New `./forge plan list`** (in `forge_cli/plans.py`): one table — active/completed plans joined with roadmap item status and `stages.json` progress (`done/total stages`). This is the "what's implemented vs pending" view; no generated index file (glob + roadmap.json stays the source of truth).
- `session_start.py`: include active plan path + story key in injected context.

## C. Contradiction gate at plan save (gap 3)

In `forge_cli/plans.py` `plan save` (alongside the existing `require_grill()` call at lines 16-81):
- Refuse save while any **open `contradiction` signal** exists in `.factory/signals.jsonl` (reuse `open_signals()` from `forge_cli/signal.py:37-40`).
- Require frontmatter `decisions_reviewed:` to list **every currently-active decision id** (reuse the active-list logic from `forge_cli/decisions.py`). Unknown or superseded ids → refuse. This forces the planner to load decisions; a genuine conflict resolves via `./forge decision new <slug> --supersedes <old>` or a raised contradiction signal — never silent divergence.
- Add a contradiction lens question to the grill prompt in `factory/prompts/` (prompt text only, no schema change).

## D. Prototype→specs→roadmap (new flow)

- **New `docs/specs/`** + `./forge spec save <slug> --from <draft.md>` (new `forge_cli/specs.py`, modeled on `plan save`): prepends frontmatter `{slug, title, status: draft|confirmed, saved}`. `./forge spec confirm <slug>` flips status — **and requires a fresh, passing grill bound to that spec** (reuse `require_grill()` from `factory_lib.py:199-254`, same machinery as plan save / sign-off). Saving drafts is friction-free; *confirming* one forces the think-aloud interrogation. `docs/` is already edit-allowlisted, so spec capture during prototyping stays free.
- **`./forge roadmap derive --input <roadmap.json>`** (extend `forge_cli/roadmap.py`): validates agent-generated epics/stories against `factory/schemas/roadmap.json` (extend schema: each story gets a required `spec` field referencing an existing `docs/specs/<slug>.md`) and writes `plans/roadmap.json`. Devs review the derived roadmap; they never author it.
- **`record_signoff.py` gate** (add beside the existing grill check, lines 32-36): refuse sign-off unless (a) ≥1 spec exists and **none are still `draft`**, (b) `plans/roadmap.json` has ≥1 story, (c) every confirmed spec is referenced by ≥1 story. Message lists exactly what's missing.
- Post-sign-off loop is unchanged: `intake.py` per story → plan (with `--story` link from B) → ship → next.
- Update the Phase Contract in `WORKFLOW.md` + `AGENTS.md` (mind the 110-line cap): 0b becomes "prototype freely; save specs as capabilities emerge"; new step 0c "derive roadmap from specs"; step 1 sign-off now requires the spec/roadmap gate.

## F. Lifecycle board — local webapp

Devs can't see at a glance what's generated vs pending, or which stories are plannable in parallel. Add a read-only local dashboard over the existing ledgers — no new state, no framework, no build step.

- **`./forge board`** (new `forge_cli/board.py`): starts a Python-stdlib `http.server` on localhost (default port, `--port` flag) and opens the browser. Two routes:
  - `/` — one static HTML file (`factory/board/index.html`, plain HTML+JS, polls the API every few seconds).
  - `/api/state` — aggregates, per request: `docs/specs/` frontmatter (draft/confirmed), `plans/roadmap.json` epics/stories with `status` + `depends_on`, the **parallel frontier** (reuse the ready-set logic behind `./forge roadmap parallel` in `forge_cli/roadmap.py` — stories whose deps are all done), `plans/active|completed/` plan files, `.factory/run.json` phase, `.factory/stages.json` per-stage status, open signals, open quickfix.
- **View**: one page, lifecycle columns per story — spec → roadmap → planned → stages (n/m done) → verify/tests/reviews → shipped — plus a "ready to plan in parallel" highlight on frontier stories. Read-only; actions stay in the CLI.
- **UI is designed with the `frontend-design` skill** (invoke it when building `index.html`): intentional visual direction, not templated defaults — still a single self-contained HTML file (inline CSS/JS, no build step).
- `# ponytail: stdlib server + polling, no websockets/framework — upgrade only if multiple simultaneous viewers ever matter.`

## E. In-repo project memory (gap 5)

- **New `docs/memory/`**: `MEMORY.md` index + one file per fact (same frontmatter format as Claude auto-memory so habits transfer).
- `session_start.py`: inject `docs/memory/MEMORY.md` contents into `additionalContext`.
- `.claude/CLAUDE.md`: add ground rule — project facts are written to `docs/memory/` (cite decision 0012); user-level auto-memory is for personal preferences only.

## Cross-cutting

- **Windows compatibility**: all new/changed code is pure Python stdlib and OS-neutral — `pathlib` for every path (no hardcoded `/`, no symlinks/chmod), `webbrowser.open()` + `http.server` for the board (both work on Windows), CRLF-tolerant file reads, no `os.fork`/POSIX signals. The existing `./forge` shim already falls back to `py -3` (Git Bash / WSL); new subcommands must also run via plain `python factory/scripts/forge.py <cmd>` on native Windows shells (cmd/PowerShell).
- **Vendor integrity**: `pr_ready.py` checks the gate surface against `constitution/VENDOR_MANIFEST.json` (lines 134-146) — update the manifest for every touched gate script.
- **Decision records**: record three new decisions via `./forge decision new`: always-armed lock + quickfix, plan-save contradiction gate, specs-before-signoff.
- **First implementation step**: save this design as `docs/superpowers/specs/2026-07-24-workflow-enforcement-design.md` (brainstorming-skill convention) and commit it.

## Files touched (core)

- `factory/scripts/pre_tool_use.py`, `update_run.py`, `record_signoff.py`, `session_start.py`, `forge.py`
- `forge_cli/plans.py`, `roadmap.py`, new `quickfix.py`, new `specs.py`, new `board.py` + `factory/board/index.html`
- `factory/schemas/roadmap.json`, `factory/prompts/` (grill prompt)
- `constitution/VENDOR_MANIFEST.json`, `WORKFLOW.md`, `AGENTS.md`, `.claude/CLAUDE.md`, `docs/decisions/` (+3), new `docs/specs/`, `docs/memory/`
- `plans/quickfixes.jsonl` (ledger, created on first use)

## Verification

1. **Hook simulation** (no harness needed — hooks read stdin JSON): pipe crafted PreToolUse payloads into `pre_tool_use.py` and assert deny/allow: locked Edit to `src/x` → deny; same in plan mode → allow; Bash `cat > src/x` while locked → deny; `echo hi > /tmp/x` → allow; edit under `docs/` → allow.
2. **Quickfix lifecycle**: `./forge quickfix start "test"` → product edit allowed → 6th distinct file → deny → `./forge quickfix done` → ledger entry exists, lock re-armed.
3. **Sign-off gate**: with a draft spec / empty roadmap, `record_signoff.py` refuses with the exact missing list; `./forge spec confirm` without a fresh grill → refused; after grilled `spec confirm` + `roadmap derive`, sign-off passes.
4. **Plan save**: missing/incomplete `decisions_reviewed` → refused; open contradiction signal → refused; complete → saved with new frontmatter; `./forge plan list` shows it.
5. **Ordering**: `update_run.py --phase reviewing` without `verify.json` → refused.
6. **Board**: `./forge board` serves; `/api/state` returns specs, stories, frontier, stages matching the ledger files; page renders lifecycle columns and highlights parallel-ready stories; edits to a ledger file appear on next poll.
7. `python3 factory/scripts/check_dual_runtime.py` stays green; `./forge next` still renders sensibly at each phase.
8. **Windows sanity**: grep new/changed files for POSIX-only APIs (`os.fork`, `os.symlink`, `chmod`, hardcoded `/tmp`, shell-outs to `sh`); confirm every new forge subcommand is reachable via `python factory/scripts/forge.py <cmd>` without the sh shim.
