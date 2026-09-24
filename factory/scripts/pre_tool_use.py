#!/usr/bin/env python3
"""Classify ordinary shell writes with broad targets and fail-closed Git.
Known writers count non-option operands; sed needs in-place mode and refuses
backup suffixes. Git permits read forms, literal file writes, and only -C
global options. Redirections count targets; interpreters stay unparsed.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    raise SystemExit(0)


EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
PATCH_TOOL = "apply_patch"


def _raw_payload() -> dict:
    try:
        stream = getattr(sys.stdin, "buffer", sys.stdin)
        raw = stream.read()
        value = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _repo_from_cwd() -> Path:
    current = Path.cwd().resolve()
    return next((path for path in (current, *current.parents)
                 if (path / ".git").exists()), current)


def _harness_checkout(path: Path) -> Path | None:
    """Return the nearest harness checkout containing this path."""
    return next((parent for parent in (path, *path.parents)
                 if (parent / ".git").exists()
                 and (parent / "factory" / "scripts").is_dir()), None)


def _cross_worktree_target(raw: str, root: Path) -> bool:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        return False
    try:
        checkout = _harness_checkout(candidate.resolve())
        return checkout is not None and checkout.resolve() != root.resolve()
    except (OSError, RuntimeError):
        return False


def _deny_cross_worktree_targets(paths: list[str], root: Path) -> None:
    if any(_cross_worktree_target(path, root) for path in paths):
        deny("cross-worktree shell write; run it from that worktree")


def _unmerged_paths(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "-u", "-z"], cwd=root, capture_output=True,
        text=True, encoding="utf-8", errors="surrogateescape",
    )
    if result.returncode:
        return set()
    return {
        record.split("\t", 1)[1]
        for record in result.stdout.split("\0")
        if "\t" in record
    }


STATIC_WRITE_EXEMPT_PREFIXES = ("plans/", "docs/", ".gstack/", "prototype/")
STATIC_WRITE_EXEMPT_FILES = {"README.md", ".gitignore", ".gitattributes", ".envrc"}

def _static_locked(raw: str, root: Path) -> bool:
    value = raw.strip().strip("\"'")
    if not value or "$" in value or "`" in value:
        return True
    candidate = Path(value)
    try:
        rel = (candidate if candidate.is_absolute() else root / candidate) \
            .resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return False
    if rel in STATIC_WRITE_EXEMPT_FILES or any(
            rel == prefix.rstrip("/") or rel.startswith(prefix)
            for prefix in STATIC_WRITE_EXEMPT_PREFIXES):
        return False
    return not _ignored_and_untracked(rel, root)


def _ignored_and_untracked(rel: str, root: Path) -> bool:
    """A path git ignores AND does not track is not product or canon.

    The exemption list named `.envrc` but not `.env`, so editing local service
    config to run verify was refused as a product write. Enumerating filenames
    always misses one; the question is what the file IS. Git already answers
    it, and the answer costs nothing on the common path because this is only
    consulted for a path that would otherwise be refused.

    BOTH conditions matter. A tracked file stays guarded even if someone adds
    it to .gitignore, so the lock cannot be lifted off product by editing an
    ignore rule.
    """
    try:
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "--", rel], cwd=root,
            capture_output=True, timeout=5)
        if ignored.returncode != 0:
            return False
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", rel], cwd=root,
            capture_output=True, timeout=5)
        return tracked.returncode != 0
    except (OSError, subprocess.SubprocessError):
        return False   # cannot tell: keep the lock on


def _fallback_readonly(command: str) -> bool:
    if "$" in command or "`" in command or re.search(r"[<>]", command):
        return False
    for segment in re.split(r"&&|\|\||[;|\n]", command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            return False
        while tokens and re.fullmatch(r"\w+=\S*", tokens[0]):
            tokens.pop(0)
        if not tokens:
            continue
        name = tokens[0].rsplit("/", 1)[-1]
        if name == "git":
            verb = next((token for token in tokens[1:] if not token.startswith("-")), "")
            if any(token.startswith("--output") for token in tokens[1:]) or verb not in {
                "status", "diff", "show", "log", "ls-files", "rev-parse"}:
                return False
        elif name not in {"pwd", "ls", "rg", "grep", "cat", "head", "tail", "wc", "diff", "stat", "file"}:
            return False
    return True


def denylist_fallback(payload: dict, reason: str) -> None:
    root = _repo_from_cwd()
    command = ((payload.get("tool_input") or {}).get("command") or "").strip()
    tool = payload.get("tool_name", "")
    target = ((payload.get("tool_input") or {}).get("file_path") or
              (payload.get("tool_input") or {}).get("notebook_path") or "")
    if tool == PATCH_TOOL:
        deny("Forge emergency deny-list engaged; apply_patch writes cannot be "
             "classified while the full policy is unavailable.")
    if (tool in EDIT_TOOLS and _static_locked(target, root)) or (
        tool == "Bash" and not _fallback_readonly(command)
    ):
        deny(f"Forge emergency deny-list engaged ({reason}); product and canon writes stay locked.")
    print(json.dumps({}))
    raise SystemExit(0)


payload = _raw_payload()
try:
    from factory_lib import (
        client_signoff, load_json, repo_root, run_state_path,
    )
    from forge_cli.context import context_files, context_paths, scan_inbox
    from forge_cli.codex_runtime import coordinator_runtime
    from forge_cli.quickfix import DEGRADED, claim_files, load_active, profile_of
    from forge_cli.repo_kind import (
        CLIENT_MACHINERY_PREFIXES, ORCHESTRATION_FILES,
        ORCHESTRATION_PREFIXES, is_harness_source_repo, locked_repo_path,
    )
except (ImportError, SyntaxError) as exc:
    denylist_fallback(payload, type(exc).__name__)

tool_name = payload.get("tool_name", "")
tool_input = payload.get("tool_input") or {}
command = (tool_input.get("command") or "").strip()
permission_mode = payload.get("permission_mode", "")
native_codex = coordinator_runtime() == "codex"


# ---------------------------------------------------------------- ask gate --
# One of the two ways to interrupt the human. The rule itself lives in
# factory_lib.may_interrupt so this and the Stop hook cannot drift apart.
if not native_codex and tool_name == "request_user_input_async":
    deny("Asynchronous questions are optional clarification only and cannot "
         "satisfy a required exchange, gate, or approval.")
if not native_codex and tool_name in {"request_user_input", "AskUserQuestion"}:
    try:
        from factory_lib import may_interrupt
        allowed, reason = may_interrupt(Path.cwd(), spend=True)
        if not allowed:
            deny(reason)
    except SystemExit:
        raise
    except Exception:
        pass


# Session lock: product and canon writes are always refused unless a bounded
# degraded window is open. Orchestration surfaces stay available.
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
# Files under .factory/ the evidence guard lets through — but that is the ONLY
# guard they skip. The scratchpad is also exempt in the shared locked-path
# classifier. The repo-kind marker is deliberately NOT there: it is a product path,
# so the session lock governs it. Changing source-repo classification therefore
# requires a protected delegated worker whose scope names the marker.
FACTORY_STATE_WRITABLE = {
    ".factory/scratchpad.md",
    ".factory/harness-source.json",
}
# The repo-kind marker. It decides whether the machinery trees are product at
# all, so a session may never change it, including during degraded mode: a
# window that could `rm` it as its first claim would flip the repo to client-mode
# and let every later machinery write skip the budget entirely.
HARNESS_SOURCE_MARKER = ".factory/harness-source.json"
PLAN_MODE_MSG = (
    "Session write lockout is armed — product and canon writes must run through "
    "`./forge delegate <task-id>`. If the companion is unavailable, open the sole "
    "bounded exception with `./forge mode degraded start --reason \"<reason>\"`."
)
QUICKFIX_LIMIT_MSG = (
    "Degraded window scope exceeded — its five-file claim budget is exhausted. "
    "Close it with `./forge mode done`, restore the companion, and use "
    "`./forge delegate <task-id>` for the remaining write work."
)
MARKER_PLAN_ONLY_MSG = (
    f"{HARNESS_SOURCE_MARKER} is the repo-kind marker: it may be created, edited, "
    "or deleted only through `./forge delegate <task-id>`, never by the session or "
    "a degraded window. Removing it inside a window could flip this repo to "
    "client-mode and escape the file budget."
)
def product_path(raw: str, root: Path, is_harness: bool) -> str | None:
    """Compatibility name for the shared repo-kind-aware lock classifier."""
    return locked_repo_path(raw, root, harness_source=is_harness)


def _lexical_product_path(rel: str, is_harness: bool) -> str | None:
    """Classify a normalized patch path without resolving a symlink leaf."""
    if not rel or rel in ORCHESTRATION_FILES:
        return None
    prefixes = ORCHESTRATION_PREFIXES
    if not is_harness:
        prefixes += CLIENT_MACHINERY_PREFIXES
    if any(rel == prefix.rstrip("/") or rel.startswith(prefix)
           for prefix in prefixes):
        return None
    return rel


def tokenize(segment: str) -> list[str] | None:
    """Shell tokens, or None when the segment cannot be parsed at all."""
    try:
        lexer = shlex.shlex(segment, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return None


QUOTED_REDIRECT_CHARS = {"<": "\ue000", ">": "\ue001", "&": "\ue002"}


def _protect_quoted_redirect_chars(value: str) -> str:
    """Keep quoted or escaped redirection punctuation out of shell operators."""
    result: list[str] = []
    quote: str | None = None
    escaped = False
    for char in value:
        if escaped:
            result.append(QUOTED_REDIRECT_CHARS.get(char, char))
            escaped = False
            continue
        if char == "\\" and quote != "'":
            result.append(char)
            escaped = True
            continue
        if quote:
            result.append(QUOTED_REDIRECT_CHARS.get(char, char))
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
        result.append(char)
    return "".join(result)


def tokenize_write_command(segment: str) -> list[str] | None:
    """Tokenize while retaining whether redirection punctuation was quoted."""
    return tokenize(_protect_quoted_redirect_chars(segment))


def _is_directory_operand(raw: str, root: Path) -> bool:
    path = Path(raw).expanduser()
    return (path if path.is_absolute() else root / path).is_dir()


COPY_WRITE_PROGRAMS = {"cp", "mv", "install", "rsync", "ln"}


def _copy_write_targets(name: str, args: list[str], root: Path) -> list[str]:
    operands = [arg for arg in args if not arg.startswith("-")]
    if len(operands) < 2:
        return operands
    dest = operands[-1]
    sources = operands[:-1] if name == "mv" else []
    if dest.endswith("/") or _is_directory_operand(dest, root):
        base = dest.rstrip("/")
        return sources + [
            f"{base}/{Path(source).name}" for source in operands[:-1]
        ]
    return sources + [dest]


PREFIX_VALUE_OPTIONS = {
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"},
    "sudo": {"-u", "--user", "-g", "--group", "-h", "--host", "-p", "--prompt",
             "-C", "--close-from", "-D", "--chdir", "-R", "--chroot", "-T",
             "--command-timeout", "-r", "--role", "-t", "--type", "-U",
             "--other-user"},
}


def _shell_command_index(tokens: list[str]) -> int | None:
    index = 0
    while index < len(tokens) and re.fullmatch(r"\w+=\S*", tokens[index]):
        index += 1
    while index < len(tokens):
        name = tokens[index].rsplit("/", 1)[-1]
        if name not in {"env", "command", "sudo"}:
            return index
        index += 1
        while index < len(tokens) and (re.fullmatch(r"\w+=\S*", tokens[index])
                                       or tokens[index].startswith("-")):
            index += 2 if tokens[index] in PREFIX_VALUE_OPTIONS.get(name, ()) else 1
    return index if index < len(tokens) else None


def has_directory_change(command: str) -> bool:
    for segment in split_shell_segments(strip_heredoc_bodies(command)):
        tokens = tokenize_write_command(segment)
        if tokens is None:
            continue
        command_index = _shell_command_index(tokens)
        if command_index is not None and tokens[command_index].rsplit("/", 1)[-1] \
                in {"cd", "pushd"}:
            return True
    return False


def split_shell_segments(value: str) -> list[str]:
    """Split shell commands on unquoted separators, preserving continuations."""
    segments: list[str] = []
    segment: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(value):
        char = value[index]
        if quote == "'":
            segment.append(char)
            if char == quote:
                quote = None
            index += 1
            continue
        if char == "\\" and quote != "'":
            if index + 1 < len(value) and value[index + 1] == "\n":
                index += 2
                continue
            segment.append(char)
            if index + 1 < len(value):
                segment.append(value[index + 1])
                index += 2
            else:
                index += 1
            continue
        if quote:
            segment.append(char)
            if char == quote:
                quote = None
        elif char in {"'", '"'}:
            quote = char
            segment.append(char)
        elif char in ";|&\n" and not (
                (char == "|" and index > 0 and value[index - 1] == ">")
                or (char == "&" and (
                    (index > 0 and value[index - 1] == ">")
                    or (index + 1 < len(value) and value[index + 1] == ">")
                ))):
            if "".join(segment).strip():
                segments.append("".join(segment))
            segment = []
        else:
            segment.append(char)
        index += 1
    if "".join(segment).strip():
        segments.append("".join(segment))
    return segments


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


OUTPUT_REDIRECT = re.compile(
    r"^(?P<fd>\d*)(?P<operator>&>>|&>|>&|>>|>\||<>|>)"
    r"(?P<target>.*)$"
)
INPUT_REDIRECT = re.compile(
    r"^(?P<fd>\d*)(?P<operator><<<|<<-|<<|<&|<)(?P<target>.*)$"
)


def _restore_quoted_redirect_chars(tokens: list[str]) -> list[str]:
    restored = {value: char for char, value in QUOTED_REDIRECT_CHARS.items()}
    return ["".join(restored.get(char, char) for char in token)
            for token in tokens]


def redirect_targets(tokens: list[str]) -> tuple[list[str], list[str]]:
    """Return output redirect targets and tokens with redirects removed."""
    targets: list[str] = []
    kept: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.isdigit() and index + 1 < len(tokens):
            next_token = tokens[index + 1]
            next_output = OUTPUT_REDIRECT.match(next_token)
            next_input = INPUT_REDIRECT.match(next_token)
            if ((next_output and not next_output.group("fd"))
                    or (next_input and not next_input.group("fd"))):
                index += 1
                token = next_token
        output = OUTPUT_REDIRECT.match(token)
        input_redirect = INPUT_REDIRECT.match(token)
        if output:
            operator = output.group("operator")
            target = output.group("target")
            index += 1
            if not target and index < len(tokens):
                target = tokens[index]
                index += 1
            if operator != ">&" or (target != "-" and not target.isdigit()):
                if target and target != "/dev/null":
                    targets.append(target)
            continue
        if input_redirect:
            index += 1
            if not input_redirect.group("target") and index < len(tokens):
                if (input_redirect.group("operator") == "<<"
                        and tokens[index] == "-"):
                    index += 1
                if index < len(tokens):
                    index += 1
            continue
        kept.append(token)
        index += 1
    return (
        _restore_quoted_redirect_chars(targets),
        _restore_quoted_redirect_chars(kept),
    )


WRITER_PROGRAMS = {
    "sed", "cp", "mv", "rm", "rmdir", "tee", "touch", "mkdir", "ln",
    "install", "truncate", "dd", "patch", "rsync", "chmod", "chown",
    "unlink",
}


def _writer_form_is_plain(name: str, args: list[str]) -> bool:
    allowed = {"sed": {"-i", "-e", "-E", "-r"}, "cp": {"-f"},
               "mv": {"-f"}, "rm": {"-f"}, "ln": {"-f"},
               "mkdir": {"-p"}, "tee": {"-a"}}.get(name, set())
    return not any(arg.startswith("-") and arg not in allowed
                   or name == "dd" and "=" in arg
                   or name == "sed" and arg == "-i" and i + 1 < len(args)
                   and args[i + 1].startswith(".") and args[i + 1]
                   or name == "sed" and arg == "-e" and i + 1 == len(args)
                   for i, arg in enumerate(args))


def _wrapped_writer(tokens: list[str]) -> bool:
    index = _shell_command_index(tokens)
    if index is None:
        return False
    name = tokens[index].rsplit("/", 1)[-1]
    if name in WRITER_PROGRAMS:
        return True
    if name not in {"sh", "bash", "dash", "ksh", "zsh"}:
        return False
    for offset, option in enumerate(tokens[index + 1:-1]):
        if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", option):
            script = tokens[index + 2 + offset]
            for segment in split_shell_segments(script):
                nested = tokenize_write_command(segment)
                if nested is None or _wrapped_writer(nested):
                    return True
            return False
    return False


def _xargs_writer(args: list[str]) -> bool:
    values = {"-a", "--arg-file", "-d", "--delimiter", "-E", "--eof",
              "-I", "--replace", "-L", "--max-lines", "-n", "--max-args",
              "-P", "--max-procs", "-s", "--max-chars"}
    flags = {"-0", "--null", "-p", "--interactive", "-r", "--no-run-if-empty",
             "-t", "--verbose", "-x", "--exit", "--show-limits", "--help",
             "--version"}
    index = 0
    while index < len(args) and args[index].startswith("-"):
        option = args[index]
        if option == "--":
            index += 1
            break
        if option in values:
            index += 2
        elif option in flags or any(
                option.startswith(value + "=")
                for value in values if value.startswith("--")):
            index += 1
        elif any(option.startswith(value) and len(option) > len(value)
                 for value in values if value.startswith("-")):
            index += 1
        else:
            return True
    return _wrapped_writer(args[index:])


def _env_split_writer(tokens: list[str]) -> bool:
    for index, option in enumerate(tokens[1:], start=1):
        if option in {"-S", "--split-string"} and index + 1 < len(tokens):
            value = tokens[index + 1]
        elif option.startswith("-S") and option != "-S":
            value = option[2:]
        elif option.startswith("--split-string="):
            value = option.split("=", 1)[1]
        else:
            continue
        try:
            return _wrapped_writer(shlex.split(value))
        except ValueError:
            return True
    return False


def _writer_targets(name: str, args: list[str]) -> list[str]:
    if name != "sed":
        return [arg.split("=", 1)[1] if "=" in arg else arg
                for arg in args if not arg.startswith("-") or "=" in arg]
    inplace = any(arg.startswith("-") and "i" in arg[1:] for arg in args)
    script = "-e" in args
    skipped = {i + 1 for i, arg in enumerate(args[:-1])
               if arg == "-e" or arg == "-i" and
               (args[i + 1] == "" or args[i + 1].startswith("."))}
    operands = [arg for i, arg in enumerate(args)
                if not arg.startswith("-") and i not in skipped]
    return (operands if script else operands[1:]) if inplace else []


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


def git_subcommand(args: list[str]) -> tuple[str | None, list[str]]:
    """Return the subcommand after the admitted -C path options."""
    index = 0
    while index < len(args):
        token = args[index]
        if token == "-C":
            index += 2
        elif token.startswith("-"):
            return None, []
        else:
            return token, args[index + 1:]
    return None, []


def _opaque_git_global_options(args: list[str]) -> bool:
    """Only literal -C paths are admitted before a Git subcommand."""
    index = 0
    while index < len(args):
        token = args[index]
        if token == "-C":
            if index + 1 == len(args) or any(
                    char in args[index + 1] for char in "$`~*?[{"):
                return True
            index += 2
        elif token.startswith("-"):
            return True
        else:
            return False
    return False


def _git_working_directory(args: list[str], root: Path) -> Path | None:
    """Resolve git's leading -C options, or refuse a redirected worktree."""
    cwd = root
    index = 0
    while index < len(args):
        token = args[index]
        if token == "-C":
            if index + 1 >= len(args):
                return None
            value = args[index + 1]
            candidate = Path(value).expanduser()
            cwd = candidate if candidate.is_absolute() else cwd / candidate
            index += 2
            continue
        if token.startswith("-"):
            return None
        break
    try:
        return cwd.resolve()
    except (OSError, RuntimeError):
        return None


