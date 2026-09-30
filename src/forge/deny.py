"""The deny hook, run before every shell command on both hosts. It blocks destructive commands,
skipped git hooks and merges. Exit code 2 blocks the command and shows the refusal to the agent.

The command is split into words the way the shell would, so every spelling of an option counts
(`rm -fr`, `rm -r -f`, `rm --recursive --force`) and quoted text such as a commit message doesn't.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from collections.abc import Iterator

from forge.repo import refuse

REFUSALS = {
    "payload": ("The hook input is not a JSON object, so Forge cannot check the command.",
                "forge doctor"),
    "destructive": ('Forge blocks "{found}" because it can destroy work that cannot be recovered.',
                    "ask the human to run it in their own terminal if it is really needed"),
    "no_verify": ('Forge blocks "{found}" because the git hooks must run on every commit and push.',
                  "run it again without skipping the hooks, and fix what they report"),
    "merge": ('Forge blocks "{found}" because only a human merges a pull request.',
              "forge close <item>, then ask the human to merge"),
}

OPERATORS = set(";&|()<>")
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "eval"}
ALONE_BREAKERS = OPERATORS | set("`'\\\n{}=")
CONFIG_GETS ={"--get", "--get-all", "--get-regexp"}
CONFIG_SCOPES = {"--global", "--local", "--system", "--worktree"}


def hook(args: argparse.Namespace) -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except ValueError:
        payload = None
    if not isinstance(payload, dict):  # fail closed: a command Forge can't read doesn't run
        refuse(REFUSALS["payload"], code=2)
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if isinstance(command, list):  # ponytail: an argv-shaped command, should a host send one
        command = shlex.join(map(str, command))
    command = str(command or "")
    # A command that is only rm: nothing before it can change the folder or a variable it uses.
    alone = not set(command) & ALONE_BREAKERS
    for words in _commands(command):
        for i, word in enumerate(words):  # a program may follow sudo, env, xargs or find -exec
            rule = _rule(word.rsplit("/", 1)[-1], words[i + 1:], alone and i == 0)
            if rule:
                refuse(REFUSALS[rule], code=2, found=" ".join(words))


def _commands(text: str, depth: int = 0) -> Iterator[list[str]]:
    """Each simple command's words, including those run by sh -c, eval, $(...) and backticks."""
    text = text.replace("\n", ";").replace("`", "$(")
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        words = list(lexer)
    except ValueError:  # an unfinished quote, say in a heredoc: plain words still show programs
        words = [word.strip("'\"") for word in text.split()]
    command: list[str] = []
    for word in [*words, ";"]:
        if word and set(word) <= OPERATORS:
            yield from _run_by(command, depth)
            yield command
            command = []
        else:
            command.append(word)
            if "$(" in word and depth < 4:  # a quoted $(...) still runs
                yield from _commands(word, depth + 1)


def _run_by(command: list[str], depth: int) -> Iterator[list[str]]:
    """The commands in the script that a shell or eval in this command runs."""
    for i, word in enumerate(command):
        if word.rsplit("/", 1)[-1] in SHELLS and depth < 4:
            yield from _commands(" ".join(command[i + 1:]), depth + 1)
            return


def _rule(program: str, args: list[str], alone: bool = False) -> str | None:
    """The rule a program and its arguments break, if any. `alone`: this is the whole command."""
    if "--no-verify" in args:
        return "no_verify"
    short = _short(args)
    if program == "rm" and ({"r", "R"} & short or "--recursive" in args) and (
            "f" in short or "--force" in args) and not (alone and _in_temp(args)):
        return "destructive"
    if program == "git":
        sub, rest = _subcommand(args)
        # -c core.hooksPath=... (or --config-env) turns every git hook off, like --no-verify.
        # Reading the value changes nothing, so only the options before `config` count then.
        checked = args[:len(args) - len(rest)] if sub == "config" and _config_read(rest) else args
        if any("hookspath" in a.lower() for a in checked):
            return "no_verify"
        short = _short(rest)
        if sub == "commit" and "n" in short:  # -n is commit's short --no-verify
            return "no_verify"
        if sub == "reset" and "--hard" in rest:
            return "destructive"
        # --force, --force-with-lease, --force-if-includes, -f, and a +refspec all force.
        if sub == "push" and ("f" in short or any(a.startswith(("--force", "+")) for a in rest)):
            return "destructive"
    if (program == "terraform" and {"destroy", "-destroy"} & set(args)
            or program == "kubectl" and "delete" in args):
        return "destructive"
    if program == "gh" and any(args[i:i + 2] == ["pr", "merge"] for i in range(len(args))):
        return "merge"
    return None


def _in_temp(args: list[str]) -> bool:
    """Whether rm names targets and each one, a literal absolute path with no .. in it, resolves
    inside the system temp folder."""
    end = args.index("--") if "--" in args else len(args)
    targets = [a for a in args[:end] if not a.startswith("-")] + args[end + 1:]
    roots = [os.path.realpath(r) for r in (os.environ.get("TMPDIR"), "/tmp", "/private/tmp") if r]
    for target in targets:
        if (not os.path.isabs(target) or set(target) & set("$`*?[]{}")
                or ".." in target.replace("\\", "/").split("/")):
            return False  # left for the shell to expand, or climbing out: Forge can't tell where
        path = os.path.realpath(target)
        if not any(path != root and _under(path, root) for root in roots):
            return False
    return bool(targets)  # no targets: xargs or find supplies them


def _under(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:  # on Windows, a path on another drive
        return False


def _config_read(args: list[str]) -> bool:
    """Whether git config only reads a value: --get, or a key with no value."""
    options = {a for a in args if a.startswith("-")}
    keys = [a for a in args if not a.startswith("-")]
    if options & CONFIG_GETS:
        return options <= CONFIG_GETS | CONFIG_SCOPES and 1 <= len(keys) <= 2
    return options <= CONFIG_SCOPES and len(keys) == 1


def _short(args: list[str]) -> set[str]:
    """The letters of short options, so -fr, -r -f and -Rf read alike."""
    return {letter for arg in args if arg[:1] == "-" and arg[:2] != "--" for letter in arg[1:]}


def _subcommand(args: list[str]) -> tuple[str, list[str]]:
    """git's subcommand and its arguments, after options such as -C <dir> and -c <key=value>."""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in ("-C", "-c") else 1
    return (args[i], args[i + 1:]) if i < len(args) else ("", [])


COMMANDS = [{
    "words": "hook deny", "run": "hook", "changes_state": False,
    "help": "Before a shell command: block destructive commands, --no-verify and gh pr merge",
    "args": [], "position": 260,
    "listing": "| `forge hook deny` | Before each shell command: blocks destructive commands, `--no-verify` and `gh pr merge` |",
}]
