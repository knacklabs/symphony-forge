#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

from factory_lib import (
    client_signoff, load_json, read_hook_input, repo_root, run_state_path,
)
from forge_cli.quickfix import claim_files, load_active, record_files
from forge_cli.repo_kind import is_harness_source_repo

payload = read_hook_input()
tool_name = payload.get("tool_name", "")
tool_input = payload.get("tool_input") or {}
command = (tool_input.get("command") or "").strip()
permission_mode = payload.get("permission_mode", "")


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    raise SystemExit(0)


# Planning lock: product writes are always refused until a plan is approved
# or a bounded quickfix is open. Planning surfaces stay available.
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
PLANNING_WRITE_OK = (
    "plans/", "docs/", ".gstack/", ".github/", "prototype/",
)
CLIENT_MACHINERY_WRITE_OK = (
    "factory/", "constitution/", "harness/", ".claude/", ".codex/",
)
# .factory/ is deliberately NOT writable by hand: run.json holds plan_status,
# so a hand-edit disarms this very lock, and AGENTS.md already requires that
# evidence enter .factory/ only through the record_* scripts. Those scripts
# write it as themselves — this guard classifies tool-call targets, not what a
# sanctioned script does internally. The scratchpad is the one freely
# hand-written file there (`forge note`); the repo-kind marker also lives there
# but is planning-locked, not free (see FACTORY_STATE_WRITABLE).
FACTORY_STATE_MSG = (
    ".factory/ is recorded state, never hand-written (AGENTS.md): run.json "
    "carries plan_status, so editing it disarms the planning lock. Use the "
    "record_* scripts, `./forge note` for the scratchpad, or `./forge stage` "
    "for stage status."
)
PLANNING_WRITE_OK_FILES = {
    "AGENTS.md", "CLAUDE.md", "WORKFLOW.md", "harness.yaml", "README.md",
    ".gitignore", ".gitattributes", ".envrc",
    # session memory, not evidence — gitignored, and `forge note` appends to it
    ".factory/scratchpad.md",
}
# Files under .factory/ the evidence guard lets through — but that is the ONLY
# guard they skip. The scratchpad is also freely writable (PLANNING_WRITE_OK_FILES
# above). The repo-kind marker is deliberately NOT there: it is a product path,
# so the planning lock governs it — creating, editing, or DELETING it needs an
# approved plan or a quickfix. Disarming the source-repo lock therefore takes the
# same ceremony as any machinery change, never a silent hand-edit or `rm`.
FACTORY_STATE_WRITABLE = {
    ".factory/scratchpad.md",
    ".factory/harness-source.json",
}
# The repo-kind marker. It decides whether the machinery trees are product at
# all, so it may be changed ONLY under an approved plan + decomposition, never a
# quickfix: a quickfix that could `rm` it as its first claimed file would flip
# the repo to client-mode and let every later machinery write skip the budget
# entirely (defeating the very bound it exists to enforce). Under an approved
# plan the machinery is already writable, so removing the marker grants nothing.
HARNESS_SOURCE_MARKER = ".factory/harness-source.json"
PLAN_MODE_MSG = (
    "Planning lock is armed — product writes require an approved plan. "
    "Either enter plan mode (shift+tab) [PLAN MODE] and save the approved plan per "
    "factory/prompts/planner.md, or run `./forge quickfix start \"<reason>\"` "
    "for a bounded five-file fix."
)
QUICKFIX_LIMIT_MSG = (
    "Quickfix scope exceeded — this is not a quickfix, enter plan mode (shift+tab). "
    "The other planning-lock exit is `./forge quickfix start \"<reason>\"`, but the "
    "current window must be closed first."
)
MARKER_PLAN_ONLY_MSG = (
    f"{HARNESS_SOURCE_MARKER} is the repo-kind marker: it may be created, edited, "
    "or deleted ONLY under an approved plan with a recorded decomposition, never a "
    "quickfix. A quickfix that removed it could flip this repo to client-mode and "
    "escape its own file budget. Plan the change, or leave the marker alone."
)
OPAQUE_WRITE_MSG = (
    "Opaque delegated writes cannot use a quickfix because its five-file budget "
    "cannot be tracked. Either enter plan mode (shift+tab) [PLAN MODE] and save an "
    "approved plan, or use `./forge quickfix start \"<reason>\"` for direct edits "
    "whose product paths the hook can record."
)