GIT_READ_ONLY_COMMANDS = {
    "status", "log", "diff", "show", "rev-parse", "ls-files", "ls-tree",
    "cat-file", "blame", "grep", "describe", "merge-base", "shortlog",
    "for-each-ref", "check-ignore", "check-attr", "fetch",
}
GIT_APPLY_READ_ONLY = {"--check", "--stat", "--numstat", "--summary"}


def _git_apply_is_read_only(args: list[str]) -> bool:
    modes = set()
    for token in args:
        if token == "--":
            break
        if token in GIT_APPLY_READ_ONLY:
            modes.add(token)
        elif token.startswith("-") and token != "-":
            return False
    return bool(modes) and "--apply" not in args


def _git_list_form(
        args: list[str], *, flags: set[str], listed: bool = False,
) -> bool:
    """Accept listing forms, with patterns only after a listing option."""
    listing = not args or listed
    patterns = listed
    for arg in args:
        if arg in {"--list", "-l"}:
            listing = True
            patterns = True
        elif arg == "--":
            if not listing:
                return False
            patterns = True
        elif arg in flags:
            continue
        elif any(arg.startswith(flag + "=") for flag in flags
                 if flag.startswith("--")):
            continue
        elif not arg.startswith("-") and patterns:
            continue
        else:
            return False
    return listing


