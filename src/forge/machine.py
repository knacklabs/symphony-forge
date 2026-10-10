"""The repos this machine has used with Forge, and its line of Forge agent runs."""
import contextlib
import json
import os
import sys
import time
import uuid
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from subprocess import CalledProcessError, Popen
from typing import Any

from forge import __version__, repo

# The Forge agent runs (work rounds, plan reads, close reviews) one machine runs at once, whatever
# the repo, so several repos' agents can't run it out of memory.
_agent_entry: dict[str, Any] | None = None
_WAIT_REASONS = {
    True: "Other planned work waits on this item, so it goes before runs nothing waits on.",
    False: "Nothing waits on this item; runs other planned work waits on go first.",
}

COMMANDS = [{"words": "lanes", "run": "lanes", "changes_state": False,
    "help": "Show this release's machine-wide runs", "position": 60,
    "args": [(("--json",), {"action": "store_true"})],
    "listing": "| `forge lanes --json` | Runs on this machine from repos on this Forge release |"},
    {"words": "stop", "run": "stop", "changes_state": False,
    "help": "Stop a running or waiting run (only a person)", "position": 61,
    "args": [(("item",), {"nargs": "?"}), (("--repo",), {"metavar": "ROOT"}),
             (("--id",), {"dest": "entry_id", "metavar": "ID"})],
    "listing": "| `forge stop <item>` | Person only: stops the item's runs in this repo (`--repo <root>` or `--id <id>`) |"}]


