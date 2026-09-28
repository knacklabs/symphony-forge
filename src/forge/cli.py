"""The forge command. One table maps every command to the module function that runs it."""
import argparse
import ast
import importlib
import pkgutil
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

from forge import __version__, machine, repo
import forge

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
    ("work", "worker:work", True, "Run the configured worker on a task or fix",
     [_arg("item"), _arg("--note", metavar="TEXT", help="guide this round of work")]),
    ("ask", "ask:ask", False, "Ask Codex a read-only question about this checkout",
     [_arg("question"), _arg("--model", metavar="MODEL", help="Codex model for this answer"),
      _arg("--effort", metavar="EFFORT", help="reasoning effort for this answer")]),
    ("close", "close:close", True, "Close a task or fix by the close rule",
     [_arg("item"), _arg("--dismiss", type=int, action="append", metavar="N"),
      _arg("--because", action="append", metavar="FILE:LINE_REASON")]),
    ("merge", "merge:merge", False, "Merge a ready item when this repo allows it",
     [_arg("item")]),
    ("spec save", "records:spec_save", True, "Save a spec as a draft", [_arg("slug")]),
    ("spec confirm", "records:spec_confirm", True,
     "Mark a spec confirmed after the human confirms in chat",
     [_arg("slug"), _arg("--by", required=True, metavar="NAME")]),
    ("spec measure", "records:spec_measure", True,
     "Record the measured result in a confirmed spec's Success measure; it stays confirmed",
     [_arg("slug"), _arg("--result", required=True, metavar="TEXT")]),
    ("spec payback", "payback:payback", False,
     "Say whether a build pays back: build, smallest slice first, don't build or find out first",
     [_arg("--build-days", metavar="DAYS"), _arg("--day-rate", metavar="AMOUNT"),
      _arg("--hours-per-month", metavar="HOURS", help="hours saved per person each month"),
      _arg("--people", metavar="COUNT"), _arg("--hourly-rate", metavar="AMOUNT"),
      _arg("--revenue-per-month", metavar="AMOUNT"), _arg("--incident-cost", metavar="AMOUNT"),
      _arg("--incident-chance", metavar="CHANCE", help="the chance each month, from 0 to 1"),
      _arg("--confidence", choices=("measured", "estimated", "guessed"), default="guessed",
           help="weighs the value by 1, 1/2 or 1/5 (default: guessed)")]),
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
    "spec": "Save and confirm specs, weigh whether a build pays back, and record its result",
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
    declarations = []
    group_help = dict(GROUPS)
    for info in pkgutil.iter_modules(forge.__path__):
        if info.ispkg:
            continue
        source = Path(info.module_finder.path) / f"{info.name}.py"
        for node in ast.parse(source.read_text(encoding="utf-8")).body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            name = getattr(node.targets[0], "id", None)
            if name == "GROUP_HELP":
                for group, help_text in ast.literal_eval(node.value).items():
                    if group in group_help:
                        raise ValueError(f"group help declared twice: {group}")
                    group_help[group] = help_text
            elif name == "COMMANDS":
                for command in ast.literal_eval(node.value):
                    declarations.append((command["position"], command["words"],
                                         f"{info.name}:{command['run']}", command["changes_state"],
                                         command["help"], command["args"]))
    declarations.extend((position * 10, *row) for position, row in
                        enumerate(TABLE, start=7))
    for _, words, target, changes, text, arguments in sorted(declarations):
        name, _, sub = words.partition(" ")
        if sub and name not in groups:
            if name not in group_help:
                raise ValueError(f"group help missing: {name}")
            group = commands.add_parser(name, help=group_help[name], description=group_help[name])
            groups[name] = group.add_subparsers(required=True, title="commands")
        command = (groups[name] if sub else commands).add_parser(sub or name, help=text,
                                                                 description=text)
        for names, options in arguments:
            command.add_argument(*names, **options)
        # "handler", not "target": `forge read` has a positional argument named target.
        command.set_defaults(words=words, handler=target, changes=changes)
    return parser


def _run(argv: list[str] | None) -> int:
    args, extra = _parser().parse_known_args(argv)
    if extra and not args.words.startswith("hook "):
        repo.refuse(REFUSALS["usage"],
                    problem=f"forge {args.words}: unrecognized arguments: {' '.join(extra)}",
                    prog=f"forge {args.words}")
    args.args = extra
    if args.changes:
        repo.check_pin()
    module, name = args.handler.split(":")
    try:
        function = getattr(importlib.import_module(f"forge.{module}"), name, None)
    except ModuleNotFoundError as exc:
        if exc.name != f"forge.{module}":
            raise
        function = None
    if function is None:
        repo.refuse(REFUSALS["not_built"], command=args.words)
    try:
        result = function(args) or 0
        if result == 0 and args.words in ("init", "migrate", "sync", "next") and not getattr(args, "dry_run", False):
            machine.remember(Path.cwd())
        return result
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