def _git_read_or_index_only(sub: str | None, args: list[str]) -> bool:
    """Whether this exact Git form cannot write worktree files."""
    if any(arg == "--output" or arg.startswith("--output=") for arg in args):
        return False
    if sub in {"diff", "log", "show", "reflog", "shortlog"} and any(
            arg == "-o" or arg.startswith("-o") and arg != "-o"
            for arg in args):
        return False
    if sub in {"add", "commit"}:
        return True
    if sub in GIT_READ_ONLY_COMMANDS:
        return True
    if sub == "reflog":
        action = next((arg for arg in args if not arg.startswith("-")), None)
        return action in {None, "show", "list"}
    if sub == "branch":
        listing_flags = {"-a", "-r", "--all", "--remotes", "-v", "-vv",
                         "--verbose", "--show-current", "--contains",
                         "--merged", "--no-merged", "--no-contains",
                         "--points-at"}
        return _git_list_form(
            args, listed=not args or any(arg in listing_flags for arg in args),
            flags=listing_flags | {"--no-abbrev", "--contains", "--merged",
                                   "--no-merged"},
        )
    if sub == "tag":
        if not args:
            return True
        return _git_list_form(
            args, flags={"--contains", "--no-contains", "--merged",
                         "--no-merged", "--points-at", "--ignore-case", "-i",
                         "--column", "--no-column", "--color", "--no-color",
                         "-n"},
        ) and args[0] in {"-l", "--list"}
    if sub == "remote":
        if not args or args in (["-v"], ["--verbose"]):
            return True
        return (args[0] == "get-url"
                and all(arg in {"--all", "--push"} or not arg.startswith("-")
                        for arg in args[1:])
                and sum(not arg.startswith("-") for arg in args[1:]) == 1)
    if sub == "config":
        read_options = {"--local", "--global", "--system", "--worktree",
                        "--show-origin", "--show-scope", "--null", "-z",
                        "--name-only", "--includes", "--no-includes"}
        index = 0
        while index < len(args):
            option = args[index]
            if option in read_options or option.startswith(("--file=", "--type=")):
                index += 1
            elif option in {"--file", "-f"} and index + 1 < len(args):
                index += 2
            else:
                break
        if index == len(args):
            return False
        action, rest = args[index], args[index + 1:]
        if action == "--get":
            return (len(rest) in {1, 2}
                    and all(not arg.startswith("-") for arg in rest))
        return (action in {"--list", "-l"}
                and all(arg in read_options or arg.startswith(
                    ("--file=", "--type=")) for arg in rest))
    if sub == "worktree":
        return (bool(args) and args[0] == "list"
                and all(arg in {"--porcelain", "-z", "--verbose", "-v"}
                        for arg in args[1:]))
    if sub == "stash":
        return bool(args) and args[0] in {"list", "show"}
    if sub == "notes":
        return (not args or args[0] in {"list", "show"})
    if sub == "symbolic-ref":
        options = {"-q", "--quiet", "--short", "--no-recurse", "--recurse"}
        names = [arg for arg in args if not arg.startswith("-")]
        return len(names) == 1 and all(
            arg in options or not arg.startswith("-") for arg in args
        )
    if sub == "apply":
        return _git_apply_is_read_only(args)
    return False


