"""The repos this machine has used with Forge, and its line of Forge agent runs."""
import contextlib
import json
import os
import sys
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from subprocess import Popen
from typing import Any

from forge import repo

# The Forge agent runs (work rounds, plan reads, close reviews) one machine runs at once, whatever
# the repo, so several repos' agents can't run it out of memory.
_agent_entry: dict[str, Any] | None = None

COMMANDS = [{"words": "stop", "run": "stop", "changes_state": False,
    "help": "Stop a running or waiting run (only a person)", "position": 61,
    "args": [(("item",), {"nargs": "?"}), (("--repo",), {"metavar": "ROOT"}),
             (("--id",), {"dest": "entry_id", "metavar": "ID"})],
    "listing": "| `forge stop <item>` | Person only: stops the item's runs in this repo (`--repo <root>` or `--id <id>`) |"}]


def half_cores() -> int:
    """The shared budget for agents and tests, including Python 3.11 and unknown counts."""
    return max(1, (getattr(os, "process_cpu_count", os.cpu_count)() or 2) // 2)


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
    """Join either machine-wide lane and wait for admission, first come, first served."""
    from forge import codex, repo as repository  # codex imports machine

    me = codex.identity(os.getpid()) or {"pid": os.getpid()}
    root = main_checkout(repo)
    entry = {"id": str(uuid.uuid4()), "kind": kind, "repo_root": root.as_posix(),
             "repo_name": root.name, "item": item, "model": model, "effort": effort,
             "joined_at": repository.now(), "started_at": None, "process": me, "forge": me,
             "agent": None,
             "output_path": None, "progress": None}
    size = 1 if kind == "test" else half_cores()
    with _queue() as runs:
        runs.append(entry)
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
                return entry
            if place != said:
                print(f"{size} Forge {'test runs' if kind == 'test' else 'agents'} already run on this machine, so this one waits "
                      f"its turn: it is number {place} in line.", flush=True)
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


def entries() -> list[dict[str, Any]]:
    """Live running and waiting entries, in arrival order, from both lanes."""
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


def agent_started(pid: int) -> None:
    """Register a model launch inside the current work/read/review admission."""
    if _agent_entry is not None:
        started(_agent_entry, pid)


@contextlib.contextmanager
def agent_process(process: Popen[Any]) -> Iterator[None]:
    """A model's separate process group must still end when its caller is interrupted."""
    from forge import codex
    try:
        agent_started(process.pid)
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
            for name, size in (("agents", half_cores()), ("tests", 1))}


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
                if not ended or codex._alive(run["process"]) is not False:
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
        for run in runs:
            if (run["kind"] != "test" and not _running(run["process"])
                    and codex.identity(run["process"]["pid"]) is None
                    and _running(run.get("forge"))):
                run["process"] = run["forge"]
        runs[:] = [run for run in runs if _running(run["process"])]
        yield runs
        path.with_suffix(".new").write_text(json.dumps(runs), encoding="utf-8")
        os.replace(path.with_suffix(".new"), path)


def _running(process: dict[str, Any] | None) -> bool:
    """Whether a recorded process still runs; one recorded by id alone runs while its id does."""
    from forge import codex

    if not process:
        return False
    if "started" not in process:
        return codex.identity(process["pid"]) is not None
    return codex._alive(process) is not False  # pyright: ignore[reportPrivateUsage]
