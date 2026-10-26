"""Kept review findings from landed lists and original, pre-squash review history."""
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from forge import backfill, board_facts, repo, review, score


def _rows(item: str, known: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for entry in known:
        if entry.get("outcome") not in ("follow-up", "lived with"):
            continue
        kept = entry["outcome"]
        scores = tuple(entry.get(field) for field in ("gain", "work", "harm"))
        outcome = score.bar(scores) if all(scores) else None
        reason = entry.get("reason") or (
            f"below the bar ({outcome})" if outcome in ("follow-up", "live with") else
            "follow-up outside this review's boundary" if kept == "follow-up" else
            "below the review's blocking level")
        rows.append({"item": item, **{field: entry.get(field) for field in (
            "file", "line", "title", "gain", "work", "harm")}, "kept": kept, "reason": reason})
    return rows


def _pull(top: Path, pr: dict[str, Any]) -> list[dict[str, Any]]:
    """A merged pull request's evidence is immutable; keep even an empty result."""
    cache = repo.forge_dir(top) / f"known-issues-pr-{pr['number']}.json"
    try:
        return json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    fetched = repo.run("git", "fetch", "-q", "--no-tags", "origin",
                       f"refs/pull/{pr['number']}/head", cwd=top)
    fetched.check_returncode()
    head = repo.git("rev-parse", "FETCH_HEAD", cwd=top)
    identity = backfill._identity(top, head, pr["headRefName"])
    rows = []
    if identity is not None:
        item, state = identity
        known = state.get("known")
        if known is None:
            starts = repo.git("log", "--reverse", "--diff-filter=A", "--format=%H", head,
                              "--", repo.state_path(item), cwd=top).splitlines()
            if not starts:
                raise ValueError("The item's start commit could not be read")
            known = []
            for number, result in enumerate(review._history(
                    top, item, starts[0], state.get("review") or {}, ref=head), 1):
                score.remember(known, result, number, {})
        rows = _rows(item, known)
    temp = cache.with_suffix(f".{os.getpid()}.tmp")
    try:
        temp.write_text(json.dumps(rows), encoding="utf-8")
        os.replace(temp, cache)
    except OSError:
        pass  # A read-only Git directory must not prevent a view.
    finally:
        temp.unlink(missing_ok=True)
    return rows


def collect(top: Path, copies: dict[str, tuple[dict[str, Any], Path | str]], landed: str) -> list[dict[str, Any]]:
    """The board selects default-branch lists first, including empty lists. Each saved list uses
    its own branch or worktree's files; older merged items use the default branch's files.
    A problem in a file that no longer exists is left out; one with no file stays.

    The paginated GitHub listing has no time cutoff: the board's six-week runway
    must not discard findings kept earlier in the repo's life.
    """
    saved = {item: state["known"] for item, (state, _) in copies.items() if "known" in state}

    def inventory(_now: Any) -> list[dict[str, Any]] | None:
        # A query-string ampersand becomes a command separator through gh.cmd on Windows.
        done = repo.run("gh", "api", "--paginate", "--method", "GET", "--raw-field", "per_page=100",
                        "repos/{owner}/{repo}/pulls?state=closed", "--jq",
                        ".[] | select(.merged_at != null) | {number, headRefName: .head.ref}", cwd=top)
        if done.returncode:
            return None
        try:
            prs = [json.loads(line) for line in done.stdout.splitlines() if line.strip()]
        except ValueError:
            return None
        return [pr for pr in prs if isinstance(pr, dict)
                and str(pr.get("headRefName") or "").startswith(("fix/", "task/", "story/"))]

    prs = board_facts._cached(top, "known-issues-prs-cache", inventory, stale=True, seconds=86400)
    saved_branches = {state.get("branch") for item, (state, _) in copies.items() if item in saved}

    def historical(_now: Any) -> list[dict[str, Any]] | None:
        if prs is None:
            return None
        rows = []
        for pr in prs:
            # No fetch is needed for items whose current landed list is available.
            if pr["headRefName"] in saved_branches:
                continue
            try:
                rows.extend(_pull(top, pr))
            except (subprocess.CalledProcessError, ValueError, KeyError, OSError):
                return None  # Keep the last complete read and retry when GitHub is reachable.
        return rows

    # Cache the inventory, not the projection of it through today's saved lists.
    # Rebuild that projection each request; the aggregate is only an outage fallback
    # (also seeded by upgrade). Individual PR evidence remains immutable in _pull.
    older = board_facts._cached(top, "known-issues", historical, stale=True, seconds=0) or []
    rows = [row for row in older if row["item"] not in saved]
    rows.extend(row for item, known in saved.items() for row in _rows(item, known))
    sources = {item: where for item, (_, where) in copies.items() if item in saved}
    present = {source: set(repo.git("ls-tree", "-r", "-z", "--name-only",
                                   "HEAD" if isinstance(source, Path) else source,
                                   cwd=source if isinstance(source, Path) else top).split("\0"))
               for source in {landed, *sources.values()}}
    rows = [row for row in rows if not row["file"] or row["file"] in present[sources.get(row["item"], landed)]]
    return sorted(rows, key=lambda row: (row["item"], row["file"], row["line"], row["title"]))