def _git_location(git_args: list[str], root: Path) -> tuple[Path, Path] | None:
    cwd = _git_working_directory(git_args, root)
    if cwd is None:
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=cwd,
            capture_output=True, text=True, encoding="utf-8",
            errors="surrogateescape",
        )
        if result.returncode:
            return None
        return cwd, Path(result.stdout.strip()).resolve()
    except (OSError, RuntimeError, subprocess.SubprocessError):
        return None


def _literal_git_file_path(raw: str) -> bool:
    return bool(raw and not raw.startswith(":") and not raw.endswith("/")
                and not Path(raw).is_absolute()
                and not any(char in raw for char in "*?[{"))


def _git_file_form(sub: str, args: list[str]) -> tuple[list[str], str | None] | None:
    """Parse only restore/checkout forms with literal file pathspecs."""
    if sub == "restore":
        if "--" in args:
            if args.count("--") != 1 or args[0] != "--":
                return None
            paths = args[1:]
        else:
            paths = args
            if any(path.startswith("-") for path in paths):
                return None
        source = None
    elif sub == "checkout":
        if args.count("--") != 1:
            return None
        separator = args.index("--")
        before, paths = args[:separator], args[separator + 1:]
        if len(before) > 1 or any(token.startswith("-") for token in before):
            return None
        source = before[0] if before else None
    else:
        return None
    if not paths or not all(_literal_git_file_path(path) for path in paths):
        return None
    return paths, source


