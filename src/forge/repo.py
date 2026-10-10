"""Shared seams: git, forge.toml, the roadmap, the version pin, refusals and `.factory` state.

Refusal convention: every module declares one REFUSALS table of (problem, next command)
templates and raises its entries with refuse(). The CLI prints the problem, then a
`Next:` line, and exits non-zero.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

from forge import __version__

# Every Forge command loads this shared runtime; child processes consume the recorded lock.
os.environ["UV_FROZEN"] = "1"
# Where a repo keeps its tests: a test folder anywhere, or a test file next to its code.
TEST_PATHS = [":(glob)**/test*/**", ":(glob)**/*.test.*", ":(glob)**/*.spec.*",
              ":(glob)**/test_*.py", ":(glob)**/*_test.py"]
CACHES = {".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}

REFUSALS = {
    "no_repo": ("This folder is not inside a git repository.", "cd <your repo>"),
    "missing_tool": ("{tool} is not installed or not on PATH.", "forge doctor"),
    "no_github": ("GitHub did not answer. Rerun the command.", ""),
    "no_config": ("This repo has no forge.toml.", "forge init"),
    "bad_config": ("forge.toml is not usable: {problem}.", "forge doctor"),
    "models": ("forge.toml's [models] table is not usable: {problem}.",
               "ask your agent to fix forge.toml's [models] table"),
    "pin": (
        "Forge {installed} is installed, but this repo pins {pinned}.",
        "uv tool install git+https://github.com/knacklabs/symphony-forge@{pinned}",
    ),
    "pin_elsewhere": ("{item} is checked out in {folder}, which pins Forge {installed}; "
                      "this folder pins {pinned}.", "cd {folder}, then forge {words} {item}"),
    "bad_roadmap": ("plans/roadmap.json is not usable: {problem}.", "git checkout -- plans/roadmap.json"),
    "bad_item": ("{item!r} is not a story key, a KEY/TASK task or a fix name.", "forge next"),
    "bad_state": ("{path} is not usable: {problem}.", "git checkout -- {path}"),
    "default_branch": (
        "Forge changes nothing on {branch}; work happens on a story, task or fix branch.",
        'forge fix start "<why>" --done "<done when>"',
    ),
}


class Refused(Exception):
    """A refusal: the problem in one sentence, then the next command, unless the sentence ends
    with it."""

    def __init__(self, problem: str, next_step: str, code: int = 1,
                 entry: tuple[str, str] | None = None):  # the REFUSALS entry refuse() raised
        super().__init__(f"{problem}\nNext: {next_step}" if next_step else problem)
        self.code, self.entry = code, entry


def refuse(entry: tuple[str, str], code: int = 1, **values: Any) -> NoReturn:
    """Raise one entry of a module's REFUSALS table, filled in with values."""
    problem, next_step = entry
    raise Refused(problem.format(**values), next_step.format(**values), code, entry)


# --- git -------------------------------------------------------------------------------


_command_cache: dict[tuple, Any] | None = None


@contextmanager
def command_cache():
    """Repository facts and worker history live only for this command, never the next one."""
    global _command_cache
    previous, _command_cache = _command_cache, {}
    try:
        yield
    finally:
        _command_cache = previous


def _common_path(cwd: str | os.PathLike[str] | None) -> Path:
    """Identify linked worktrees without another git process."""
    top = Path(cwd or Path.cwd()).resolve()
    for folder in (top, *top.parents):
        dot = folder / ".git"
        if dot.is_file():
            dot = (folder / dot.read_text(encoding="utf-8").strip().removeprefix("gitdir: ")).resolve()
        if dot.is_dir():
            common = dot / "commondir"
            return (dot / common.read_text(encoding="utf-8").strip()).resolve() if common.is_file() else dot.resolve()
    return top


def command_fact(kind: Any, cwd: str | os.PathLike[str] | None, read):
    key = (kind, _common_path(cwd))
    if _command_cache is None:
        return read()
    if key not in _command_cache:
        _command_cache[key] = read()
    return _command_cache[key]


