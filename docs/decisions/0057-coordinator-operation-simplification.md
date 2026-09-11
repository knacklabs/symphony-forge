---
status: accepted
confirmed_by: "User (Codex conversation)"
date: 2026-09-08
stories: [FORGE-COORD-1]
---

# Simplify coordinator operation without removing workflow gates

## Context
The user explicitly selected synchronous-only certification, a reviewed one-criterion roadmap edit, and removal of the three shipped Codex subagent configurations. The user also requires all task work to pause after a question until the actual answer. These choices simplify operation without removing planning or proof requirements.

## Decision
Keep synchronous completed question events as the certifying path. Ask all questions through the host's permitted question tools, show the exact artifact revision, and pause all task work while an issued question is unanswered. Resume automatically after the answer and required recorder checks; cancellation and timeout grant no approval.

After the existing epics grill and human approval, apply the approved FORGE-COORD-1 AC3 amendment as a deliberate reviewed edit. Verify that no other roadmap field or order changes. This supersedes this story spec's import-only procedure: the current importer rejects legacy rows and renumbers entries, so it cannot preserve the approved boundary. Do not add a new amendment command for this repair.

Remove only the three shipped `.codex/agents/planner-high.toml`, `.codex/agents/docs-decomposer.toml`, and `.codex/agents/functional-checker.toml` definitions and their obsolete delivery/checker requirements. Preserve the planning, decomposition and functional-check phase contracts and evidence producer identities; a logical workflow role does not require a custom-agent TOML file. Existing Forge launchers and harness model/reasoning policy remain authoritative. Preserve client-owned agent additions and Claude's companion route.

## Consequences
Update the bounded parity task scope and delivery tests before implementation; the configuration removal is not permission to bypass delegation, task approval, verification, autoreview or shipping gates. Existing approved decisions remain in force. The main conversation owns user interaction; helpers return results there. These explicit user choices do not create a new evidence system, async certifying producer or coordinator framework.
