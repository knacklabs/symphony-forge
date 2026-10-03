"""The repos this machine has used with Forge, and its line of Forge agent runs."""
import contextlib
import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import IO

from forge import repo

if os.name == "nt":
    import msvcrt
else:
    import fcntl

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
def agent_slot() -> Iterator[None]:
    """Hold one of the machine's agent slots while an agent runs. Each run takes a ticket, a file
    beside the repo list that it keeps locked while its process lives, so a run that dies frees its
    place however it ends. Tickets are named by when they were taken, so the line is first come,
    first served. A run waits while AGENT_SLOTS live tickets are ahead of it, and says its place
    when it starts waiting and each time that changes."""
    folder = _repos_file().parent / "agent-runs"
    folder.mkdir(parents=True, exist_ok=True)
    while True:
        mine = folder / f"{time.time_ns():020d}-{os.getpid()}"
        ticket = mine.open("xb")
        while not _lock(ticket):  # another run is checking it for a moment
            time.sleep(0.05)
        with contextlib.suppress(FileNotFoundError):
            if os.path.samestat(os.fstat(ticket.fileno()), os.stat(mine)):
                break
        ticket.close()  # a check took it, unlocked, for a dead run's and removed it
    try:
        said = 0
        while (ahead := sum(_live(other) for other in folder.iterdir()
                            if other.name < mine.name)) >= AGENT_SLOTS:
            if (place := ahead - AGENT_SLOTS + 1) != said:
                print(f"{AGENT_SLOTS} Forge agents already run on this machine, so this one waits "
                      f"its turn: it is number {place} in line.", flush=True)
                said = place
            time.sleep(0.5)
        yield
    finally:
        ticket.close()
        with contextlib.suppress(OSError):  # on Windows, while another run checks it
            mine.unlink()


def _lock(file: IO[bytes]) -> bool:
    """Lock `file` without waiting; False when another holds it. The system lets go when the
    holder closes it or ends."""
    try:
        if os.name == "nt":
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _live(ticket: Path) -> bool:
    """Whether a live run holds `ticket`. A dead run's ticket is removed."""
    try:
        with ticket.open("rb") as held:
            if not _lock(held):
                return True
    except FileNotFoundError:
        return False
    with contextlib.suppress(OSError):
        ticket.unlink()
    return False