def product_path(raw: str, root: Path) -> str | None:
    """Return a canonical repo-relative product path, otherwise None."""
    value = raw.strip().strip("\"'")
    if not value or value in {"-", "/dev/null"}:
        return None
    # Unexpanded shell expansions ($HOME, $(pwd), backticks) cannot be
    # classified — the hook sees the literal, not the destination. Treat as
    # unknown rather than product: this guard defends drift, and a drifting
    # worker writes plain paths (decision 0013; artifact gates backstop).
    if "$" in value or "`" in value:
        return None
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        rel = resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
    if not rel or rel in PLANNING_WRITE_OK_FILES:
        return None
    exempt_prefixes = PLANNING_WRITE_OK
    if not is_harness_source_repo(root):
        exempt_prefixes += CLIENT_MACHINERY_WRITE_OK
    if any(rel == prefix.rstrip("/") or rel.startswith(prefix)
           for prefix in exempt_prefixes):
        return None
    return rel


def tokenize(segment: str) -> list[str] | None:
    """Shell tokens, or None when the segment cannot be parsed at all.

    Non-posix mode is the fallback because it survives the apostrophe in a
    heredoc body (`cat > src/app.ts <<'EOF'\\nit's fine`) that posix mode
    rejects — losing that would blind the guard to a real product write.
    """
    for posix in (True, False):
        try:
            return shlex.split(segment, posix=posix)
        except ValueError:
            continue
    return None


HEREDOC_START = re.compile(r"<<-?\s*[\"']?(\w+)[\"']?")


def strip_heredoc_bodies(value: str) -> str:
    """Drop heredoc BODIES, keep the command lines that open them.

    `cat > src/app.ts <<'EOF'` is a product write and must still be seen; the
    body is data — prose there ("changed a > b", "sed -i") is not a command.
    """
    lines = value.splitlines()
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        match = HEREDOC_START.search(line)
        index += 1
        if not match:
            continue
        terminator = match.group(1)
        while index < len(lines) and lines[index].strip() != terminator:
            index += 1
        index += 1  # skip the terminator itself
    return "\n".join(kept)


def redirect_targets(tokens: list[str]) -> list[str]:
    """Write targets of unquoted > / >> operators.

    Token-level so a redirect character INSIDE a quoted argument
    (git commit -m 'a > b') is text, not a redirect.
    """
    targets: list[str] = []
    for index, token in enumerate(tokens):
        if token in {">", ">>"}:
            if index + 1 < len(tokens):
                targets.append(tokens[index + 1])
        elif token.startswith(">") and token.lstrip(">"):
            targets.append(token.lstrip(">"))
    return targets


def in_factory_state(raw: str, root: Path) -> bool:
    """True when a write target lands in protected .factory/ state."""
    value = raw.strip().strip("\"'")
    if not value or "$" in value or "`" in value:
        return False
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        rel = candidate.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return False
    # `.factory` (the directory itself, e.g. `rm -rf .factory`) is protected too:
    # deleting it wipes recorded state and the repo-kind marker in one stroke.
    if rel == ".factory":
        return True
    return rel.startswith(".factory/") and rel not in FACTORY_STATE_WRITABLE


# git global options that consume a following token as their value; the real
# subcommand is the first bare token once these (and plain flags) are skipped.
GIT_VALUE_OPTS = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace",
    "--super-prefix", "--config-env",
}


