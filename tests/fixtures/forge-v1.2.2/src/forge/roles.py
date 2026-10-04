"""Forge's subagent roles for both hosts, each on the model and effort forge.toml gives its kind.

A role whose kind's model belongs to the other family leaves the model out on that host, so the
role runs on the session's model. Roles set no tools or permission mode: they inherit the session's.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from forge import repo

REFUSALS = {
    "foreign_role": ("{path} is a role of your own that Forge didn't write, and forge sync writes a "
                     "role of that name; rename or delete your file, then sync again.", "forge sync"),
}

MARK = "Forge writes this role with forge sync from forge.toml's [models]; change forge.toml, not this file."
BUILD = ("Build the bounded task you were handed, in this checkout and nothing more. Follow the repo's "
         "AGENTS.md rules and the standards page. Write the end-to-end test first and watch it fail, "
         "then take the smallest change that makes it pass. A file outside the task's Scope that the "
         "change needs you may change; name it and why in your handoff. Stop only for a one-way step, "
         "a security question or a new moving part. Run tests in the foreground, commit your own work "
         "with a short plain-English message, and never commit to the default branch, skip the git "
         "hooks, push or merge.")
READ_ONLY = ("Change no files: report what you found with exact paths, symbols and evidence, and "
             "leave the change to a building role.")
# role: (kind, description, instructions)
ROLES = {
    "worker": ("build", "Builds a bounded Forge task or fix end to end.", BUILD),
    "coder": ("build", "Builds server-side APIs, data and business logic for a bounded task.",
              BUILD + " Trace every caller of what you change and keep validation and error handling."),
    "frontend": ("build", "Builds frontend screens and interaction for a bounded task.",
                 BUILD + " Keep keyboard access, labels and contrast, and handle loading, error and "
                         "empty states."),
    "tester": ("build", "Writes and fixes automated tests for a bounded task.",
               BUILD + " Test behaviour at the boundary the user touches, never internals, and never "
                       "weaken a test to hide a defect."),
    "refactorer": ("build", "Makes behaviour-preserving refactors for a bounded task.",
                   BUILD + " Keep behaviour and validation exactly as they are; the existing tests "
                           "must pass unchanged."),
    "explorer": ("lite", "Explores the codebase and traces dependencies without changing files.",
                 "Answer the question you were handed by reading the repo. " + READ_ONLY),
    "planner": ("design", "Turns an approved story into bounded tasks with their tests.",
                "Split the approved story into the fewest tasks that each prove Done-when items end "
                "to end, naming each task's Scope and tests. Plan in plain English. " + READ_ONLY),
    "architect": ("design", "Weighs design choices against the repo's decisions and standards.",
                  "Give one recommendation, its reason and how sure you are, choosing the fewest "
                  "moving parts that meet Done-when, and name any new moving part. " + READ_ONLY),
    "debugger": ("review", "Finds the root cause of a hard failure.",
                 "Reproduce the failure, then trace it to a confirmed root cause and the smallest "
                 "fix, with the test that would fail without it. " + READ_ONLY),
    "security": ("review", "Checks trust boundaries, validation, permissions and secrets.",
                 "Check where input enters, that every data access checks permission, and that "
                 "secrets and personal data stay out of code and logs; state the evidence and the "
                 "smallest safe change. " + READ_ONLY),
    "performance": ("review", "Measures performance problems and finds the smallest fix.",
                    "Measure before you claim, find the cause, and propose the smallest correct "
                    "change with the measurement that proves it. " + READ_ONLY),
}


def _family(model: str) -> str:
    return "claude" if re.match(r"claude|opus|sonnet|haiku|fable", model) else "codex"


def _chosen(cfg: dict[str, Any], kind: str, family: str) -> tuple[str, str]:
    """(model, effort) for a role on this host; "" leaves it out so the session's own applies."""
    models = cfg.get("models", {})
    # A kind with no entry for this family gets none: the role inherits the session's settings.
    entry = models.get(kind, {})
    if kind == "design":
        entry = entry.get(family, {})
    model, effort = entry.get("model", ""), entry.get("effort", "")
    if family == "claude" and effort == "ultra":
        effort = "max"
    # A design entry is already the host's own; other kinds name one model for both hosts.
    return (model if model and (kind == "design" or _family(model) == family) else ""), effort


def ships(top: Path, cfg: dict[str, Any]) -> dict[str, str]:
    wanted = {}
    for name, (kind, description, instructions) in ROLES.items():
        model, effort = _chosen(cfg, kind, "codex")
        wanted[f".codex/agents/{name}.toml"] = "".join([
            f"# {MARK}\n", f"name = {json.dumps(name)}\n", f"description = {json.dumps(description)}\n",
            f"model = {json.dumps(model)}\n" * bool(model),
            f"model_reasoning_effort = {json.dumps(effort)}\n" * bool(effort),
            f"developer_instructions = {json.dumps(instructions)}\n"])
        model, effort = _chosen(cfg, kind, "claude")
        wanted[f".claude/agents/{name}.md"] = "".join([
            f"---\n# {MARK}\n", f"name: {name}\n", f"description: {json.dumps(description)}\n",
            # Quoted, so no value from forge.toml can add a line such as tools to the frontmatter.
            f"model: {json.dumps(model)}\n" * bool(model),
            f"effort: {json.dumps(effort)}\n" * bool(effort),
            f"---\n\n{instructions}\n"])
    return wanted


def refuse_foreign(top: Path, rels: list[str]) -> None:
    """Refuse before sync writes anything when it would overwrite a role file Forge didn't write."""
    for rel in rels:
        path = top / rel
        if rel.startswith((".codex/agents/", ".claude/agents/")) and path.is_file() and MARK not in (
                path.read_text(encoding="utf-8")):
            repo.refuse(REFUSALS["foreign_role"], path=rel)