def half_cores() -> int:
    """The shared budget for agents and tests, including Python 3.11 and unknown counts."""
    return max(1, (getattr(os, "process_cpu_count", os.cpu_count)() or 2) // 2)


def test_slots() -> int:
    """One test run per four available cores, with at least one place."""
    return max(1, half_cores() // 2)


def _repos_file() -> Path:
    config = os.environ.get("APPDATA" if os.name == "nt" else "XDG_CONFIG_HOME")
    return Path(config or Path.home() / ("AppData/Roaming" if os.name == "nt" else ".config")) / "forge" / "repos"


def main_checkout(path: Path) -> Path:
    """Resolve the main checkout from Git's folder shared by all worktrees."""
    return Path(repo.git("rev-parse", "--path-format=absolute", "--git-common-dir",
                         cwd=path)).resolve().parent


def remembered() -> list[Path]:
    """Read each existing Forge main checkout once."""
    try:
        lines = _repos_file().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return list(dict.fromkeys(path for line in lines
                              if line and ((path := Path(line).resolve()) / "forge.toml").is_file()))


def remember(top: Path) -> None:
    """Best-effort registration after a successful Forge command."""
    try:
        path = main_checkout(top)
        if not (path / "forge.toml").is_file() or path in remembered():
            return
        registry = _repos_file()
        registry.parent.mkdir(parents=True, exist_ok=True)
        with registry.open("a", encoding="utf-8") as out:
            out.write(f"{path}\n")
    except Exception:
        pass


def join(kind: str, repo: Path, item: str | None, model: str | None, effort: str | None) -> dict[str, Any]:
    """Join a lane; prerequisite agents go first, with arrival order within each group."""
    from forge import codex, repo as repository  # codex imports machine

    me = codex.identity(os.getpid()) or {"pid": os.getpid()}
    root = main_checkout(repo)
    unblocks = False
    if kind != "test" and item and "/" in item:
        from forge import board

        unblocks = any(item in part["waits_for"] and part["status"] != "Merged"
                       for plan in board.machine_board(repo)["dependency_maps"]
                       for part in plan["parts"])
    title = None
    round_number = None
    if item and (match := repository.ITEM.fullmatch(item)):
        state = repository.read_state(item, repo) or {}
        round_number = state.get("round", 0 if kind in ("test", "review") else None)
        if kind == "work":
            round_number = (round_number + 1 if isinstance(round_number, int)
                            else 1 if state.get("status") == "started" else None)
        title = state.get("why") if match["fix"] else state.get("title")
        if match["task"] or (not title and kind == "read"):
            from forge import task

            doc = (repo / "plans" / f"{match['key']}.md" if match["key"] else
                   repo / "docs" / "specs" / f"{item}.md")
            if doc.is_file():
                sections = task.sections(doc.read_text(encoding="utf-8"))
                title = (task.rows(sections).get(match["task"], {}).get("Name")
                         if match["task"] else sections.get("#"))
    entry = {"id": str(uuid.uuid4()), "version": __version__, "kind": kind, "repo_root": root.as_posix(),
             "checkout_root": repo.resolve().as_posix(),
             "repo_name": root.name, "item": item, "title": title, "model": model, "effort": effort,
             "joined_at": repository.now(), "started_at": None, "process": me, "forge": me,
             "agent": None, "round": round_number, "unblocks": unblocks,
             "output_path": None, "progress": None}
    size = test_slots() if kind == "test" else half_cores()
    with _queue() as runs:
        runs.append(entry)
    _lane_event(entry, "lane joined", at=entry["joined_at"])
    try:
        said = 0
        while True:
            with _queue() as runs:
                lane = [run for run in runs if (run["kind"] == "test") == (kind == "test")]
                position = next((n for n, run in enumerate(lane) if run["id"] == entry["id"]), None)
                if position is None:
                    raise repository.Refused("This run was stopped while waiting; it will not start.", "")
                place = position - size + 1
                if place <= 0:
                    # Admission holds the place before the model process is launched.
                    lane[position]["admitted"] = True
                    entry["admitted"] = True
            if place <= 0:
                _lane_event(entry, "lane admitted")
                return entry
            if place != said:
                print(f"{size} Forge {'test runs' if kind == 'test' else 'agents'} already run on this machine, so this one waits "
                      f"its turn: it is number {place} in line."
                      + (f" {_WAIT_REASONS[unblocks]}" if kind != "test" else ""), flush=True)
                said = place
            time.sleep(0.5)
    except BaseException:
        leave(entry)
        raise


def started(entry: dict[str, Any] | int, pid: int | None = None) -> None:
    """The actual command holds the place even if its Forge parent is killed."""
    from forge import codex

    # The live default-branch PR checker still calls started(pid) and agent_slot(top, kind).
    if pid is None:
        assert isinstance(entry, int)
        agent_started(entry)
        return
    assert isinstance(entry, dict)
    process = codex.identity(pid) or {"pid": pid}
    with _queue() as runs:
        for run in runs:
            if run["id"] == entry["id"]:
                run.update(entry, process=process, agent=process, started_at=repo.now())
                entry.update(run)
                return
    # Stop may win between admission and spawning. Do not leave a cancelled child running.
    if codex._alive(process) is True:
        codex._stop(process, True)
    raise repo.Refused("This run was stopped; it will not start another agent.", "")


def leave(entry: dict[str, Any]) -> None:
    """Release an entry once its command has ended."""
    with _queue() as runs:
        runs[:] = [run for run in runs if run["id"] != entry["id"] or
                   (run["process"]["pid"] != os.getpid() and _running(run["process"]))]


def _lane_event(entry: dict[str, Any], event: str, **fields: Any) -> None:
    """Lane history belongs in the item's existing log, not the machine queue."""
    if entry.get("item") and entry.get("checkout_root"):
        try:
            repo.record_event(Path(entry["checkout_root"]), entry["item"], event,
                              lane_id=entry["id"], kind=entry["kind"],
                              lane="tests" if entry["kind"] == "test" else "agents",
                              round=entry.get("round"), **fields)
        except (OSError, CalledProcessError):
            pass  # A removed checkout must not prevent release of its machine place.


def entries() -> list[dict[str, Any]]:
    """Live running and waiting entries, in admission order, from both lanes."""
    with _queue() as runs:
        return list(runs)


@contextlib.contextmanager
def agent_slot(top: Path, kind: str, item: str | None = None, model: str | None = None,
               effort: str | None = None) -> Iterator[dict[str, Any]]:
    """A single command has one active agent entry, shared by its model launches."""
    global _agent_entry
    entry = _agent_entry = join(kind, top, item, model, effort)
    try:
        yield entry
    finally:
        leave(entry)
        _agent_entry = None


def agent_started(pid: int, output_path: Path | None = None) -> None:
    """Register a model launch inside the current work/read/review admission."""
    if _agent_entry is not None:
        if output_path is not None:
            _agent_entry["output_path"] = output_path.as_posix()
        started(_agent_entry, pid)


@contextlib.contextmanager
def agent_process(process: Popen[Any], output_path: Path | None = None) -> Iterator[None]:
    """A model's separate process group must still end when its caller is interrupted."""
    from forge import codex
    try:
        agent_started(process.pid, output_path)
        yield
    except BaseException:
        if process.poll() is None:
            codex._stop(codex.identity(process.pid) or {"pid": process.pid}, True)
            process.wait()
        raise


def view() -> dict[str, Any]:
    # The board needs identity, not command lines containing model prompts or host arguments.
    runs = [{key: value for key, value in run.items() if key not in ("forge", "agent", "repo", "legacy")}
            for run in entries()]
    for run in runs:
        run["process"] = {key: value for key, value in run["process"].items()
                          if key in ("pid", "started")}
    return {name: {"size": size, "entries": [run for run in runs
            if (run["kind"] == "test") == (name == "tests")]}
            for name, size in (("agents", half_cores()), ("tests", test_slots()))}


def lanes(args: Any) -> int:
    """Show this release, while older runs still count towards queue admission."""
    result = view()
    now = datetime.fromisoformat(repo.now())
    for lane in result.values():
        rows = []
        for index, run in enumerate(lane["entries"]):
            if run.get("version") != __version__:
                continue
            run["place"] = 0 if run["started_at"] else max(0, index - lane["size"] + 1)
            at = run["started_at"] or run["joined_at"]
            run["elapsed"] = max(0, (now - datetime.fromisoformat(at)).total_seconds())
            rows.append(run)
        lane["entries"] = rows
    result.update(version=__version__, machine={**load(), "cores":
                  getattr(os, "process_cpu_count", os.cpu_count)()})
    if args.json:
        print(json.dumps(result))
    else:
        print(f"Test lane: {result['tests']['size']} places.")
        for name in ("agents", "tests"):
            for run in result[name]["entries"]:
                state = f"waiting #{run['place']}" if run["place"] else "running"
                reason = f" {_WAIT_REASONS[bool(run.get('unblocks'))]}" if run["place"] and name == "agents" else ""
                print(f"{run['repo_name']}: {run['item']} ({run['kind']}, {state}){reason}")
        if not any(result[name]["entries"] for name in ("agents", "tests")):
            print("Nothing running")
    return 0


def load() -> dict[str, Any]:
    """OS measurements; unavailable values stay null, never invented."""
    memory: dict[str, int | None] = {"total_bytes": None, "available_bytes": None}
    with contextlib.suppress(OSError, ValueError, AttributeError):
        if sys.platform == "linux":
            values = {line.split()[0]: int(line.split()[1]) * 1024
                      for line in Path("/proc/meminfo").read_text().splitlines()}
            memory.update(total_bytes=values["MemTotal:"], available_bytes=values["MemAvailable:"])
        elif sys.platform == "darwin":
            memory["total_bytes"] = int(repo.run("sysctl", "-n", "hw.memsize").stdout)
            stats = repo.run("vm_stat").stdout.splitlines()
            page_size = int(stats[0].split("of ")[1].split()[0])
            pages = {key: int(value.strip().rstrip(".")) for line in stats[1:]
                     if ":" in line for key, value in [line.split(":", 1)]}
            memory["available_bytes"] = page_size * sum(pages.get(key, 0) for key in
                ("Pages free", "Pages inactive", "Pages speculative"))
        elif os.name == "nt":
            import ctypes
            class Memory(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                            *[(name, ctypes.c_ulonglong) for name in
                              ("total", "available", "page_total", "page_available", "virtual_total",
                               "virtual_available", "extended")]]
            status = Memory()
            status.length = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                memory.update(total_bytes=status.total, available_bytes=status.available)
    average = None
    with contextlib.suppress(OSError):
        average = list(os.getloadavg()) if hasattr(os, "getloadavg") else None
    return {"load": average, "memory": memory}


def stop(args: Any) -> int:
    """A person cancels waiting entries or ends verified process trees before freeing places."""
    from forge import codex
    if os.environ.get("FORGE_WORKER"):
        raise repo.Refused("Only a person can run forge stop; ask the person to stop the run.", "")
    if bool(args.entry_id) == bool(args.item) or (args.entry_id and args.repo):
        raise repo.Refused("Name an item with optional --repo, or use --id alone.", "")
    root = main_checkout(Path(args.repo).resolve() if args.repo else repo.root()) if args.item else None
    with _queue() as runs:
        selected = [run for run in runs if run["id"] == args.entry_id or
                    (root and run["repo_root"] == root.as_posix() and run["item"] == args.item)]
        # Validate every target before signalling any. Unknown identity never grants permission.
        for run in selected:
            process = run["process"]
            if (run.get("agent") or run["started_at"]) and ("started" not in process or codex._alive(process) is None):
                raise repo.Refused("Forge cannot verify this run's process; nothing was stopped.", "")
        for run in selected:
            if (run.get("agent") or run["started_at"]) and codex._alive(run["process"]) is True:
                ended = codex._stop(run["process"], run["process"] != run.get("forge"))
                # The tree is confirmed ended even if its leader still awaits reaping.
                if not ended:
                    raise repo.Refused("Forge could not confirm the run stopped; its place is still held.", "")
            runs.remove(run)
    print("Stopped the run." if selected else "There is nothing to stop.")
    return 0


@contextlib.contextmanager
def _queue() -> Iterator[list[dict[str, Any]]]:
    """The machine's line of agent runs, to read and change while holding its lock."""
    from forge import codex

    path = _repos_file().parent / "agent-runs.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with codex._one_at_a_time(path):  # pyright: ignore[reportPrivateUsage]
        try:
            runs = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            runs = []
        # Runs launched by the previous release still hold their places during an upgrade.
        for run in runs:
            if "id" not in run:
                root = Path(run["repo"]).resolve()
                run.update(id=str(uuid.uuid4()), legacy=True, repo_root=root.as_posix(), repo_name=root.name,
                           item=None, model=None, effort=None, joined_at=None,
                           started_at=run["agent"].get("started") if run["agent"] else None,
                           process=run["agent"] or run["forge"], output_path=None, progress=None)
            if run.get("legacy"):
                run["process"] = run["agent"] or run["forge"]
        # A work round can launch a commit nudge, and a review can retry. Between those model
        # calls its live Forge process holds the admission. Tests hold only their command once
        # started. A reused child pid is dropped, never reassigned to its new owner.
        before = list(runs)
        retained = []
        for run in runs:
            recorded = run["process"]
            current = codex.identity(recorded["pid"])
            # One OS observation decides both liveness and parent fallback. A second
            # lookup could see a reused pid after the first already reported it gone.
            if current is not None and ("started" not in recorded or "command" not in current
                                        or codex._legacy_identity(recorded)
                                        or current["started"] == recorded["started"]):
                retained.append(run)
            elif (run["kind"] != "test"
                    and current is None
                    and _running(run.get("forge"))):
                run["process"] = run["forge"]
                retained.append(run)
        runs[:] = retained
        agents = iter(sorted((run for run in runs if run["kind"] != "test"), key=lambda run:
            0 if run.get("admitted") or run["started_at"] or run.get("legacy") else
            1 if run.get("unblocks") else 2))
        runs[:] = [run if run["kind"] == "test" else next(agents) for run in runs]
        yield runs
        path.with_suffix(".new").write_text(json.dumps(runs), encoding="utf-8")
        os.replace(path.with_suffix(".new"), path)
        remaining = {run["id"] for run in runs}
        live = {run["id"] for run in retained}
        for run in before:
            if run["id"] not in remaining:
                _lane_event(run, "lane left", end_known=run["id"] in live)


def _running(process: dict[str, Any] | None) -> bool:
    """Whether a recorded process still runs; one recorded by id alone runs while its id does."""
    from forge import codex

    if not process:
        return False
    if "started" not in process:
        return codex.identity(process["pid"]) is not None
    return codex._alive(process) is not False  # pyright: ignore[reportPrivateUsage]
