"""State and hotspot details used by forge next's report."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from forge import repo, spotted, story


def parse_state(text: str | bytes) -> tuple[dict[str, Any], str | None]:
    """Parse a saved record without hiding malformed JSON from `forge next`."""
    try:
        data = json.loads(text.decode("utf-8") if isinstance(text, bytes) else text)
    except (UnicodeError, ValueError) as problem:
        return {}, str(problem)
    if not isinstance(data, dict):
        return {}, "it is not a JSON object"
    return repo.without_size_stop(data), None


def parse_blobs(texts: dict[str, bytes]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Parse Git record blobs and retain why unreadable blobs were rejected."""
    states, unusable = {}, {}
    for blob, text in texts.items():
        state, problem = parse_state(text)
        states[blob] = state
        if problem:
            unusable[blob] = problem
    return states, unusable


def changed_state(path: Path, parsed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Read a changed worktree record without letting bad text stop the report."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {}
    if text not in parsed:
        parsed[text], _ = parse_state(text)
    return parsed[text]


def ref_states(refs: dict[str, str], files: dict[str, dict[str, str]],
               states: dict[str, dict[str, Any]], unusable: dict[str, str]
               ) -> tuple[dict[tuple[str, str], str], dict[str, dict[str, dict[str, Any]]]]:
    """Keep invalid records identifiable while exposing safe state to next-step readers."""
    errors = {(ref, rel): unusable[blob] for ref, tree in refs.items()
              for rel, blob in files[tree].items() if blob in unusable}
    copies = {ref: {rel: {"status": "unusable"} if blob in unusable else states[blob]
                    for rel, blob in files[tree].items()} for ref, tree in refs.items()}
    return errors, copies


def read_ref_state(item: str, ref: str, top: Path) -> dict[str, Any]:
    """Read a task record from a Git ref, refusing a broken base before work starts."""
    rel = repo.state_path(item)
    text = repo.blob_bytes(top, [f"{ref}:{rel}"]).get(f"{ref}:{rel}")
    if text is None:
        return {}
    state, problem = parse_state(text)
    if problem:
        repo.refuse(repo.REFUSALS["bad_state"], path=rel, problem=problem)
    return state


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
