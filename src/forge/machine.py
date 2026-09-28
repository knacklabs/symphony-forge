"""The repos this machine has used with Forge."""
import os
from pathlib import Path

from forge import repo


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