def git_subcommand(args: list[str]) -> tuple[str | None, list[str], str]:
    """(subcommand, subcommand args, `-C` cwd prefix), skipping global options.

    `-C <dir>` changes the directory git resolves paths against (cumulative when
    repeated), so its value is captured and later joined onto the operands —
    otherwise `git -C .factory rm harness-source.json` would resolve against the
    repo root and miss the marker. Other value-taking global options are skipped.
    """
    index = 0
    cwd_parts: list[str] = []
    while index < len(args):
        token = args[index]
        if token == "-C" and index + 1 < len(args):
            cwd_parts.append(args[index + 1])
            index += 2
            continue
        if token in GIT_VALUE_OPTS:
            index += 2  # option plus its separate value
            continue
        if token.startswith("-"):
            index += 1  # a flag, or --opt=value carrying its own value
            continue
        return token, args[index + 1:], "/".join(cwd_parts)
    return None, [], "/".join(cwd_parts)


def bash_write_paths(value: str) -> list[str]:
    """Extract likely write targets from a shell command.

    # ponytail: heuristic, defends drift not adversaries — tighten patterns
    # if a real bypass shows up.
    """
    found: list[str] = []
    # Newlines separate commands too: without them a multi-line script is one
    # segment, and an earlier command's operand list swallows later lines.
    for segment in re.split(r"[;&|\n]+", strip_heredoc_bodies(value)):
        tokens = tokenize(segment)
        if tokens is None:
            continue
        found.extend(redirect_targets(tokens))
        # Command POSITION only (after env-var prefixes) — the same discipline
        # the codex-exec guard uses. Otherwise prose that merely mentions a
        # tool ("...sed -i, cp, mv...") is parsed as an invocation.
        command_index = next(
            (index for index, token in enumerate(tokens)
             if not re.fullmatch(r"\w+=\S*", token)),
            None,
        )
        if command_index is None:
            continue
        command_name = tokens[command_index].rsplit("/", 1)[-1]
        if command_name not in {"tee", "sed", "cp", "mv", "touch", "rm",
                                "unlink", "git"}:
            continue
        args = tokens[command_index + 1:]
        operands = [token for token in args
                    if not token.startswith("-") and token not in {">", ">>"}]
        if command_name == "tee":
            found.extend(operands)
        elif command_name == "touch":
            found.extend(operands)
        elif command_name in {"rm", "unlink"}:
            # Deleting a product path disarms as surely as writing one: removing
            # the repo-kind marker would silently flip source->client and unlock
            # all machinery. Every operand is a target.
            found.extend(operands)
        elif command_name == "git":
            # `git rm` / `git mv` delete or relocate tracked files just like their
            # shell namesakes — catch the marker (and any product path) going out
            # the git side door too. Skip git's global options (and their values,
            # e.g. `-C <dir>`, `-c <k=v>`) to find the real subcommand, so
            # `git -C . rm <marker>` is not a bypass. Other subcommands that can
            # also drop a file (checkout, reset, restore, clean, stash), and a
            # `-C <dir>` that relocates path resolution, are arbitrary VCS ops
            # beyond this drift heuristic: git keeps them visible and the artifact
            # gates backstop (decision 0013 — this defends drift, not an adversary).
            sub, sub_args, cwd = git_subcommand(args)
            if sub in {"rm", "mv"}:
                for token in sub_args:
                    if token.startswith("-") or token in {">", ">>"}:
                        continue
                    # Resolve the operand against git's -C directory so the true
                    # target (not a root-relative mis-read) is classified.
                    found.append(token if Path(token).is_absolute() or not cwd
                                 else f"{cwd}/{token}")
        elif command_name == "cp" and operands:
            found.append(operands[-1])
        elif command_name == "mv":
            found.extend(operands)
        elif command_name == "sed" and any(
            token == "-i" or token.startswith("-i") or token.startswith("--in-place")
            for token in args
        ) and operands:
            found.append(operands[-1])
    return found


