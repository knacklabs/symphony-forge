"""State and hotspot details used by forge next's report."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from forge import repo, spotted, story


def read_state(item: str, top: Path, refusals: dict[Path, str] | None = None) -> dict[str, Any] | None:
    """Keep an unusable local record from stopping the rest of the report."""
    try:
        return repo.read_state(item, top)
    except repo.Refused as problem:
        if problem.entry != repo.REFUSALS["bad_state"]:
            raise
        if refusals is not None:
            message = str(problem).splitlines()[0]
            old = refusals.get(top)
            if not old:
                refusals[top] = message
            elif message not in old.splitlines():
                refusals[top] = f"{old}\n{message}"
        return {"status": "unusable"}


def hotspots(top: Path, trees: dict[str, Path], cap: int | None = None,
             refusals: dict[Path, str] | None = None) -> list[str]:
    """Hotspots on the default branch, unless their fix already has a worktree. With a cap, the
    session context names that many and points to forge next for the rest."""
    ref = story.landed_ref(top)
    try:
        items = spotted.read(top, ref)
        old = spotted.before_signoff(top, ref, offline=cap is not None) if items else set()
        items = [entry for entry in items if entry["key"] not in old]
    except spotted.Unreadable as problem:
        return [f"{spotted.PATH} on the default branch can't be read, so no hotspots are "
                f"listed: {problem}."]
    hotspots = spotted.hotspots(items)
    if not hotspots:
        return []
    files = set(repo.git("ls-tree", "-r", "-z", "--name-only", ref, cwd=top).split("\0"))
    whys = {(read_state(branch.partition("/")[2], path, refusals) or {}).get("why")
            for branch, path in trees.items()
            if re.fullmatch(r"(?:fix|forge)/[a-z0-9][a-z0-9-]*", branch)}
    lines: list[list[str]] = []
    for hotspot in hotspots:
        path, count = hotspot["path"], hotspot["count"]
        why, done = spotted.fix_text(path, hotspot["texts"])
        if path not in files or why in whys:
            continue
        reason = (f"{count} noted problems are open there." if hotspot["reason"] == "open"
                  else f"{count} changes had the same kind of serious review finding there.")
        suffix = Path(path).suffix.lower()
        kind = ("ui" if suffix in {".html", ".css", ".scss", ".jsx", ".tsx", ".vue", ".svelte"}
                or suffix in {".ts", ".js"} and set(Path(path).parts) & {
                    "web", "frontend", "components", "screens", "pages"}
                else "backend" if suffix in {".py", ".ts", ".js", ".go", ".rs", ".java", ".rb",
                                             ".sql", ".prisma"} else "mechanical")
        lines.append([f"{path} keeps breaking: {reason}",
                      f'Next: forge fix start "{why}" --done "{done}" --kind {kind}'])
    if cap is None:
        return [line for block in lines for line in block]
    more = f"{len(lines) - cap} more files keep breaking. Run forge next for the list."
    return [block[0] for block in lines[:cap]] + ([more] if len(lines) > cap else [])
