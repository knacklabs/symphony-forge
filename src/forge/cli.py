"""The forge command. One table maps every command to the module function that runs it."""
from __future__ import annotations

import argparse
import importlib
import subprocess
import sys
from collections.abc import Callable
from typing import Any, NoReturn

from forge import __version__, repo

REFUSALS = {
    "usage": ("{problem}.", "{prog} --help"),
    "not_built": ("forge {command} is not built yet.", "forge --help"),
    "failed": ("{command} failed: {problem}", "forge doctor"),
}


def _arg(*names: str, **options: Any) -> tuple[tuple[str, ...], dict[str, Any]]:
    return names, options


# Command words, "module:function", whether it changes state, help, arguments.
# A command that changes state refuses unless the installed Forge matches the forge.toml pin.
# Each function takes the parsed arguments and returns an exit code (None means 0).
TABLE = [
    ("init", "init:init", True,
     "Set up a new repo: forge.toml, the docs skeleton, the first commit, then sync", []),
    ("sync", "sync:sync", True,
     "Write the generated adapter files and git hooks for the pinned version", []),
    ("doctor", "doctor:doctor", False,
     "Check tools, versions, hooks, adapter drift and the named CI checks",
     [_arg("--fix", action="store_true",
           help="with Codex workers, install the pinned Codex SDK if it is missing or wrong")]),
    ("migrate", "migrate:migrate", True,
     "Move a client from the copied-in Forge to v1 in one pull request",
     [_arg("--dry-run", action="store_true", help="print the full plan and change nothing")]),
    ("next", "nextstep:next_step", False,
     "Say where things stand and give the exact next command", []),
    ("board", "board:board", False, "Write and open the plain-English board page",
     [_arg("--out", metavar="PATH", help="write the page here instead of .git/forge/board.html")]),
    ("story new", "story:new", True, "Start a story branch, worktree and story doc, or promote a fix",
     [_arg("key"), _arg("title", nargs="?"), _arg("--from-fix", metavar="FIX")]),
    ("story done", "story:done", True, "Record a finished story's outcome sentence and dates",
     [_arg("key"), _arg("outcome")]),
    ("read", "story:read", True, "Run the one cold read of a story doc or spec",
     [_arg("target", help="a story key or a spec slug"),
      _arg("--amended", action="store_true", help="record the one amendment")]),
    ("task start", "task:start", True, "Start a task in its own branch and worktree",
     [_arg("item", metavar="KEY/TASK")]),
    ("fix start", "task:fix_start", True,
     "Start a fix in its own branch and worktree, with a one-line why and done-when",
     [_arg("why"), _arg("--done", required=True, metavar="DONE_WHEN")]),
    ("fix allow-large", "task:allow_large", True,
     "Record the human's permission for this fix to go over the fix limit", [_arg("reason")]),
    ("work", "worker:work", True, "Run the configured worker on a task or fix", [_arg("item")]),
    ("close", "close:close", True, "Close a task or fix by the close rule",
     [_arg("item"), _arg("--dismiss", type=int, action="append", metavar="N"),
      _arg("--because", action="append", metavar="FILE:LINE_REASON")]),
    ("spec save", "records:spec_save", True, "Save a spec as a draft", [_arg("slug")]),
    ("spec confirm", "records:spec_confirm", True,
     "Mark a spec confirmed after the human confirms in chat",
     [_arg("slug"), _arg("--by", required=True, metavar="NAME")]),
    ("decision new", "records:decision_new", True, "Write a decision record", [_arg("slug")]),
    ("decision accept", "records:decision_accept", True,
     "Accept a decision after the human confirms in chat",
     [_arg("slug"), _arg("--by", required=True, metavar="NAME")]),
    ("roadmap add", "records:roadmap_add", True, "Add roadmap items from a confirmed spec",
     [_arg("spec")]),
    # Hooks get any extra arguments (git's pre-push remote, pr-check's flags) as args.args.
    ("hook context", "nextstep:context_hook", False,
     "Session start: print forge next and the story state", []),
    ("hook approval", "approval:hook", True,
     "After a plan or question tool: record approvals and count human touches", []),
    ("hook deny", "deny:hook", False,
     "Before a shell command: block destructive commands, --no-verify and gh pr merge", []),
    ("hook pre-commit", "githooks:pre_commit", False, "The git pre-commit rules", []),
    ("hook pre-push", "githooks:pre_push", False, "The git pre-push rules", []),
    ("hook pr-check", "prcheck:pr_check", False,
     "The required forge-pr-check, run from the base branch", []),
]

GROUPS = {
    "story": "Start a story, or record its outcome",
    "task": "Start a task",
    "fix": "Start a fix, or let it go over the fix limit",
    "spec": "Save and confirm specs",
    "decision": "Write and accept decisions",
    "roadmap": "Add roadmap items",
    "hook": "Internal: the one entry point that git hooks, host hooks and CI call",
}


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        repo.refuse(REFUSALS["usage"], problem=f"{self.prog}: {message}", prog=self.prog)


def _parser() -> _Parser:
    parser = _Parser(prog="forge",
                     description="Forge takes a story from approval to a merged pull request.")
    parser.add_argument("--version", action="version", version=f"forge v{__version__}")
    commands = parser.add_subparsers(required=True, title="commands")
    groups: dict[str, Any] = {}
    for words, target, changes, text, arguments in TABLE:
        name, _, sub = words.partition(" ")
        if sub:
            if name not in groups:
                group = commands.add_parser(name, help=GROUPS[name], description=GROUPS[name])
                groups[name] = group.add_subparsers(required=True, title="commands")
            command = groups[name].add_parser(sub, help=text, description=text)
        else:
            command = commands.add_parser(name, help=text, description=text)
        for names, options in arguments:
            command.add_argument(*names, **options)
        # "handler", not "target": `forge read` has a positional argument named target.
        command.set_defaults(words=words, handler=target, changes=changes)
    return parser


def _function(args: argparse.Namespace) -> Callable[[argparse.Namespace], int | None]:
    module, name = args.handler.split(":")
    try:
        found = importlib.import_module(f"forge.{module}")
    except ModuleNotFoundError as exc:
        if exc.name != f"forge.{module}":
            raise
        found = None
    function = getattr(found, name, None)
    if function is None:
        repo.refuse(REFUSALS["not_built"], command=args.words)
    return function


def _run(argv: list[str] | None) -> int:
    args, extra = _parser().parse_known_args(argv)
    if extra and not args.words.startswith("hook "):
        prog = f"forge {args.words}"
        repo.refuse(REFUSALS["usage"], problem=f"{prog}: unrecognized arguments: {' '.join(extra)}",
                    prog=prog)
    args.args = extra
    if args.changes:
        repo.check_pin()
    function = _function(args)
    try:
        return function(args) or 0
    except subprocess.CalledProcessError as exc:
        # A git (or gh) failure the command didn't expect: show what the tool said.
        repo.refuse(REFUSALS["failed"], command=" ".join(map(str, exc.cmd[:2])),
                    problem=(exc.stderr or exc.stdout or f"exit code {exc.returncode}").strip())


def main(argv: list[str] | None = None) -> int:
    # UTF-8 whatever the console code page (Windows pipes use a legacy one), so "→" stays "→".
    # Hook input too: a plan read in the wrong code page would hash to another digest.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    try:
        return _run(argv)
    except repo.Refused as refusal:
        print(refusal, file=sys.stderr)
        return refusal.code
    except KeyboardInterrupt:  # Ctrl-C: the human stopped it on purpose, so no traceback
        return 130