def _git_apply_paths(
        args: list[str], root: Path, git_args: list[str],
) -> list[str] | None:
    """Resolve the literal file paths changed by one patch file."""
    if len(args) != 1 or not args[0] or args[0].startswith("-"):
        return None
    location = _git_location(git_args, root)
    if location is None:
        return None
    cwd, checkout_root = location
    patch_path = Path(args[0]).expanduser()
    if not patch_path.is_absolute():
        patch_path = cwd / patch_path
    if not patch_path.is_file():
        return None
    try:
        result = subprocess.run(
            ["git", "apply", "--numstat", "-z", str(patch_path)],
            cwd=cwd, capture_output=True, text=True, encoding="utf-8",
            errors="surrogateescape",
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode:
        return None
    paths: list[str] = []
    records = result.stdout.split("\0")
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        fields = record.split("\t", 2)
        if len(fields) != 3:
            return None
        if fields[2]:
            paths.append(fields[2])
        else:
            if index + 1 >= len(records) or not records[index] or not records[index + 1]:
                return None
            paths.extend((records[index], records[index + 1]))
            index += 2
    return _resolve_git_file_paths(paths, cwd, checkout_root, root, git_args)


def _resolve_git_file_paths(
        paths: list[str], cwd: Path, checkout_root: Path, root: Path,
        git_args: list[str], source: str | None = None,
) -> list[str] | None:
    if not paths:
        return None
    result_paths: list[str] = []
    for raw in paths:
        if not _literal_git_file_path(raw):
            return None
        try:
            lexical_target = Path(os.path.abspath(cwd / raw))
            lexical_rel = lexical_target.relative_to(checkout_root).as_posix()
            lexical_parent = lexical_target.parent.relative_to(checkout_root)
            resolved_parent = lexical_target.parent.resolve().relative_to(checkout_root)
            target = lexical_target.resolve(strict=lexical_target.is_symlink())
            resolved_rel = target.relative_to(checkout_root).as_posix()
        except (OSError, RuntimeError, ValueError):
            return None
        if (not lexical_rel or lexical_rel == "."
                or lexical_parent != resolved_parent or target.is_dir()):
            return None
        try:
            indexed = subprocess.run(
                ["git", "ls-files", "--full-name", "-z", "--", raw],
                cwd=cwd, capture_output=True, text=True,
                encoding="utf-8", errors="surrogateescape",
            )
            if indexed.returncode:
                return None
        except (OSError, subprocess.SubprocessError):
            return None
        if any(path != lexical_rel and path.startswith(lexical_rel + "/")
               for path in indexed.stdout.split("\0") if path):
            return None
        if source is not None:
            try:
                entry = subprocess.run(
                    ["git", "ls-tree", "-z", "--full-tree", source,
                     "--", lexical_rel],
                    cwd=checkout_root, capture_output=True, text=True,
                    encoding="utf-8", errors="surrogateescape",
                )
            except (OSError, subprocess.SubprocessError):
                return None
            if entry.returncode:
                return None
            for record in entry.stdout.split("\0"):
                if not record:
                    continue
                metadata, _, entry_path = record.partition("\t")
                if entry_path == lexical_rel and len(metadata.split()) > 1 \
                        and metadata.split()[1] != "blob":
                    return None
        for rel in dict.fromkeys((lexical_rel, resolved_rel)):
            result_paths.append(
                rel if checkout_root == root.resolve() else str(checkout_root / rel)
            )
    return list(dict.fromkeys(result_paths))


def _git_write_paths(
        sub: str | None, args: list[str], root: Path, git_args: list[str],
) -> list[str] | None:
    if sub == "apply":
        if _git_apply_is_read_only(args):
            return []
        return _git_apply_paths(args, root, git_args)
    form = _git_file_form(sub or "", args)
    if form is None:
        return None
    paths, source = form
    location = _git_location(git_args, root)
    if location is None:
        return None
    cwd, checkout_root = location
    return _resolve_git_file_paths(paths, cwd, checkout_root, root, git_args, source)


def has_git_commit(value: str) -> bool:
    """True when a shell segment directly invokes `git ... commit`."""
    for segment in split_shell_segments(strip_heredoc_bodies(value)):
        tokens = tokenize(segment)
        if tokens is None:
            continue
        command_index = _shell_command_index(tokens)
        if command_index is None:
            continue
        if tokens[command_index].rsplit("/", 1)[-1] != "git":
            continue
        if git_subcommand(tokens[command_index + 1:])[0] == "commit":
            return True
    return False


def bash_write_paths(value: str, root: Path) -> list[str]:
    """Extract likely write targets from a shell command.

    # ponytail: heuristic, defends drift not adversaries — tighten patterns
    # if a real bypass shows up.
    """
    found: list[str] = []
    # Newlines separate commands too: without them a multi-line script is one
    # segment, and an earlier command's operand list swallows later lines.
    for segment in split_shell_segments(strip_heredoc_bodies(value)):
        tokens = tokenize_write_command(segment)
        if tokens is None:
            continue
        redirects, tokens = redirect_targets(tokens)
        found.extend(redirects)
        # Command POSITION only (after env-var prefixes) — the same discipline
        # the codex-exec guard uses. Otherwise prose that merely mentions a
        # tool ("...sed -i, cp, mv...") is parsed as an invocation.
        command_index = _shell_command_index(tokens)
        if command_index is None:
            continue
        command_name = tokens[command_index].rsplit("/", 1)[-1]
        if command_name not in WRITER_PROGRAMS | {"git"}:
            continue
        args = tokens[command_index + 1:]
        if command_name == "git":
            if _opaque_git_global_options(args):
                found.extend(_writer_targets("git", args) or [])
            else:
                sub, sub_args = git_subcommand(args)
                paths = _git_write_paths(sub, sub_args, root, args)
                if paths is not None:
                    found.extend(paths)
                elif sub in {"rm", "mv"}:
                    found.extend(token for token in sub_args
                                 if token != "--" and not token.startswith("-"))
        else:
            targets = (
                _copy_write_targets(command_name, args, root)
                if command_name in COPY_WRITE_PROGRAMS
                else _writer_targets(command_name, args)
            )
            if targets:
                found.extend(targets)
    return found


PATCH_HEADER = re.compile(r"^\*\*\* (Add|Update|Delete) File: (.+)$")


def apply_patch_paths(value: str) -> list[tuple[str, str]] | None:
    """Extract every write path from one native apply_patch payload.

    None is a malformed patch. The parser understands only the native patch
    envelope and its Add/Update/Delete/Move controls, so an unknown control
    fails closed instead of silently dropping a write target.
    """
    lines = value.splitlines()
    if len(lines) < 3 or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
        return None
    paths: list[tuple[str, str]] = []
    operation = ""
    moved = False
    operation_index = -1
    for line in lines[1:-1]:
        match = PATCH_HEADER.fullmatch(line)
        if match:
            operation = match.group(1)
            moved = False
            path = match.group(2).strip()
            if not path:
                return None
            paths.append((operation, path))
            operation_index = len(paths) - 1
            continue
        if line.startswith("*** Move to: "):
            path = line.removeprefix("*** Move to: ").strip()
            if operation != "Update" or moved or not path:
                return None
            paths[operation_index] = ("Move source", paths[operation_index][1])
            paths.append(("Move destination", path))
            moved = True
            continue
        if line == "*** End of File":
            if operation != "Update":
                return None
            continue
        if line.startswith("*** "):
            return None
    return paths if paths else None


def normalized_patch_paths(
    paths: list[tuple[str, str]], root: Path,
) -> list[str] | None:
    normalized: list[str] = []
    lexical_root = Path(os.path.abspath(root))
    resolved_root = root.resolve()
    for operation, raw in paths:
        if "$" in raw or "`" in raw:
            return None
        candidate = Path(raw).expanduser()
        try:
            absolute = candidate if candidate.is_absolute() else lexical_root / candidate
            lexical = Path(os.path.abspath(absolute))
            rel = lexical.relative_to(lexical_root).as_posix()
            parent = lexical.parent.relative_to(lexical_root)
            resolved_parent = lexical.parent.resolve().relative_to(resolved_root)
        except (OSError, RuntimeError, ValueError):
            return None
        if not rel or rel == "." or resolved_parent != parent:
            return None
        if operation in {"Add", "Update", "Move destination"} \
                and lexical.is_symlink():
            return None
        normalized.append(rel)
    return normalized


def normalized_native_bash_paths(paths: list[str], root: Path) -> list[str] | None:
    """Keep Bash write leaves lexical while refusing linked parents."""
    normalized: list[str] = []
    lexical_root = Path(os.path.abspath(root))
    resolved_root = root.resolve()
    for raw in paths:
        if not raw or raw in {"-", "/dev/null"} or "$" in raw or "`" in raw:
            continue
        candidate = Path(raw).expanduser()
        absolute = candidate if candidate.is_absolute() else lexical_root / candidate
        if absolute.is_absolute() and _cross_worktree_target(str(absolute), root):
            return None
        lexical = Path(os.path.abspath(absolute))
        try:
            resolved_parent = lexical.parent.resolve()
        except (OSError, RuntimeError):
            return None
        try:
            rel = lexical.relative_to(lexical_root).as_posix()
        except ValueError:
            try:
                resolved_parent.relative_to(resolved_root)
            except ValueError:
                continue
            return None
        try:
            parent = lexical.parent.relative_to(lexical_root)
            resolved_parent_rel = resolved_parent.relative_to(resolved_root)
        except ValueError:
            return None
        if not rel or rel == "." or resolved_parent_rel != parent:
            return None
        normalized.append(rel)
        # A write through a symlink leaf lands on its target: scope both.
        if lexical.is_symlink():
            try:
                normalized.append(
                    lexical.resolve(strict=True).relative_to(resolved_root).as_posix())
            except (OSError, RuntimeError, ValueError):
                return None
    return normalized


def _contains_marker(rel: str) -> bool:
    """True when rel IS the repo-kind marker or a directory that contains it.

    An ancestor delete (`rm -r .factory`) removes the marker just as surely as
    deleting it by name. The repo ROOT (`.`/``) is deliberately excluded: it is
    a benign create-destination for `cp/mv <src> .`, not a marker deletion, and
    a genuine root wipe (`rm -rf .`) is caught by the rm-rf policy instead.
    """
    if rel == HARNESS_SOURCE_MARKER:
        return True
    if not rel or rel == ".":
        return False
    return HARNESS_SOURCE_MARKER.startswith(rel.rstrip("/") + "/")


# Shell metacharacters that expand one literal into an unbounded set of paths:
# globs (`*?[`) and brace expansion (`{1..6}`, `{a,b}`).
GLOB_METACHARS = ("*", "?", "[", "{")
OPAQUE_DEGRADED_MSG = (
    "This op touches an unbounded set of machinery files — a recursive/globbed "
    "delete, or a recursive/globbed copy or move INTO a machinery path — so a "
    "degraded window cannot honestly claim it against its budget. Enumerate the exact "
    "paths, or plan the change where the whole diff is measured."
)
OPAQUE_NATIVE_MSG = (
    "Host-native recursive or globbed product operations cannot be proven "
    "to stay within the active task scope."
)
UNPARSEABLE_BASH_MSG = (
    "Bash command could not be safely parsed, so Forge cannot verify "
    "that it respects the delegation and planning boundaries. Use "
    "`./forge delegate <task-id>` for a companion launch."
)
GIT_OPAQUE_MSG = (
    "Opaque Git form `{form}` is not admitted under the session lock. Use "
    "`./forge delegate <task-id>` or a Lite window with literal in-scope file paths."
)


def _opaque_git_form(command: str, root: Path) -> str | None:
    for segment in split_shell_segments(strip_heredoc_bodies(command)):
        tokens = tokenize_write_command(segment)
        if tokens is None:
            continue
        index = _shell_command_index(tokens)
        if index is None or tokens[index].rsplit("/", 1)[-1] != "git":
            continue
        git_args = tokens[index + 1:]
        sub, args = git_subcommand(git_args)
        opaque_globals = _opaque_git_global_options(git_args)
        if not opaque_globals and _git_read_or_index_only(sub, args):
            continue
        if not opaque_globals and _git_write_paths(sub, args, root, git_args) is not None:
            continue
        form = f"git {sub or 'unknown'}"
        if sub in {"stash", "reflog", "remote", "worktree", "notes"}:
            action = next((arg for arg in args if not arg.startswith("-")), None)
            if action:
                form += f" {action}"
        elif sub == "reset":
            mode = next((arg for arg in args
                         if arg in {"--soft", "--mixed", "--hard", "--merge", "--keep"}), None)
            if mode:
                form += f" {mode}"
        elif sub == "restore":
            if any(arg in {"-p", "--patch"} for arg in args):
                form += " -p"
            elif not args:
                form += " (pathless)"
        elif sub == "checkout" and "--" in args:
            form += " <tree> -- <pathspec>"
        return form
    return None


def has_opaque_product_write(
        command: str, root: Path, is_harness: bool) -> bool | str | None:
    """Whether a write has an unbounded product target or opaque form."""
    changed_directory = False
    for segment in split_shell_segments(strip_heredoc_bodies(command)):
        tokens = tokenize_write_command(segment)
        if tokens is None:
            return None
        _, tokens = redirect_targets(tokens)
        index = _shell_command_index(tokens)
        if index is None:
            if tokens and tokens[0].rsplit("/", 1)[-1] == "env" \
                    and _env_split_writer(tokens):
                return "plain"
            continue
        name = tokens[index].rsplit("/", 1)[-1]
        args = tokens[index + 1:]
        if name in {"cd", "pushd"}:
            changed_directory = True
            continue
        if name in WRITER_PROGRAMS and (
                changed_directory
                or any(token.rsplit("/", 1)[-1] == "sudo"
                       or re.fullmatch(r"\w+=\S*", token) for token in tokens[:index])
                or any(token.rsplit("/", 1)[-1] == "env" and any(
                    option.startswith("-") or re.fullmatch(r"\w+=\S*", option)
                    for option in tokens[position + 1:index])
                    for position, token in enumerate(tokens[:index]))
                or not _writer_form_is_plain(name, args)):
            return "plain"
        if name == "xargs" and _xargs_writer(args):
            return "plain"
        if name == "find" and any(
                token in {"-exec", "-execdir"} and _wrapped_writer(args[position + 1:])
                for position, token in enumerate(args)):
            return "plain"
        if name == "git":
            git_args = args
            sub, args = git_subcommand(args)
            if _opaque_git_global_options(git_args):
                return True
            if _git_read_or_index_only(sub, args):
                continue
            if _git_write_paths(sub, args, root, git_args) is None:
                return True
            continue
        elif name not in WRITER_PROGRAMS:
            continue
        targets = (
            _copy_write_targets(name, args, root)
            if name in COPY_WRITE_PROGRAMS else _writer_targets(name, args)
        )
        product_targets = [target for target in targets
                           if product_path(target, root, is_harness)]
        if not product_targets:
            continue
        globbed = any(any(char in target for char in GLOB_METACHARS)
                      for target in targets)
        if globbed:
            return True
        if name == "rsync" and any(
                _is_directory_operand(source, root)
                for source in [arg for arg in args if not arg.startswith("-")][:-1]):
            return True
    return False


def guard_product_writes(
        targets: list[str], root: Path, *, lexical_targets: bool = False,
) -> None:
    window = load_active(root)
    # Effective repo kind: a live marker read, UNLESS a window is open — then
    # the kind pinned at its start wins, so deleting the marker during the window
    # (by any means) cannot flip classification and let machinery escape the
    # budget. Fail-safe: an old window with no pin falls back to the live marker.
    if window is not None and "harness_source" in window:
        is_harness = bool(window["harness_source"])
    else:
        is_harness = is_harness_source_repo(root)
    degraded = bool(window and profile_of(window) == DEGRADED)
    classify = _lexical_product_path if lexical_targets else None
    product = list(dict.fromkeys(
        rel for raw in targets
        if (rel := (classify(raw, is_harness) if classify else
                    product_path(raw, root, is_harness))) is not None
    ))
    if not product:
        return
    if any(_contains_marker(rel) for rel in product):
        # A session window must never be able to touch the marker:
        # deleting it — directly, or by removing an ANCESTOR like `.factory` via
        # `rm -rf .factory` — would disable classification and the budget with it.
        # Only a protected delegated worker whose scope names it may change it.
        deny(MARKER_PLAN_ONLY_MSG)
    if not degraded:
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

# Raw `codex exec` bypasses Forge's protected runtime launch: no bound brief,
# live worker registration, or lifecycle proof. Keep the existing invocation
# matcher, including substitutions and global flags; exempt only exact help argv
# and safe display commands whose quoted text happens to contain the phrase.
SHELL_WORD = r'''(?:"(?:\\[^\r\n]|[^"\\\r\n])*"|'[^'\r\n]*'|\\[^\r\n]|[^\s;&|"'\\])+'''
SHELL_TOKEN = rf"(?:{SHELL_WORD})+"
EXEC_WORD = r'''(?:"exec"|'exec'|exec)'''
EXEC_OPTION = (
    rf'''(?:-[cl]+|-[cl]*a{SHELL_TOKEN}|-[cl]*a\s+{SHELL_WORD})'''
)
CODEX_EXEC_INVOCATION = re.compile(
    r"(?:^|[;&|]\s*|\$\(\s*|[<>]\(\s*|(?<![\w=(@?!+*$])\(\s*|`\s*)"
    rf"(?:\w+={SHELL_WORD}\s+)*(?:command(?:\s+-p)*(?:\s+--)?\s+)?"
    rf"(?:{EXEC_WORD}\s+(?:{EXEC_OPTION}\s+)*(?:--\s+)?)?"
    r"(?:\"[^\"\r\n;&|]*[/\\]codex(?:\.exe|\.cmd)?\"|"
    r"'[^'\r\n;&|]*[/\\]codex(?:\.exe|\.cmd)?'|"
    r"(?:[^\s;&|]*[/\\])?codex(?:\.exe|\.cmd)?)"
    rf"(?:\s+-{{1,2}}[\w-]+(?:[= ]{SHELL_WORD})?)*"
    r"\s+exec\b",
    re.IGNORECASE | re.MULTILINE,
)


def _active_codex_exec_match(value: str) -> bool:
    """Accept regex candidates only at active shell boundaries."""
    quote = None
    escaped = False
    substitutions: list[tuple[str, str | None, int]] = []
    position = 0
    for match in CODEX_EXEC_INVOCATION.finditer(value):
        while position < match.start():
            char = value[position]
            if escaped:
                escaped = False
            elif char == "\\" and quote != "'":
                escaped = True
            elif quote == "'":
                if char == quote:
                    quote = None
            elif value.startswith("$(", position):
                substitutions.append((")", quote, 0))
                quote = None
                position += 2
                continue
            elif quote is None and value.startswith(("<(", ">("), position):
                substitutions.append((")", quote, 0))
                position += 2
                continue
            elif char == "`":
                if quote is None and substitutions and substitutions[-1][0] == "`":
                    _closing, quote, _depth = substitutions.pop()
                else:
                    substitutions.append(("`", quote, 0))
                    quote = None
            elif quote:
                if char == quote:
                    quote = None
            elif substitutions and char == "(" and substitutions[-1][0] == ")":
                closing, saved_quote, depth = substitutions[-1]
                substitutions[-1] = (closing, saved_quote, depth + 1)
            elif substitutions and char == substitutions[-1][0]:
                if char == ")" and substitutions[-1][2]:
                    closing, saved_quote, depth = substitutions[-1]
                    substitutions[-1] = (closing, saved_quote, depth - 1)
                else:
                    _closing, quote, _depth = substitutions.pop()
            elif char in "'\"":
                quote = char
            position += 1
        boundary = match.group(0).lstrip()
        if (not escaped and
                (quote is None or
                 (quote == '"' and boundary.startswith(("$(", "`"))))):
            return True
    return False


def _wrapped_codex_exec(tokens: list[str]) -> bool:
    """Detect a literal Codex exec argv behind a command wrapper."""
    def codex_exec_at(index: int) -> bool:
        if re.split(r"[/\\]", tokens[index])[-1].lower() not in {
                "codex", "codex.exe", "codex.cmd"}:
            return False
        operand_options = {
            "-a", "--ask-for-approval", "-C", "--cd", "-c", "--config",
            "--disable", "--enable", "-i", "--image", "--local-provider",
            "-m", "--model", "-p", "--profile", "-s", "--sandbox", "--add-dir",
        }
        position = index + 1
        while position < len(tokens):
            option = tokens[position]
            if option in operand_options:
                position += 2
                continue
            if any(option.startswith(f"{name}=") for name in operand_options):
                position += 1
                continue
            if option.startswith("-"):
                return "exec" in tokens[position + 1:]
            return option == "exec"
        return False

    def literal_launch_after(start: int) -> bool:
        return any(codex_exec_at(index) for index in range(start, len(tokens)))

    def split_env_launch(value: str, tail: list[str]) -> bool:
        try:
            return _wrapped_codex_exec(["env", *shlex.split(value), *tail])
        except ValueError:
            return False

    position = 0
    while position < len(tokens):
        name = re.split(r"[/\\]", tokens[position])[-1].lower()
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[position]):
            position += 1
            continue
        if codex_exec_at(position):
            return True
        if name in {"command", "nohup"}:
            position += 1
            while position < len(tokens) and tokens[position].startswith("-"):
                option = tokens[position]
                if option in {"--help", "--version"}:
                    return False
                if option == "--":
                    position += 1
                    break
                if name == "command" and option[1:] and set(option[1:]) <= {"p", "v", "V"}:
                    if set(option[1:]) & {"v", "V"}:
                        return False
                    position += 1
                    continue
                return literal_launch_after(position + 1)
            continue
        if name == "env":
            position += 1
            options = True
            while position < len(tokens):
                option = tokens[position]
                if options and option in {"--help", "--version"}:
                    return False
                if options and option == "--":
                    position += 1
                    options = False
                    continue
                if not option.startswith("-") and "=" in option.split("/", 1)[0]:
                    position += 1
                    continue
                if not options:
                    break
                if option in {"-S", "--split-string"}:
                    if position + 1 >= len(tokens):
                        return False
                    return split_env_launch(tokens[position + 1], tokens[position + 2:])
                if option.startswith("-S") and option != "-S":
                    return split_env_launch(option[2:], tokens[position + 1:])
                if option.startswith("--split-string="):
                    return split_env_launch(option.split("=", 1)[1], tokens[position + 1:])
                if option in {"-u", "--unset", "-C", "--chdir"}:
                    position += 2
                    continue
                if option in {"-i", "--ignore-environment", "-0", "--null", "-v", "--debug"}:
                    position += 1
                    continue
                if option.startswith(("-u", "-C", "--unset=", "--chdir=")):
                    position += 1
                    continue
                if option.startswith("-"):
                    return literal_launch_after(position + 1)
                break
            continue
        if name == "nice":
            position += 1
            while position < len(tokens) and tokens[position].startswith(("-", "+")):
                option = tokens[position]
                if option in {"--help", "--version"}:
                    return False
                if option == "--":
                    position += 1
                    break
                if option in {"-n", "--adjustment"}:
                    position += 2
                elif re.fullmatch(r"[+-]\d+", option) or option.startswith(
                        ("-n", "--adjustment=")):
                    position += 1
                else:
                    return literal_launch_after(position + 1)
            continue
        if name == "xargs":
            position += 1
            while position < len(tokens) and tokens[position].startswith("-"):
                option = tokens[position]
                if option in {"--help", "--version"}:
                    return False
                if option == "--":
                    position += 1
                    break
                operand_options = {
                    "-a", "--arg-file", "-d", "--delimiter", "-E", "--eof",
                    "-I", "--replace", "-L", "--max-lines", "-n", "--max-args",
                    "-P", "--max-procs", "-s", "--max-chars",
                }
                if option in operand_options:
                    position += 2
                elif option in {"-0", "--null", "-p", "--interactive", "-r",
                                "--no-run-if-empty", "-t", "--verbose", "-x",
                                "--exit", "--show-limits"} or any(
                                    option.startswith(prefix)
                                    for prefix in ("-a", "-d", "-E", "-I", "-L", "-n",
                                                   "-P", "-s", "--arg-file=",
                                                   "--delimiter=", "--eof=", "--replace=",
                                                   "--max-lines=", "--max-args=",
                                                   "--max-procs=", "--max-chars=")):
                    position += 1
                else:
                    return literal_launch_after(position + 1)
            continue
        if name in {"sh", "bash", "dash", "ksh", "zsh"}:
            shell = name
            position += 1
            while position < len(tokens):
                option = tokens[position]
                if option == "--" or not option.startswith(("-", "+")):
                    return False
                if shell == "bash" and option.startswith(
                        ("--rcfile=", "--init-file=")):
                    position += 1
                    continue
                if shell == "bash" and option in {"--rcfile", "--init-file"}:
                    position += 2
                    continue
                if not option.startswith("--"):
                    operand_letters = {"o"} | ({"O"} if shell == "bash" else set())
                    consumed_operand = False
                    for offset, letter in enumerate(option[1:]):
                        if letter in operand_letters:
                            position += 1 if option[offset + 2:] else 2
                            consumed_operand = True
                            break
                        if option.startswith("-") and letter == "c":
                            try:
                                nested = tokens[position + 1]
                                nested_tokens = shlex.split(nested)
                            except (ValueError, IndexError):
                                return False
                            return bool(_active_codex_exec_match(nested)
                                        or _wrapped_codex_exec(nested_tokens))
                    if consumed_operand:
                        continue
                position += 1
            return False
        return False
    return False