def run(*args: str, cwd: str | os.PathLike[str] | None = None,
        input: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run a program without a shell. It is looked up on PATH, so .cmd shims work on Windows."""
    exe = shutil.which(args[0])
    if exe is None:
        refuse(REFUSALS["missing_tool"], tool=args[0])
    # An empty stdin, never the terminal: a prompt would hang instead of failing.
    def execute():
        return subprocess.run([exe, *args[1:]], cwd=cwd, input=input or "", capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              # Git hooks need the caller's worker identity.
                              env=os.environ if args[0] == "git" else {**os.environ, "FORGE_WORKER": "1"})
    if args == ("git", "rev-parse", "--path-format=absolute", "--git-common-dir"):
        return command_fact("common directory", cwd, execute)
    done = _github_read(args, execute) if args[0] == "gh" else execute()
    if _command_cache is not None and done.returncode == 0 and args[:2] == ("git", "fetch"):
        key = ("landed ref", _common_path(cwd))
        if key in _command_cache and not _command_cache[key].startswith("origin/"):
            del _command_cache[key]  # A first fetch can create the previously absent remote ref.
    if _command_cache is not None and done.returncode == 0 and args[:3] == ("git", "remote", "set-head"):
        for kind in ("default branch", "landed ref"):
            _command_cache.pop((kind, _common_path(cwd)), None)
    if (_command_cache is not None and done.returncode == 0 and args[0] == "git"
            and args[1] in ("fetch", "merge", "switch", "checkout")):
        common = _common_path(cwd)
        for key in list(_command_cache):
            if isinstance(key[0], tuple) and key[0][0] == "commits" and key[1] == common:
                del _command_cache[key]
    return done


def _github_read(args: tuple[str, ...], execute) -> subprocess.CompletedProcess[str]:
    """Retry reads only: replaying a write after an unreadable receipt could duplicate it."""
    api = args[1:2] == ("api",)
    read = (args[1:3] in (("pr", "list"), ("pr", "view"), ("pr", "checks"),
                         ("run", "list"), ("run", "view"),
                         ("release", "list"), ("release", "view")))
    if api:
        # gh infers POST from fields; our GraphQL query is a read despite that POST.
        read = (not any(flag in args for flag in ("-f", "-F", "--field", "--raw-field", "--input"))
                or ("graphql" in args and any(re.match(r"query=\s*(?:\{|query\b)", arg)
                                              for arg in args)))
        if "--method" in args or "-X" in args:
            flag = "--method" if "--method" in args else "-X"
            read = args[args.index(flag) + 1].upper() == "GET"
    if not read:
        return execute()
    jq = args[args.index("--jq") + 1] if "--jq" in args else None
    structured = api or "--json" in args
    for pause in (1, 2, 4, None):
        done = execute()
        said = done.stderr + done.stdout
        if done.returncode and re.search(r"\bHTTP\s+(?:401|403|404)\b", said, re.I):
            return done
        unreadable = False
        if structured and done.returncode == 0:
            text = done.stdout.strip()
            try:
                if ((jq is None and api and "--paginate" in args and "--slurp" not in args)
                        or (jq is not None and jq.endswith("[]"))):
                    decoder = json.JSONDecoder()
                    while text:
                        _, end = decoder.raw_decode(text)
                        text = text[end:].lstrip()
                elif jq is None:
                    json.loads(text)
                else:
                    unreadable = text.startswith("<")
            except ValueError:
                unreadable = True
        transient = unreadable or (structured and (done.stdout.lstrip().startswith("<")
                                                   or done.stderr.lstrip().startswith("<"))) or (done.returncode and (
            re.search(r"\bHTTP\s+5\d\d\b", said, re.I)
            or re.search(r"\bunexpected EOF\b|\binvalid character\b", said, re.I)
            or "looking for beginning of value" in said
            or "unexpected end of JSON input" in said))
        if not transient:
            return done
        if pause is None:
            return subprocess.CompletedProcess(done.args, 1, "",
                                               REFUSALS["no_github"][0] + "\n")
        time.sleep(pause)


def git(*args: str, cwd: str | os.PathLike[str] | None = None) -> str:
    """Run git and return its trimmed output. A failure raises CalledProcessError."""
    done = run("git", *args, cwd=cwd)
    if done.returncode:
        raise subprocess.CalledProcessError(done.returncode, ["git", *args], done.stdout, done.stderr)
    return done.stdout.strip()


def commit_log(top: Path, base: str, head: str = "HEAD") -> list[tuple[str, str, list[str]]]:
    """Snapshot worker history once; close's later bookkeeping commits add no worker evidence."""
    def key(ref):
        return ("commits", top.resolve(), base, ref)

    def read():
        tip = git("rev-parse", head, cwd=top)
        return command_fact(key(tip), top, lambda: select(tip))

    def select(tip):
        commits = git("rev-list", "--no-merges", f"{base}..{tip}", cwd=top).splitlines()
        # Commit contents are immutable even when a fetch changes range membership.
        records = command_fact(("commit records", top.resolve()), top, dict)
        missing = [sha for sha in commits if sha not in records]
        log = (git("log", "--no-walk", "--format=%x00%x00%H%x00m%B",
                   "--name-only", "-z", *missing, cwd=top) if missing else "")
        for record in log.split("\0\0"):
            if not record:
                continue
            sha, message, *paths = record.lstrip("\0").split("\0", 2)
            files = [p for p in (paths[0].removeprefix("\n").split("\0") if paths else []) if p]
            records[sha] = (sha, message.removeprefix("m"), files)
        return [records[sha] for sha in commits]
    return command_fact(key(head), top, read)


def root(cwd: str | os.PathLike[str] | None = None) -> Path:
    """The top of the current checkout (a worktree's own folder inside a worktree)."""
    done = run("git", "rev-parse", "--show-toplevel", cwd=cwd)
    if done.returncode:
        refuse(REFUSALS["no_repo"])
    return Path(done.stdout.strip())


def current_branch(cwd: str | os.PathLike[str] | None = None) -> str:
    """The checked-out branch, or "" on a detached HEAD."""
    return git("branch", "--show-current", cwd=cwd)


def default_branch(cwd: str | os.PathLike[str] | None = None) -> str:
    # ponytail: origin/HEAD, else "main". A remote-less repo on another name needs origin/HEAD set.
    done = command_fact("default branch", cwd, lambda: run(
        "git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=cwd))
    return done.stdout.strip().removeprefix("origin/") if done.returncode == 0 else "main"


def forge_dir(cwd: str | os.PathLike[str] | None = None) -> Path:
    """`.git/forge/`, shared by every worktree, for logs and the board. Never committed."""
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd)
    path = Path(common) / "forge"
    path.mkdir(exist_ok=True)
    return path


def work_log(top: Path, item: str) -> Path:
    """The item's work log in `.git/forge/`, where its worker's progress goes."""
    return forge_dir(top) / f"work-{item.replace('/', '-')}.log"


def record_timing(top: Path, item: str, step: str, start: str, clock: float,
                  outcome: str, model: dict[str, str] | None = None) -> None:
    """Append a best-effort timing in the shared, uncommitted Git directory."""
    line = {"item": item, "round": (read_state(item, top) or {}).get("round", 0),
            "step": step, "start": start,
            "seconds": round(time.monotonic() - clock, 3), "outcome": outcome}
    if model:
        line.update({key: model[key] for key in ("model", "effort") if key in model})
    try:
        with (forge_dir(top) / "timings.jsonl").open("a", encoding="utf-8") as out:
            out.write(json.dumps(line) + "\n")
    except OSError:
        pass  # Timing is diagnostic; a full or unwritable Git directory must not fail the command.


def record_event(top: Path, item: str, event: str, **fields: Any) -> str:
    """Write an occurrence once; consumers use its random id, never its text or timestamp."""
    identity = str(uuid.uuid4())
    line = {"id": identity, "item": item, "event": event, "at": now(),
            "round": (read_state(item, top) or {}).get("round", 0), **fields}
    from forge import codex
    path = forge_dir(top) / "events.jsonl"
    with codex._one_at_a_time(path.with_suffix(".lock")), path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(line) + "\n")
    return identity


def record_progress(top: Path, item: str, run_id: str, **fields: Any) -> None:
    """Coalesce a run's live updates into at most one record per ten seconds."""
    from forge import codex
    path = forge_dir(top) / "events.jsonl"
    with codex._one_at_a_time(path.with_suffix(".lock")):
        rows = path.read_text(encoding="utf-8").splitlines()
        parsed = [json.loads(row) for row in rows]
        previous = next((n for n in range(len(rows) - 1, -1, -1)
                         if parsed[n].get("run_id") == run_id and
                         parsed[n].get("event") == "progress"), None)
        start = next(row for row in parsed if row.get("id") == run_id)
        # ponytail: rewrite this diagnostic log to coalesce; split progress out if it grows large.
        line = {"id": str(uuid.uuid4()), "item": item, "event": "progress", "run_id": run_id,
                "kind": "progress", "round": start.get("round"), "at": now(), **fields}
        if previous is not None:
            old = parsed[previous]
            line = {**old, **line}
            if (datetime.fromisoformat(now()) - datetime.fromisoformat(old["recorded_at"])).total_seconds() < 10:
                rows[previous] = json.dumps({**line, "id": old["id"]})
            else:
                rows.append(json.dumps({**line, "recorded_at": now()}))
        else:
            rows.append(json.dumps({**line, "recorded_at": now()}))
        temp = path.with_suffix(".new")
        temp.write_text("\n".join(rows) + "\n", encoding="utf-8")
        for wait in (0.05,) * 40 + (0,):  # Windows readers can briefly hold the events file open.
            try:
                return os.replace(temp, path)
            except PermissionError:
                if not wait:
                    temp.unlink(missing_ok=True)
                    refuse(codex.REFUSALS["record"], record=path)
                time.sleep(wait)


def worker_step(name: str, inputs: dict[str, Any]) -> str:
    """Describe only the tool's action, never its output or message contents."""
    actions = {"webSearch": "searching the web", "imageGeneration": "generating an image",
               "sleep": "waiting", "subAgentActivity": "working with a helper",
               "enteredReviewMode": "reviewing", "exitedReviewMode": "finishing the review",
               "contextCompaction": "compacting context"}
    if name in actions:
        return actions[name]
    command = inputs.get("command")
    if isinstance(command, str):
        return "committing" if re.search(r"\bgit\s+commit\b", command) else "running " + " ".join(command.split())
    path = inputs.get("file_path") or inputs.get("path")
    return ("editing " if name in ("Edit", "Write", "fileChange") else "reading ") + " ".join(str(path).split()) if path else "using " + name


def claude_output(top: Path, item: str, run_id: str, event: dict[str, Any]) -> str:
    """Read the same tool actions and result diagnostics for Claude workers and readers."""
    if event.get("type") == "system" and event.get("subtype") == "init":
        record_progress(top, item, run_id, **{key: event[key] for key in ("model", "effort") if key in event})
    response = event.get("response") or {}
    if event.get("type") == "control_response" and response.get("request_id") == "forge-live-settings":
        applied = (response.get("response") or {}).get("applied") or {}
        record_progress(top, item, run_id, **{key: applied[key] for key in ("model", "effort") if key in applied})
    content = (event.get("message") or {}).get("content", [])
    for tool in content:
        if isinstance(tool, dict) and tool.get("type") == "tool_use":
            record_progress(top, item, run_id,
                            step=worker_step(tool.get("name", "tool"), tool.get("input") or {}))
    if event.get("type") == "result":
        return str(event.get("result") or "\n".join(
            [str(event.get("subtype", "")), *event.get("errors", [])])) + "\n"
    return "".join(c.get("text", "") + "\n" for c in content
                   if isinstance(c, dict) and c.get("type") == "text")


@contextmanager
def record_run(top: Path, item: str, kind: str, **fields: Any):
    """Keep starts and ends even for a run entirely between two board refreshes."""
    identity = record_event(top, item, "run start", kind=kind, **fields)
    result = {"outcome": "failed", "run_id": identity}
    if "round" in fields:
        result["round"] = fields["round"]
    try:
        yield result
    finally:
        record_event(top, item, "run end", kind=kind, **result)


# --- forge.toml, the pin and the roadmap -----------------------------------------------

KEYS = {"version": str, "repo": str, "stage": str, "workers": str, "test": str, "fast_test": str,
        "signoff": str, "runner": str,
        "merge": str, "checks": list, "interfaces": list, "models": dict}
# A client repo without a stage counts as live: prototype rules never reach an app by default.
DEFAULTS = {"repo": "client", "stage": "live", "workers": "codex", "test": "", "fast_test": "",
            "signoff": "", "runner": "ubuntu-latest",
            "merge": "human", "checks": [], "interfaces": [], "models": {}}
CHOICES = {"repo": ("client", "forge-source"), "stage": ("live", "prototype"),
           "workers": ("claude", "codex", "split"), "merge": ("agent", "human")}
# signoff pins the client's sign-off record: a decision directly under docs/decisions whose slug
# ends in client-signoff, as `forge decision new` names it and the old Forge accepted it.
SIGNOFF = re.compile(r"docs/decisions/[0-9]{4,}-[a-z0-9-]*client-signoff\.md")
# A release, and nothing else: sync writes the pin into the hooks' shell launcher.
VERSION = re.compile(r"v?[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.]+)?")
# The kinds of work in forge.toml's [models] table. Each has a model and an effort (a review's
# effort is optional); build, fix, lite and explore may add their subagents' model and effort,
# as a pair.
# The cold read and design work have one entry per family.
KINDS = ("build", "fix", "lite", "explore", "grill", "design", "review")
SUBAGENTS = ("subagents", "subagent_effort")
FAMILIES = ("codex", "claude")
# A worker's models when forge.toml has no entry for its family, so Forge always names them.
WORKER_DEFAULTS = {"claude": {"model": "claude-opus-5-5", "effort": "medium"},
                   "codex": {"model": "gpt-6.1-sol", "effort": "medium"}}
DESIGN_DEFAULTS = {"claude": {"model": "claude-opus-5-5", "effort": "high"},
                   "codex": {"model": "gpt-6.1-sol", "effort": "high"}}


def config(top: Path | None = None) -> dict[str, Any]:
    """Read and check forge.toml at the top of the checkout; missing keys get their defaults."""
    path = (top or root()) / "forge.toml"
    if not path.is_file():
        refuse(REFUSALS["no_config"])
    try:
        return _config_text(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        refuse(REFUSALS["bad_config"], problem=exc)


def default_config(top: Path) -> dict[str, Any]:
    """Fetch and read only the default branch's config for merge permission and checks."""
    default = default_branch(top)
    git("fetch", "-q", "origin", default, cwd=top)
    found = run("git", "show", f"origin/{default}:forge.toml", cwd=top)
    if found.returncode:
        refuse(REFUSALS["no_config"])
    return _config_text(found.stdout)


def merge_setting(top: Path) -> str:
    """Use agent merges for client prototypes until the fetched default branch signs off."""
    cfg = default_config(top)
    return "agent" if is_prototype(top, cfg, (f"origin/{default_branch(top)}",)) else cfg["merge"]


def is_prototype(top: Path, cfg: dict[str, Any] | None = None, refs: tuple[str, ...] = ()) -> bool:
    """Prototype rules apply only to a client repo whose stage is prototype and whose sign-off
    record isn't accepted: exactly the record forge.toml's signoff pins, or, with none pinned, a
    decision whose slug ends in client-signoff. The record is looked for in these refs, or with none
    given, in this checkout and on the default branch."""
    cfg = cfg if cfg is not None else config(top)
    if cfg["repo"] != "client" or cfg["stage"] != "prototype":
        return False
    from forge import story

    pinned = cfg["signoff"]

    def wanted(name: str) -> bool:
        return name == pinned if pinned else name.endswith("client-signoff.md")

    texts = [] if refs else [path.read_text(encoding="utf-8")
                             for path in top.glob("docs/decisions/*.md")
                             if wanted(path.relative_to(top).as_posix())]
    for ref in refs or (story.landed_ref(top),):
        names = git("ls-tree", "-r", "--name-only", ref, "--", "docs/decisions", cwd=top).splitlines()
        texts += [story.show(top, ref, name) or "" for name in names if wanted(name)]
    return not any(re.search(r"^status:\s*[\"']?accepted\b", text.split("---")[1], re.M)
                   for text in texts if text.startswith("---"))


def _config_text(text: str) -> dict[str, Any]:
    try:
        data = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        refuse(REFUSALS["bad_config"], problem=exc)
    problem = _config_problem(data)
    if problem:
        refuse(REFUSALS["bad_config"], problem=problem)
    problem = _models_problem(data.get("models", {}))
    if problem:
        refuse(REFUSALS["models"], problem=problem)
    return {**DEFAULTS, **data}


def ready_path(item: str, top: Path) -> Path:
    """An item's uncommitted ready receipt in the shared git directory."""
    state_path(item)  # Validate before using the item in a path.
    return forge_dir(top) / "ready" / f"{item}.json"


def models(cfg: dict[str, Any], kind: str, family: str) -> dict[str, str]:
    """One kind's entry for a family ("codex" or "claude") from forge.toml's [models] table: its
    own entry, or a single entry whose model is that family's; {} when the kind has none for it."""
    if kind == "explore" and kind not in cfg["models"]:
        kind = "lite"
    chosen = cfg["models"].get(kind) or {}
    if "model" not in chosen:
        return chosen.get(family) or {}
    # ponytail: gpt models are Codex's and every other model Claude's; name the family's entry
    # when another Codex model family arrives.
    return chosen if chosen["model"].startswith("gpt") == (family == "codex") else {}


def user_facing(cfg: dict[str, Any], row: dict[str, str]) -> bool:
    """A User-facing row is design work in clients, or when the source repo opts into split."""
    return (cfg["repo"] == "client" or cfg["workers"] == "split") and row.get(
        "User-facing", "").lower() in ("yes", "true")


def worker_models(cfg: dict[str, Any], kind: str, family: str) -> dict[str, str]:
    """A worker's models for this kind: forge.toml's entry for the family, else Forge's default."""
    return models(cfg, kind, family) or WORKER_DEFAULTS[family]


def worker(cfg: dict[str, Any], kind: str, design: bool) -> tuple[str, dict[str, str], str]:
    """Who builds an item, with which models, and why: workers = codex or claude puts everything on
    that tool, and split puts user-facing (design) work on Claude and the rest on Codex. Design
    work uses the family's design model. forge work and forge next both ask this."""
    family = cfg["workers"] if cfg["workers"] != "split" else "claude" if design else "codex"
    chosen = design_models(cfg, family) if design else worker_models(cfg, kind, family)
    why = (("it is user-facing" if design else "it isn't user-facing") + " (workers = split)"
           if cfg["workers"] == "split" else f"workers = {family}"
           + (", with the design model as it is user-facing" if design else ""))
    return family, chosen, why


def design_models(cfg: dict[str, Any], family: str) -> dict[str, str]:
    """The design model for a family, including the default in older repos."""
    return cfg["models"].get("design", {}).get(family, DESIGN_DEFAULTS[family])


def _models_problem(table: Any) -> str:
    if not isinstance(table, dict):
        return "models must be a table"
    for kind, chosen in table.items():
        if kind not in KINDS:
            return f"{kind} is not a kind of work; the kinds are {', '.join(KINDS[:-1])} and {KINDS[-1]}"
        if not isinstance(chosen, dict):
            return f"models.{kind} must be a table"
        per_family = kind in ("grill", "design") or any(family in chosen for family in FAMILIES)
        wrong = [key for key in chosen if key not in FAMILIES] if per_family else []
        if wrong:
            return (f"models.{kind} has one entry per family, codex and claude, "
                    f"so it can't set {wrong[0]}")
        entries = ({f"{kind}.{family}": entry for family, entry in chosen.items()}
                   if per_family else {kind: chosen})
        for name, entry in entries.items():
            if not isinstance(entry, dict):
                return f"models.{name} must be a table"
            for key, value in entry.items():
                if key not in ("model", "effort", *(SUBAGENTS if kind in ("build", "fix", "lite", "explore") else ())):
                    return f"models.{name} can't set {key}"
                if not isinstance(value, str):
                    return f"models.{name}.{key} must be a string"
            for key in ("model",) if kind == "review" else ("model", "effort"):
                if key not in entry:
                    return f"models.{name} has no {key}"
            if (SUBAGENTS[0] in entry) != (SUBAGENTS[1] in entry):
                return f"models.{name} sets only one of subagents and subagent_effort; set both or neither"
    return ""


def _config_problem(data: dict[str, Any]) -> str:
    if "version" not in data:
        return "it has no version"
    for key, value in data.items():
        kind = KEYS.get(key)
        if kind is None:
            return f"{key!r} is not a forge.toml key"
        if kind is str and not isinstance(value, str):
            return f"{key} must be a string"
        if kind is list and not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
            return f"{key} must be a list of strings"
        if key in CHOICES and value not in CHOICES[key]:
            return f"{key} must be one of {', '.join(CHOICES[key])}"
        if key == "version" and not VERSION.fullmatch(value):
            return "version must be a Forge release, such as v1.2.1"
        if key == "runner" and not value.strip():
            return "runner must name a GitHub Actions runner label"
        if key == "signoff" and value and not SIGNOFF.fullmatch(value):
            return ("signoff must name the client's sign-off record, "
                    "docs/decisions/NNNN-client-signoff.md")
    return ""


def check_pin(cwd: str | os.PathLike[str] | None = None, item: str = "", words: str = "") -> None:
    """Run the release forge.toml pins through uv when the installed Forge isn't it, else refuse.

    A folder outside git, or a repo with no forge.toml yet (before init or migrate), has no pin.
    On the default branch a newer Forge runs while an upgrade fix waits: the default branch as last
    fetched still pins an older one, and a fix worktree pins the installed one.
    """
    if words == "work":
        from forge.worker import checkout
        checkout(item)  # A conflicted forge.toml cannot supply a release pin yet.
    done = run("git", "rev-parse", "--show-toplevel", cwd=cwd)
    top = Path(done.stdout.strip())
    if done.returncode or not (top / "forge.toml").is_file():
        return
    pinned = config(top)["version"].removeprefix("v")
    if pinned == __version__:
        return
    from forge import story

    trees = story.worktrees(top)
    here = {path: _pin((path / "forge.toml").read_text(encoding="utf-8"))
            for path in trees.values() if (path / "forge.toml").is_file()}
    landed_ref = story.landed_ref(top)
    landed = _pin(story.show(top, landed_ref, "forge.toml") or "")
    # Task start must update its story before an old checkout can hand it to the old release.
    if (words == "task start" and (task := ITEM.fullmatch(item)) and task["task"]
            and landed_ref == f"origin/{default_branch(top)}" and _older(pinned, landed)):
        return
    branch = current_branch(top)
    if branch == default_branch(top) and _older(pinned) and _older(landed):
        upgrade = next((branch[4:] for branch, path in trees.items()
                        if branch.startswith("fix/") and here.get(path) == __version__), "")
        if upgrade:
            print(f"Forge v{__version__} runs here while the upgrade in fix {upgrade} waits for its "
                  "merge.", file=sys.stderr)
            return
    branches = (f"fix/{item}", f"forge/{item}", f"task/{item.replace('/', '-')}", f"story/{item}")
    folder = next((trees[branch] for branch in branches if item and branch in trees), None)
    if folder is not None and folder != top and here.get(folder) == __version__:
        refuse(REFUSALS["pin_elsewhere"], item=item, folder=folder, installed=f"v{__version__}",
               pinned=f"v{pinned}", words=words)
    # Run the pinned release through uv instead, unless this already is that run (no loop).
    if shutil.which("uv") and os.environ.get("FORGE_PINNED_RUN") != f"v{pinned}":
        advice = (f" Merge {default_branch(top)} into this branch to use Forge v{__version__} "
                  "and its rules." if _older(pinned) and landed == __version__
                  and landed_ref == f"origin/{default_branch(top)}"
                  and branch and branch != default_branch(top) else "")
        print(f"Forge v{__version__} is installed, but this repo pins v{pinned}, so v{pinned} runs "
              f"through uv.{advice}", file=sys.stderr)
        sys.exit(run_release(f"v{pinned}", sys.argv[1:], cwd))
    refuse(REFUSALS["pin"], installed=f"v{__version__}", pinned=f"v{pinned}")


def resume_pin(top: Path, previous: str, rounds: int | None = None, *, accepted: bool = False,
               before: list[str] | None = None) -> None:
    """Hand a running command to a changed pin, finishing its nested close when needed."""
    release = "v" + _pin((top / "forge.toml").read_text(encoding="utf-8"))
    if release == previous or release == f"v{__version__}" or not VERSION.fullmatch(release):
        return
    print(f"Forge pin changed from {previous} to {release}; "
          f"continuing forge {sys.argv[1]} with {release}.", flush=True)
    if rounds is not None:
        os.environ["FORGE_LAND_ROUNDS"] = str(rounds)
    if accepted:
        os.environ["FORGE_CLOSE_ACCEPTED"] = "1"
    if before and (status := run_release(release, before, top)):
        sys.exit(status)
    sys.exit(run_release(release, sys.argv[1:], top))


def run_release(release: str, args: list[str], cwd: str | os.PathLike[str] | None) -> int:
    """Run a Forge release's `forge <args>` through uv in cwd, its output streamed; its exit code."""
    return subprocess.run(
        [shutil.which("uv") or "uv", "tool", "run", "--from",
         f"git+https://github.com/knacklabs/symphony-forge@{release}", "forge", *args],
        cwd=cwd, env={**os.environ, "FORGE_PINNED_RUN": release}).returncode


def set_version(text: str, release: str) -> str:
    """forge.toml's text with its version string set to the release, every other byte kept.

    One blunt rule, failing closed: exactly one line in the whole file starts `version =` (lines
    inside strings count), it is a plain `version = "..."` before the first table, and the edit
    parses to the same settings with only the version changed. Otherwise it refuses.
    """
    lines = re.findall(r"^[ \t]*version[ \t]*=", text, re.M)
    plain = re.search(r'^(version[ \t]*=[ \t]*)"[^"\\\r\n]*"([ \t]*(?:#[^\r\n]*)?\r?)$', text, re.M)
    new = ""
    if len(lines) == 1 and plain and not re.search(r"^[ \t]*\[", text[:plain.start()], re.M):
        new = f'{text[:plain.start()]}{plain[1]}"{release}"{plain[2]}{text[plain.end():]}'
        try:
            if tomllib.loads(new) != {**tomllib.loads(text), "version": release}:
                new = ""
        except tomllib.TOMLDecodeError:
            new = ""
    if not new:
        refuse(REFUSALS["bad_config"], problem=f'Forge could not set version = "{release}" in it, '
               "so it left it alone")
    return new


def _pin(text: str) -> str:
    """The version a forge.toml's text pins, without the v, or "" when it can't be read."""
    try:
        version = tomllib.loads(text).get("version")
    except tomllib.TOMLDecodeError:
        return ""
    return version.removeprefix("v") if isinstance(version, str) else ""


def _older(version: str, target: str = __version__) -> bool:
    """The version is a release older than the target (the installed Forge by default)."""
    release, installed = (re.match(r"(\d+)\.(\d+)\.(\d+)", v) for v in (version, target))
    return bool(release and installed and
                tuple(map(int, release.groups())) < tuple(map(int, installed.groups())))


def roadmap(top: Path | None = None) -> list[dict[str, Any]]:
    """The items of plans/roadmap.json (each has a key), or [] when there is no roadmap yet."""
    path = (top or root()) / "plans" / "roadmap.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        refuse(REFUSALS["bad_roadmap"], problem=exc)
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list) or not all(
            isinstance(item, dict) and isinstance(item.get("key"), str) for item in items):
        refuse(REFUSALS["bad_roadmap"], problem="it needs an items list where every item has a key")
    return items


# --- .factory state: one file per story, task or fix -----------------------------------

ITEM = re.compile(r"(?P<key>[A-Z][A-Z0-9-]*)(?:/(?P<task>[A-Z0-9][A-Z0-9-]*))?|(?P<fix>[a-z0-9][a-z0-9-]*)")


def state_path(item: str) -> str:
    """The repo-relative state file of a story (KEY), a task (KEY/TASK) or a fix (its name)."""
    match = ITEM.fullmatch(item)
    if not match:
        refuse(REFUSALS["bad_item"], item=item)
    if match["fix"]:
        return f".factory/fixes/{item}.json"
    if match["task"]:
        # Tasks sit in tasks/ so a task named STORY can't collide with story.json on a
        # case-insensitive disk (macOS, Windows).
        return f".factory/stories/{match['key']}/tasks/{match['task']}.json"
    return f".factory/stories/{item}/story.json"


def read_state(item: str, top: Path | None = None) -> dict[str, Any] | None:
    """An item's state in this checkout, or None when Forge never started it here."""
    rel = state_path(item)
    path = (top or root()) / rel
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        refuse(REFUSALS["bad_state"], path=rel, problem=exc)
    if not isinstance(data, dict):
        refuse(REFUSALS["bad_state"], path=rel, problem="it is not a JSON object")
    return data


def write_state(item: str, data: dict[str, Any], top: Path | None = None) -> str:
    """Write an item's state in a checkout on a work branch. Returns the repo-relative path."""
    top = top or root()
    _work_branch(top)
    rel = state_path(item)
    path = top / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    # Bytes, so Windows writes the same LF file as everyone else.
    tmp.write_bytes((json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    os.replace(tmp, path)
    return rel


def now() -> str:
    """The current UTC time. FORGE_NOW overrides it, so tests can drive dated steps."""
    # ponytail: an env override is the whole clock seam.
    return os.environ.get("FORGE_NOW") or datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_step(data: dict[str, Any], step: str) -> dict[str, Any]:
    """Add a dated step (start, review, ci-green, ready, merged) to an item's state."""
    data.setdefault("steps", []).append({"step": step, "at": now()})
    return data


def commit_state(message: str, *paths: str, top: Path | None = None) -> bool:
    """Commit these repo-relative paths (state and the docs that go with it) on the work branch.

    The git hooks run as usual. Returns False when nothing changed.
    """
    top = top or root()
    _work_branch(top)
    git("add", "--", *paths, cwd=top)
    if run("git", "diff", "--cached", "--quiet", "--", *paths, cwd=top).returncode == 0:
        return False
    git("commit", "-q", "-m", message, "--", *paths, cwd=top)
    return True


def _work_branch(top: Path) -> str:
    """The checkout's branch. Refuses the default branch (once it has a commit) and a detached HEAD."""
    branch = current_branch(top)
    born = run("git", "rev-parse", "--verify", "-q", "HEAD", cwd=top).returncode == 0
    if not branch or (born and branch == default_branch(top)):
        refuse(REFUSALS["default_branch"], branch=branch or "a detached HEAD")
    return branch
