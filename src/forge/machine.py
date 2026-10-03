"""The repos this machine has used with Forge, and its line of Forge agent runs."""
import contextlib
import json
import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from forge import repo

# The Forge agent runs (work rounds, plan reads, close reviews) one machine runs at once, whatever
# the repo, so several repos' agents can't run it out of memory.
AGENT_SLOTS = 2


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


@contextlib.contextmanager
def agent_slot(top: Path, kind: str) -> Iterator[None]:
    """Hold one of the machine's agent slots while a `kind` run in `top` runs its agent. The line
    is one queue file, read and written only under one lock: a run joins at the end and starts once
    it is among the first AGENT_SLOTS live entries, first come, first served, saying its place when
    it starts waiting and each time that changes. An entry is live while its Forge or its agent
    runs, so a killed Forge whose agent still runs keeps its place until the agent ends; dead ones
    are dropped."""
    from forge import codex  # codex imports machine

    me = codex.identity(os.getpid()) or {"pid": os.getpid()}
    with _queue() as runs:
        runs.append({"forge": me, "agent": None, "repo": str(top), "kind": kind})
    try:
        said = 0
        while True:
            with _queue() as runs:
                runs[:] = [run for run in runs if _running(run["forge"]) or _running(run["agent"])]
                place = next(n for n, run in enumerate(runs) if run["forge"] == me) - AGENT_SLOTS + 1
            if place <= 0:
                break
            if place != said:
                print(f"{AGENT_SLOTS} Forge agents already run on this machine, so this one waits "
                      f"its turn: it is number {place} in line.", flush=True)
                said = place
            time.sleep(0.5)
        yield
    finally:
        with _queue() as runs:
            runs[:] = [run for run in runs if run["forge"] != me]


def started(pid: int) -> None:
    """Record the agent this Forge just started, so its place lasts as long as the agent does."""
    from forge import codex

    agent = codex.identity(pid) or {"pid": pid}
    with _queue() as runs:
        for run in runs:
            if run["forge"]["pid"] == os.getpid():
                run["agent"] = agent


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