check_bypass = ["pnpm test", "pnpm lint", "pnpm typecheck", "pnpm check:all"]
if (not native_codex and any(token in command for token in check_bypass)
        and "factory/scripts/verify.py" not in command):
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
# Hotfix (vendored; upstream symphony-forge): a file-tool write into a SIBLING
# worktree must be governed and claimed by THAT checkout's lock and mode
# window, not the session cwd's. Without this, an Edit/Write whose target lies
# outside the cwd root is neither locked nor counted against a degraded window.
if tool_name in EDIT_TOOLS:
    _edit_target = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if _edit_target and Path(_edit_target).is_absolute():
        _target = Path(_edit_target).resolve()
        try:
            _target.relative_to(root.resolve())
        except ValueError:
            # Keep walking outward to the first parent that is a HARNESS
            # checkout. Stopping at the first `.git` and then validating it
            # gave up whenever a nested Git root sat on the way up — a
            # vendored dependency, a sub-project, any checkout inside the
            # tree — and fell back to session-cwd governance, which is the
            # ungoverned write this block exists to prevent.
            _alt = _harness_checkout(_target)
            if _alt is not None:
                root = _alt
unmerged = _unmerged_paths(root)
if tool_name in EDIT_TOOLS and unmerged:
    edit_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if edit_path:
        candidate = Path(edit_path)
        try:
            rel = (candidate if candidate.is_absolute() else root / candidate).resolve() \
                .relative_to(root.resolve()).as_posix()
        except ValueError:
            rel = ""
        if rel in unmerged:
            deny("Conflicted files must be resolved with git-native recovery, not content hand-writes.")

