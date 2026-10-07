"""The forge command. Each command is declared by its owning module."""
import argparse
import ast
import importlib.metadata
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, NoReturn

from forge import __version__, machine, repo
import forge

REFUSALS = {
    "usage": ("{problem}.", "{prog} --help"),
    "not_built": ("forge {command} is not built yet.", "forge --help"),
    "failed": ("{command} failed: {problem}", "forge doctor"),
}

# Names and display order are known without reading command implementations. Arguments,
# descriptions and handlers still belong to their owners.
ROUTES = {
    "init": "init", "sync": "sync", "doctor": "doctor", "test": "fasttest",
    "migrate": "migrate", "upgrade": "upgrade", "next": "nextstep", "board": "board", "lanes": "machine", "stop": "machine",
    "story new": "story", "story done": "story", "read": "story",
    "task start": "task", "fix start": "task", "fix allow-large": "task", "fix amend": "task",
    "work": "worker", "ask": "ask", "close": "close", "merge": "merge", "land": "land",
    "spec save": "records", "spec confirm": "records", "spec measure": "records",
    "spec payback": "payback", "decision new": "records", "decision accept": "records",
    "roadmap add": "records", "roadmap retire": "records",
    "hook context": "nextstep", "hook handoff": "nextstep", "hook approval": "approval",
    "hook deny": "deny", "hook pre-commit": "githooks", "hook pre-push": "githooks",
    "hook merge-roadmap": "sync", "hook pr-check": "prcheck",
}
GROUP_OWNERS = {"story": "story", "task": "task", "fix": "task", "spec": "records",
                "decision": "records", "roadmap": "records", "hook": "nextstep"}


class _Commands(argparse._SubParsersAction):
    """Argparse's normal choices and errors, with parsers built only when selected."""

    def __init__(self, *args: Any, prefix: str, load: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.prefix, self.load = prefix, load
        for words in ROUTES:
            if words.startswith(prefix):
                self._name_parser_map.setdefault(words[len(prefix):].split()[0], None)

    def _description(self, words: str) -> str:
        if words in ROUTES:
            return self._command(words)["help"]
        owner = GROUP_OWNERS.get(words)
        if not owner or words not in self.load(owner).get("GROUP_HELP", {}):
            raise ValueError(f"group help missing: {words}")
        return self.load(owner)["GROUP_HELP"][words]

    def _command(self, words: str) -> dict[str, Any]:
        return next(command for command in self.load(ROUTES[words])["COMMANDS"]
                    if command["words"] == words)

    def _get_subactions(self) -> list[Any]:
        # Only help needs the descriptions of siblings; running a command never reads them.
        return [self._ChoicesPseudoAction(name, [], self._description(self.prefix + name))
                for name in self._name_parser_map]

    def __call__(self, parser: Any, namespace: Any, values: Any, option_string: Any = None) -> None:
        name = values[0]
        if name in self._name_parser_map and self._name_parser_map[name] is None:
            words = self.prefix + name
            command = self._command(words) if words in ROUTES else None
            selected = _Parser(prog=f"{self._prog_prefix} {name}",
                               description=self._description(words) if command or
                               values[1:2] in (["--help"], ["-h"]) else None)
            if command:
                for names, options in command["args"]:
                    selected.add_argument(*names, **options)
                selected.set_defaults(words=words, handler=f"{ROUTES[words]}:{command['run']}",
                                      changes=command["changes_state"])
            else:
                selected.add_subparsers(action=_Commands, required=True, title="commands",
                                       prefix=words + " ", load=self.load)
            self._name_parser_map[name] = selected
        super().__call__(parser, namespace, values, option_string)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        repo.refuse(REFUSALS["usage"], problem=f"{self.prog}: {message}", prog=self.prog)


def _parser() -> _Parser:
    parser = _Parser(prog="forge",
                     description="Forge takes a story from approval to a merged pull request.")
    parser.add_argument("--version", action="version", version=f"forge v{__version__}")
    declarations: dict[str, dict[str, Any]] = {}

    def load(owner: str) -> dict[str, Any]:
        if owner not in declarations:
            source = Path(__file__).with_name(f"{owner}.py")
            # Evaluate only declarations, without importing the owner's runtime dependencies.
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            declarations[owner] = {
                target.id: eval(compile(ast.Expression(node.value), str(source), "eval"))
                for node in tree.body if isinstance(node, ast.Assign) for target in node.targets
                if isinstance(target, ast.Name) and target.id in ("COMMANDS", "GROUP_HELP")}
        return declarations[owner]

    parser.add_subparsers(action=_Commands, required=True, title="commands", prefix="", load=load)
    return parser


def _run(argv: list[str] | None) -> int:
    # A forge installed from this repo runs its old code, so run this checkout's; never another repo's.
    top = repo.run("git", "rev-parse", "--show-toplevel").stdout.strip()
    url = json.loads(next((d.read_text("direct_url.json") or "{}" for d in importlib.metadata.distributions(name="symphony-forge")), "{}")).get("url") or ""
    made = urllib.request.url2pathname(urllib.parse.urlparse(url).path) if url.startswith("file:") else ""
    src = str(Path(top, "src"))
    forwarding = (top and made and os.environ.get("FORGE_FROM_CHECKOUT") != src
                  and Path(forge.__file__).resolve().parent != Path(src, "forge"))
    # Read the folders directly: a hook's GIT_DIR must not answer for both of them.
    if forwarding and repo._common_path(top) == repo._common_path(made):
        print(f"Running this checkout's code in {Path(src, 'forge')}, not the installed Forge.", file=sys.stderr)
        return subprocess.run([sys.executable, "-c", "from forge.cli import main; raise SystemExit(main())", *(argv or sys.argv[1:])],
                              env={**os.environ, "PYTHONPATH": src, "FORGE_FROM_CHECKOUT": src}).returncode
    args, extra = _parser().parse_known_args(argv)
    if extra and not args.words.startswith("hook "):
        repo.refuse(REFUSALS["usage"],
                    problem=f"forge {args.words}: unrecognized arguments: {' '.join(extra)}",
                    prog=f"forge {args.words}")
    args.args = extra
    if args.changes and not args.words.startswith("hook "):
        repo.check_pin(item=getattr(args, "item", None) or "", words=args.words)
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
        with repo.command_cache():
            return _run(argv)
    except repo.Refused as refusal:
        print(refusal, file=sys.stderr)
        return refusal.code
    except KeyboardInterrupt:  # Ctrl-C: the human stopped it on purpose, so no traceback
        return 130
