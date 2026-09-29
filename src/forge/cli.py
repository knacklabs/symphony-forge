"""The forge command. Each command is declared by its owning module."""
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
    group_help = {}
    for info in pkgutil.iter_modules(forge.__path__):
        if info.ispkg:
            continue
        source = Path(info.module_finder.path) / f"{info.name}.py"
        names = {target.id for node in ast.parse(source.read_text(encoding="utf-8")).body
                 if isinstance(node, ast.Assign) for target in node.targets
                 if isinstance(target, ast.Name)}
        if not names.intersection({"COMMANDS", "GROUP_HELP"}):
            continue
        module_name = info.name
        module = importlib.import_module(f"forge.{module_name}")
        for group, help_text in getattr(module, "GROUP_HELP", {}).items():
            if group in group_help:
                raise ValueError(f"group help declared twice: {group}")
            group_help[group] = help_text
        for command in getattr(module, "COMMANDS", []):
            declarations.append((command["position"], command["words"],
                                 f"{module_name}:{command['run']}", command["changes_state"],
                                 command["help"], command["args"]))
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