try:
    state_path = run_state_path(root)
    run_state = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if state_path.is_file() else {}
    )
    if not isinstance(run_state, dict):
        raise TypeError("run state must be a JSON object")
except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
    denylist_fallback(payload, type(exc).__name__)

window = load_active(root)
is_harness = (
    bool(window["harness_source"])
    if window is not None and "harness_source" in window
    else is_harness_source_repo(root)
)
opaque = has_opaque_product_write(command, root, is_harness) \
    if tool_name == "Bash" and command else False
if opaque == "plain":
    deny("the write lock only allows plain file writes; use a Lite window or "
         "`forge delegate` for this command")
if opaque is None:
    deny(UNPARSEABLE_BASH_MSG)

if tool_name == "Bash" and has_directory_change(command) and (
        bash_write_paths(command, root) or _opaque_git_form(command, root)):
    deny("run writes from the checkout without changing directory")

if tool_name == "Bash" and has_git_commit(command):
    context_dir, ledger_path = context_paths(root)
    # An inbox that was never scanned and holds nothing stays untouched: the
    # belt must not leave an untracked ledger.json behind on every commit.
    if ledger_path.exists() or (context_dir.is_dir() and context_files(context_dir)):
        drift, refused = scan_inbox(root)
    else:
        drift, refused = [], []
    if refused:
        deny("REFUSED (not registered — fix, then rescan):\n" +
             "\n".join(f"- {line}" for line in refused))
    if drift:
        staged = subprocess.run(
            ["git", "add", "--", "docs/context/ledger.json"],
            cwd=root, capture_output=True, text=True,
            encoding="utf-8", errors="surrogateescape",
        )
        if staged.returncode:
            deny("Context ledger refreshed but could not be staged: " +
                 (staged.stderr.strip() or staged.stdout.strip() or "git add failed"))

edit_target = (tool_input.get("file_path") or tool_input.get("notebook_path") or "")
write_targets = [edit_target] if tool_name in EDIT_TOOLS and edit_target else []
if tool_name == "Bash":
    write_targets = bash_write_paths(command, root)
    _deny_cross_worktree_targets(write_targets, root)
    write_targets = normalized_native_bash_paths(write_targets, root)
    if write_targets is None:
        deny(
            "Host-native Bash writes cannot traverse a symlinked or unresolved parent."
            if native_codex else
            "Bash writes cannot traverse a symlinked or unresolved parent."
        )
elif tool_name == PATCH_TOOL:
    parsed_patch_paths = apply_patch_paths(command)
    if parsed_patch_paths is not None:
        _deny_cross_worktree_targets(
            [raw for _operation, raw in parsed_patch_paths], root,
        )
    normalized_paths = (
        normalized_patch_paths(parsed_patch_paths, root)
        if parsed_patch_paths is not None else None
    )
    if normalized_paths is None:
        deny("apply_patch payload is malformed; Forge cannot prove its write paths.")
    write_targets = normalized_paths

# Recorded state is never hand-written, in any mode and at any plan status.
for candidate in write_targets:
    if in_factory_state(candidate, root):
        deny(FACTORY_STATE_MSG)

# The session lock covers every permission mode. Planning changes authorization
# for the plan UI, never for product or canon writes.
if command and tool_name == "Bash":
    if opaque:
        git_form = _opaque_git_form(command, root)
        contains_marker = any(
                _contains_marker(rel)
                for raw in write_targets
                if (rel := _lexical_product_path(raw, is_harness)) is not None
        )
        if contains_marker:
            if git_form:
                deny(GIT_OPAQUE_MSG.format(form=git_form) + " " + MARKER_PLAN_ONLY_MSG)
            deny(MARKER_PLAN_ONLY_MSG)
        if git_form:
            deny(GIT_OPAQUE_MSG.format(form=git_form))
        if native_codex:
            deny(OPAQUE_DEGRADED_MSG if window else OPAQUE_NATIVE_MSG)
        deny(OPAQUE_DEGRADED_MSG if window and profile_of(window) == DEGRADED
             else PLAN_MODE_MSG)
if tool_name == "Bash" or native_codex and tool_name == PATCH_TOOL:
    locked_targets = list(dict.fromkeys(
        rel for raw in write_targets
        if (rel := _lexical_product_path(raw, is_harness)) is not None
    ))
