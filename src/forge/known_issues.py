"""Kept review findings from landed lists and original, pre-squash review history."""
import json
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


def collect(top: Path, states: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Default-branch lists win, including empty lists. Older items use their PR heads.

    The paginated GitHub listing has no time cutoff: the board's six-week runway
    must not discard findings kept earlier in the repo's life.
    """
    saved = {item: state["known"] for item, state in states.items() if "known" in state}

    def historical(_now: Any) -> list[dict[str, Any]] | None:
        done = repo.run("gh", "api", "--paginate",
                        "repos/{owner}/{repo}/pulls?state=closed&per_page=100", "--jq",
                        ".[] | select(.merged_at != null) | {number, headRefName: .head.ref}", cwd=top)
        if done.returncode:
            return None
        try:
            prs = [json.loads(line) for line in done.stdout.splitlines() if line.strip()]
        except ValueError:
            return None
        rows = []
        for pr in prs:
            if not isinstance(pr, dict) or not str(pr.get("headRefName") or "").startswith(("fix/", "task/", "story/")):
                continue
            # No fetch is needed for items whose current landed list is available.
            if any(state.get("branch") == pr["headRefName"] for item, state in states.items() if item in saved):
                continue
            try:
                fetched = repo.run("git", "fetch", "-q", "--no-tags", "origin",
                                   f"refs/pull/{pr['number']}/head", cwd=top)
                fetched.check_returncode()
                head = repo.git("rev-parse", "FETCH_HEAD", cwd=top)
                identity = backfill._identity(top, head, pr["headRefName"])
                if identity is None:
                    continue
                item, state = identity
                if item in saved:
                    continue
                known = state.get("known")
                if known is None:
                    starts = repo.git("log", "--reverse", "--diff-filter=A", "--format=%H", head,
                                      "--", repo.state_path(item), cwd=top).splitlines()
                    if not starts:
                        continue
                    known = []
                    for number, result in enumerate(review._history(
                            top, item, starts[0], state.get("review") or {}, ref=head), 1):
                        score.remember(known, result, number, {})
                rows.extend(_rows(item, known))
            except (subprocess.CalledProcessError, ValueError, KeyError, OSError):
                return None  # Keep the last complete read and retry when GitHub is reachable.
        return rows

    older = board_facts._cached(top, "known-issues", historical, stale=True) or []
    rows = [row for row in older if row["item"] not in saved]
    rows.extend(row for item, known in saved.items() for row in _rows(item, known))
    return sorted(rows, key=lambda row: (row["item"], row["file"], row["line"], row["title"]))