def _contains_marker(rel: str) -> bool:
    """True when rel IS the repo-kind marker or a directory that contains it.

    An ancestor delete (`rm -rf .factory`, or the repo root) removes the marker
    just as surely as deleting it by name, so it must be gated the same way.
    """
    if rel in ("", ".", HARNESS_SOURCE_MARKER):
        return True
    return HARNESS_SOURCE_MARKER.startswith(rel.rstrip("/") + "/")


def guard_product_writes(targets: list[str], state: dict, root: Path) -> None:
    product = list(dict.fromkeys(
        rel for raw in targets if (rel := product_path(raw, root)) is not None
    ))
    if not product:
        return
    approved_and_decomposed = (state.get("plan_status") == "approved"
                               and state.get("decomposition_status") == "recorded")
    if (any(_contains_marker(rel) for rel in product)
            and not approved_and_decomposed):
        # A quickfix must never be able to touch the marker (see its definition):
        # deleting it — directly, or by removing an ANCESTOR like `.factory` via
        # `rm -rf .factory` — would disable classification and the budget with it.
        # Only an approved, decomposed plan authorizes a marker change.
        deny(MARKER_PLAN_ONLY_MSG)
    if (state.get("plan_status") == "approved"
            and state.get("decomposition_status") == "recorded"):
        # The plan already authorizes this write. Recording only observes it:
        # it neither applies the quickfix budget nor changes the return below.
        record_files(root, product)
    if state.get("plan_status") == "approved":
        # An approved plan is not yet an implementation licence: the bounded
        # tasks are what implementation is measured against, and a write before
        # the decomposition exists belongs to no task (AGENTS.md phase 4).
        if state.get("decomposition_status") == "recorded":
            return
        if not load_active(root):
            deny(
                "Plan approved, but no decomposition is recorded — implementation "
                "is bounded by tasks, so a product write now belongs to no task. "
                "Record it: python3 factory/scripts/record_decomposition_from_json.py "
                "--input /tmp/decomposition.json (or open a bounded window: "
                "./forge quickfix start \"<reason>\")."
            )
    # An open window does not skip this: each product file it touches must be
    # claimed against the budget, which is what bounds the escape hatch.
    quickfix = load_active(root)
    if not quickfix:
        deny(PLAN_MODE_MSG)
    claimed, _ = claim_files(root, product)
    if not claimed:
        deny(QUICKFIX_LIMIT_MSG)


blocked = [
    r"\brm\s+-rf\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+push\s+--force\b",
    r"\bterraform\s+destroy\b",
    r"\bkubectl\s+delete\b",
]
for pattern in blocked:
    if re.search(pattern, command):
        deny(f"Blocked by factory policy: {command}")

# Raw `codex exec` bypasses the sanctioned runtime (/codex:rescue -> the
# plugin companion): no session threading, no background management, no
# repo-pinned invocation shape. There is NO escape hatch — doctor installs
# codex-plugin-cc as a required tool; if it breaks, repair it or work in a
# Codex session directly (docs/degraded-mode.md).
# Match INVOCATIONS (command position, env prefixes, pipeline segments,
# command substitution) — not prose in heredocs/echo that mentions the phrase.
# `codex [global flags] exec` counts too — flags between must not bypass.
CODEX_EXEC_INVOCATION = re.compile(
    r"(?:^|[;&|]\s*|\$\(\s*)(?:\w+=\S+\s+)*codex(?:\s+-{1,2}[\w-]+(?:[= ]\S+)?)*\s+exec\b",
    re.MULTILINE,
)
if CODEX_EXEC_INVOCATION.search(command):
    deny(
        "Direct `codex exec` is off-contract — invoke Codex through the plugin: "
        "/codex:rescue [--background] [--write] [--model <m>] [--effort <e>] \"<task>\" "
        "(read-only unless --write). Plugin missing or broken? `./forge doctor --fix` "
        "reinstalls it; meanwhile work in a Codex session directly "
        "(docs/degraded-mode.md) — same prompts, same artifacts, same gates."
    )

