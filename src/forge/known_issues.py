"""Kept review findings from landed lists and original, pre-squash review history."""
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from forge import backfill, board_facts, repo, review, score, time_records


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


def inventory(top: Path) -> list[dict[str, Any]] | None:
    """Every merged Forge PR, without a time cutoff. GitHub's last-page link lets
    independent pages overlap rather than adding a network round trip per page."""
    def page(number: int, size: int = 100) -> tuple[list[dict[str, Any]], int] | None:
        # A query-string ampersand becomes a command separator through gh.cmd on Windows.
        done = repo.run("gh", "api", "--include", "--method", "GET", "--raw-field", f"per_page={size}",
                        *(("--raw-field", f"page={number}") if number != 1 else ()),
                        "repos/{owner}/{repo}/pulls?state=closed", "--jq",
                        ".[] | select(.merged_at != null) | {number, headRefName: .head.ref}", cwd=top)
        if done.returncode:
            return None
        headers, separator, body = done.stdout.replace("\r\n", "\n").partition("\n\n")
        if not separator or not headers.startswith("HTTP/"):
            return None
        last = re.search(r'<[^>]*[?&]page=(\d+)[^>]*>;\s*rel="last"', headers)
        if 'rel="next"' in headers and last is None:
            return None  # An incomplete inventory must not replace the last complete read.
        try:
            prs = [json.loads(line) for line in body.splitlines() if line.strip()]
        except ValueError:
            return None
        return prs, int(last[1]) if last else number

    def fetch(_now: Any) -> list[dict[str, Any]] | None:
        # A complete recent window can extend the last complete inventory. Keep
        # every older PR by number; a gap longer than the window needs a full read.
        try:
            previous = json.loads((repo.forge_dir(top) / "known-issues-prs-cache.json").read_text("utf-8"))
            at = time_records.when(previous.get("fetched_at"))
            old = previous["data"]
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            at, old = None, None
        if at and at <= _now and isinstance(old, list):
            recent = board_facts.prs(top)
            weeks = (recent or {}).get("weeks") or []
            starts = [time_records.when(week.get("start")) for week in weeks]
            if (weeks and all(week.get("complete") for week in weeks) and all(starts)
                    and min(start for start in starts if start is not None) <= at):
                by_number = {pr["number"]: pr for pr in old}
                by_number.update({pr["number"]: {"number": pr["number"], "headRefName": pr["headRefName"]}
                                  for pr in board_facts.merged_prs(recent)
                                  if str(pr.get("headRefName") or "").startswith(("fix/", "task/", "story/"))})
                return list(by_number.values())
        # A one-row probe gives the total through its last-page link without
        # downloading a large page before the other pages can start.
        first = page(1, 1)
        if first is None:
            return None
        prs, last = first
        if last > 1:
            last = (last + 99) // 100
            with ThreadPoolExecutor(min(12, last)) as pool:
                pages = list(pool.map(page, range(1, last + 1)))
            if None in pages:
                return None
            prs = [pr for result in pages if result is not None for pr in result[0]]
        return [pr for pr in prs if isinstance(pr, dict)
                and str(pr.get("headRefName") or "").startswith(("fix/", "task/", "story/"))]

    return board_facts._cached(top, "known-issues-prs-cache", fetch, stale=True)


def collect(top: Path, copies: dict[str, tuple[dict[str, Any], Path | str]], landed: str) -> list[dict[str, Any]]:
    """The board selects default-branch lists first, including empty lists. Each saved list uses
    its own branch or worktree's files; older merged items use the default branch's files.
    A problem in a file that no longer exists is left out; one with no file stays.
    """
    saved = {item: state["known"] for item, (state, _) in copies.items() if "known" in state}

    prs = inventory(top)
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