else:
    locked_targets = list(dict.fromkeys(
        rel for raw in write_targets
        if (rel := product_path(raw, root, is_harness)) is not None
    ))
if tool_name == PATCH_TOOL:
    scoped_targets = (
        list(dict.fromkeys(
            rel for raw in write_targets
            if (rel := _lexical_product_path(raw, is_harness)) is not None
        ))
        if native_codex else write_targets
    )
else:
    scoped_targets = locked_targets
if native_codex:
    is_degraded = False
    if scoped_targets:
        if window:
            from forge_cli.quickfix import DEGRADED, LITE, profile_of
            profile = profile_of(window)
            is_degraded = profile == DEGRADED or window.get("kind") == DEGRADED
            if any(_contains_marker(rel) for rel in scoped_targets):
                deny(MARKER_PLAN_ONLY_MSG)
            if profile == LITE and not is_degraded:
                claimed, _ = claim_files(root, locked_targets)
                if not claimed:
                    deny(QUICKFIX_LIMIT_MSG)
            elif not is_degraded:
                deny(
                    "Host-native product writes require an authorized Lite or "
                    "active task stage; ordinary quickfix is recording-only."
                )
        if not window or is_degraded:
            try:
                from forge_cli.worker_admission import (
                    native_stage_admission, path_in_scope,
                )
            except (ImportError, SyntaxError) as exc:
                denylist_fallback(payload, type(exc).__name__)
            worker, worker_error = native_stage_admission(root)
            if worker_error:
                deny(worker_error)
            outside = [rel for rel in scoped_targets
                       if not path_in_scope(rel, worker["scope"])]
            if outside:
                deny("Host-native write is outside the active task scope: "
                     + ", ".join(outside))
else:
    try:
        from forge_cli.worker_admission import live_worker_admission, path_in_scope
    except (ImportError, SyntaxError) as exc:
        denylist_fallback(payload, type(exc).__name__)
    worker, worker_error = live_worker_admission(root)
    if scoped_targets and worker_error:
        deny(worker_error)
    if scoped_targets and worker:
        marker_targeted = any(_contains_marker(rel) for rel in scoped_targets)
        if marker_targeted and worker["kind"] != "stage":
            deny(MARKER_PLAN_ONLY_MSG)
        if worker["kind"] == "stage":
            outside = [rel for rel in scoped_targets
                       if not path_in_scope(rel, worker["scope"])]
            if outside:
                deny("Registered worker write is outside the protected task scope: "
                     + ", ".join(outside))
        elif worker["kind"] == "lite":
            claimed, _ = claim_files(root, locked_targets)
            if not claimed:
                deny(QUICKFIX_LIMIT_MSG)
        else:
            deny("Forge worker write admission returned an unknown grant kind.")
    else:
        guard_product_writes(write_targets, root,
                             lexical_targets=tool_name == "Bash")
# A heredoc whose ONLY consumer is a data sink (cat/tee/printf/echo writing
# to a file) is data, never argv: its body is dropped before the companion
# classification so a note that mentions the companion, or holds a quote or
# backtick that breaks shlex, is not mistaken for a launch. Every other shape
# keeps its body and is classified as before — a body fed to sh/node/xargs,
# through a pipe, or followed by more text CAN carry a launch (`sh <<EOF`,
# `cat <<EOF | sh`), so nothing outside this exact shape is stripped.
HEREDOC_SINK_ARGV0 = {"cat", "tee", "printf", "echo"}
HEREDOC_NOTE = re.compile(
    r"\A(?P<head>[^\n]*?)<<-?[ \t]*(?P<q>['\"]?)(?P<word>\w+)(?P=q)"
    r"(?P<tail>[^\n]*)\n(?P<body>.*?)\n(?P=word)[ \t]*\n?\Z", re.DOTALL)


def _strip_note_heredoc(text: str) -> str:
    match = HEREDOC_NOTE.match(text)
    if match is None:
        return text
    head, tail = match.group("head"), match.group("tail")
    argv0 = re.match(r"[ \t]*(?:\w+=\S*[ \t]+)*([^\s<>|;&]+)", head)
    if (
        argv0 is None
        or Path(argv0.group(1)).name not in HEREDOC_SINK_ARGV0
        or re.search(r"[|;&`]|\$\(", head + tail)
    ):
        return text
    return text[:match.start("body")] + text[match.end("body"):]


classify_command = _strip_note_heredoc(command)
literal_command = classify_command.replace("''", "").replace('""', "")
shell_shape = re.sub(
    r"\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_]*", "", literal_command)
try:
    shell_tokens = shlex.split(classify_command)
except ValueError:
    if (
        tool_name == "Bash"
        and (
            "--write" in shell_shape
            or
            re.search(r"\bcodex-companion(?:\.mjs)?\b", shell_shape)
        )
    ):
        deny(UNPARSEABLE_BASH_MSG)
    shell_tokens = []
compact_command = re.sub(r"[^a-z0-9]", "", shell_shape.lower())
has_companion = (
    re.search(r"\bcodex-companion(?:\.mjs)?\b", shell_shape) is not None
    or re.search(r"\$(?:\{)?(?=[A-Za-z_])[A-Za-z0-9_]*companion[A-Za-z0-9_]*",
                 classify_command, re.IGNORECASE) is not None
    or any(re.fullmatch(r"codex-companion(?:\.mjs)?", Path(token).name)
           for token in shell_tokens)
    or "codexcompanion" in compact_command
)
# No shell-capable pagers (less/more run "+!cmd" startup commands).
DISPLAY_SAFE_ARGV0 = {
    "rg", "grep", "cat", "head", "tail", "printf", "echo",
    "ls", "stat", "wc", "file", "md5", "shasum",
}


# Exec-capable or non-terminating options among DISPLAY_SAFE_ARGV0 tools,
# per tool: rg --pre / --pre-glob run a preprocessor command; tail -f / -F /
# --follow / --pid follow forever. Every other flag (grep -n, rg -i, tail -n,
# ls -la, head -c ...) only reads or formats, so a display command that
# merely MENTIONS the companion may carry them. Pager-style `+` tokens stay
# denied. Per tool, because `-f` is a harmless read flag for grep/stat.
DISPLAY_EXEC_OPTIONS = {
    "rg": ("--pre",),
    "tail": ("-f", "-F", "--follow", "--pid"),
}


def _display_safe(tokens):
    """Display command whose options cannot execute or hang."""
    denied = DISPLAY_EXEC_OPTIONS.get(Path(tokens[0]).name, ())
    return not any(
        t.startswith("+") or t.startswith(denied) for t in tokens[1:]
    )


def _has_active_shell_syntax(value: str) -> bool:
    """Shell syntax outside quotes (plus expansions inside double quotes)."""
    quote = None
    escaped = False
    for char in value:
        if escaped:
            escaped = False
        elif char == "\\" and quote != "'":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
            elif quote == '"' and char in "$`":
                return True
        elif char in "'\"":
            quote = char
        elif char in ";&|<>$`(){}\n*?~[]":
            return True
    return False


codex_match = (
    _active_codex_exec_match(command) or _wrapped_codex_exec(shell_tokens)
) if tool_name == "Bash" else None
codex_help = (
    len(shell_tokens) == 3
    and re.split(r"[/\\]", shell_tokens[0])[-1].lower()
    in {"codex", "codex.exe", "codex.cmd"}
    and shell_tokens[1:] in (["exec", "--help"], ["exec", "-h"])
    and not _has_active_shell_syntax(command)
)
quoted_display = (
    bool(shell_tokens) and Path(shell_tokens[0]).name in DISPLAY_SAFE_ARGV0
    and _display_safe(shell_tokens) and not _has_active_shell_syntax(command)
)
if codex_match and not codex_help and not quoted_display:
    deny(
        "Direct `codex exec` is off-contract. In Codex, use the host's native "
        "subagent tools with the descriptor from `./forge delegate <task-id>`; "
        "in Claude, use the Forge-managed codex-plugin-cc path."
    )


if tool_name == "Bash" and has_companion and not quoted_display:
    deny("Companion launches are off-contract. Use `./forge delegate <task-id>`; "
         "Codex dispatches its host-native subagent descriptor and Claude owns "
         "the codex-plugin-cc launch internally.")

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