check_bypass = ["pnpm test", "pnpm lint", "pnpm typecheck", "pnpm check:all"]
if any(token in command for token in check_bypass) and "factory/scripts/verify.py" not in command:
    deny(
        "Use `python3 factory/scripts/verify.py` so verification artifacts stay deterministic."
    )

# Sign-off gate: heavy factory phases cannot start before client sign-off.
# Discovery/prototype phases and record_signoff.py itself stay allowed.
PHASE_ADVANCING = (
    "record_decomposition_from_json.py",
    "pr_ready.py",
)
GATED_PHASES = (
    "planning",
    "decomposing",
    "awaiting-approval",
    "implementing",
    "testing",
    "reviewing",
    "functional-check",
    "pr-ready",
)
root = repo_root()
run_state = load_json(run_state_path(root), default={})

edit_target = (tool_input.get("file_path") or tool_input.get("notebook_path") or "")
write_targets = [edit_target] if tool_name in EDIT_TOOLS and edit_target else []
if tool_name == "Bash":
    write_targets = bash_write_paths(command)

# Recorded state is never hand-written, in any mode and at any plan status.
for candidate in write_targets:
    if in_factory_state(candidate, root):
        deny(FACTORY_STATE_MSG)

# The lock covers plan mode too: plan mode stops the Edit tools, not a Bash
# redirect, and writing product code while planning is the thing being stopped.
if permission_mode != "plan" or tool_name == "Bash":
    guard_product_writes(write_targets, run_state, root)
literal_command = command.replace("''", "").replace('""', "")
shell_shape = re.sub(
    r"\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*", "", literal_command)
try:
    shell_tokens = shlex.split(command)
except ValueError:
    if (
        tool_name == "Bash"
        and (
            "--write" in shell_shape
            or
            re.search(r"\bcodex-companion(?:\.mjs)?\b", shell_shape)
        )
    ):
        deny("Bash command could not be safely parsed, so Forge cannot verify "
             "that it respects the delegation and planning boundaries. Use "
             "`./forge delegate <task-id>` for a companion launch.")
    shell_tokens = []
compact_command = re.sub(r"[^a-z0-9]", "", shell_shape.lower())
has_companion = (
    re.search(r"\bcodex-companion(?:\.mjs)?\b", shell_shape) is not None
    or any(re.fullmatch(r"codex-companion(?:\.mjs)?", Path(token).name)
           for token in shell_tokens)
    or "codexcompanion" in compact_command
)
# Read-only companion runs are the /codex:rescue exploration lane and
# pass. Only write launches must route through the canonical executor,
# which owns the argv and records evidence `forge stage done` can verify.
COMPANION_WRITE_FLAGS = {
    "--write", "--full-auto", "--dangerously-bypass-approvals-and-sandbox",
}
has_companion_write = (
    any(token in COMPANION_WRITE_FLAGS for token in shell_tokens)
    or "--write" in shell_shape
)
if tool_name == "Bash" and has_companion and has_companion_write:
    deny("Companion write launches are off-contract. Use "
         "`./forge delegate <task-id>`; it owns the argv launch and records "
         "evidence that `forge stage done` can verify. Read-only companion "
         "runs (/codex:rescue exploration) are allowed.")

if run_state and not client_signoff(root)[0]:
    advancing = any(script in command for script in PHASE_ADVANCING)
    if "update_run.py" in command and "--phase" in command:
        advancing = advancing or any(phase in command for phase in GATED_PHASES)
    if advancing:
        deny(
            "Client sign-off not recorded. Get docs/decisions/NNNN-client-signoff.md "
            "accepted (non-empty confirmed_by), then run "
            "`python3 factory/scripts/record_signoff.py` before advancing the phase."
        )

print(json.dumps({}))
