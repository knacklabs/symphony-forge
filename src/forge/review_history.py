"""Merge review snapshots without separating findings from their dispositions."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from forge import repo, score


def _key(result: dict[str, Any]) -> tuple[str, str]:
    return (str(result.get("commit", "")),
            json.dumps(result.get("findings", []), sort_keys=True, separators=(",", ":")))


def merge_review_snapshots(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep distinct review rounds and union concurrent dismissals for the same snapshot."""
    merged: list[dict[str, Any]] = []
    positions: dict[tuple[str, str], int] = {}
    for row in rows:
        key = _key(row)
        if key not in positions:
            positions[key] = len(merged)
            merged.append(copy.deepcopy(row))
            continue
        current = merged[positions[key]]
        dismissals = current.setdefault("dismissals", [])
        dismissals.extend(copy.deepcopy(value) for value in row.get("dismissals", [])
                          if value not in dismissals)
    return merged


class ReviewHistory(list[dict[str, Any]]):
    """A JSON-compatible list with Git ancestry kept outside its saved review rows."""

    def __init__(self, rows=(), origins=(), ancestors=(), legacy_order=()):
        super().__init__(rows)
        self.origins = list(origins)
        self.ancestors = list(ancestors)
        self.legacy_order = list(legacy_order)


def history(top: Path, item: str, base: str, previous: dict[str, Any],
            ref: str = "HEAD", *, state: dict[str, Any] | None = None,
            path: str = "", section: str = "", include_merged: bool = False,
            saved_rounds: list[dict[str, Any]] | None = None,
            bind=None) -> ReviewHistory:
    """Read review snapshots and retain their first record commit as transient provenance."""
    path = path or repo.state_path(item)
    found: list[tuple[dict[str, Any], str | None, int | None]] = []
    traversal = "--full-history"
    commits = repo.git("rev-list", "--reverse", traversal, f"{base}..{ref}" if base else ref,
                       "--", path, cwd=top).split()
    for sha in commits:
        saved = json.loads(repo.git("show", f"{sha}:{path}", cwd=top))
        result = (saved.get(section, {}) if section else saved).get("review") or {}
        if result.get("commit"):
            if bind:
                bind(result)
            found.append((result, sha, None))

    rows = merge_review_snapshots([row for row, _, _ in found])
    first = {}
    for row, origin, legacy in found:
        first.setdefault(_key(row), (origin, legacy))
    annotated = [(row, *first[_key(row)]) for row in rows]

    if saved_rounds:
        by_key = {_key(row): row for row, _, _ in annotated}
        from_saved = []
        for index, row in enumerate(saved_rounds):
            key = _key(row)
            if key in by_key:
                combined = merge_review_snapshots([by_key[key], row])[0]
                origin = first.get(key, (None, None))[0]
            else:
                combined, origin = copy.deepcopy(row), None
            from_saved.append((combined, origin, index))
        included = {_key(row) for row, _, _ in from_saved}
        annotated = from_saved + [entry for entry in annotated if _key(entry[0]) not in included]

    if previous.get("commit"):
        if bind:
            bind(previous)
        key = _key(previous)
        match = next((index for index, (row, _, _) in enumerate(annotated) if _key(row) == key), None)
        if match is None:
            annotated.append((copy.deepcopy(previous), repo.git("rev-parse", ref, cwd=top), None))
        else:
            row, origin, order = annotated.pop(match)
            annotated.append((merge_review_snapshots([row, previous])[0], origin, order))

    origins = [origin for _, origin, _ in annotated]
    ancestors = []
    unique = set(filter(None, origins))
    for origin in origins:
        ancestors.append({candidate for candidate in unique if candidate != origin and
                          repo.run("git", "merge-base", "--is-ancestor", candidate, origin,
                                   cwd=top).returncode == 0} if origin else set())
    return ReviewHistory([row for row, _, _ in annotated], origins, ancestors,
                         [order for _, _, order in annotated])


def settled(history: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    """Settle findings only when every saved occurrence precedes the absent review."""
    origins = getattr(history, "origins", [None] * len(history))
    ancestors = getattr(history, "ancestors", [set() for _ in history])
    legacy_order = getattr(history, "legacy_order", [None] * len(history))

    def precedes(older: int, newer: int) -> bool:
        if origins[older] and origins[newer]:
            if origins[older] == origins[newer]:
                return (legacy_order[older] is not None and legacy_order[newer] is not None
                        and legacy_order[older] < legacy_order[newer])
            return origins[older] in ancestors[newer]
        if legacy_order[older] is not None and legacy_order[newer] is not None:
            return legacy_order[older] < legacy_order[newer]
        return not origins[older] and not origins[newer] and older < newer

    def follows(older: int, newer: int) -> bool:
        return precedes(newer, older)

    current_findings = [{score.identity(f["file"], f["title"])
                         for f in result.get("findings", [])} for result in history]
    occurrences: dict[tuple[str, str], list[int]] = {}
    for index, keys in enumerate(current_findings):
        for key in keys:
            occurrences.setdefault(key, []).append(index)

    settled, earlier, names = {}, set(), {}
    for index, result in enumerate(history):
        current = current_findings[index]
        names = {**{score.identity(f["file"], f["title"]): (f["file"], f["title"])
                    for f in result.get("findings", [])}, **names}
        for key in earlier - current:
            found = occurrences.get(key, [])
            if (found and any(precedes(source, index) for source in found)
                    and all(precedes(source, index) or follows(source, index) for source in found)):
                settled.setdefault(key, "fixed: absent from a later review")
        for finding in score.open_findings(result):
            if finding.get("required_done_when") and not str(finding.get("follow_up", "")).startswith("Split into"):
                continue
            if (outcome := score.bar(score.of(finding))) in ("follow-up", "live with"):
                settled.setdefault(score.identity(finding["file"], finding["title"]),
                                   f"known: below the bar ({outcome})")
            if finding.get("follow_up"):
                settled.setdefault(score.identity(finding["file"], finding["title"]),
                                   "known: " + finding["follow_up"])
        accepted = set()
        for dismissal in result.get("dismissals", []):
            finding = result["findings"][dismissal["finding"] - 1]
            key = score.identity(finding["file"], finding["title"])
            if dismissal.get("accepted"):
                accepted.add(key)
                settled[key] = "accepted by the owner: " + dismissal["because"]
            else:
                settled[key] = (dismissal["because"] if dismissal["because"].startswith(
                    ("known:", "accepted by the owner:")) else "dismissed because " + dismissal["because"])
        earlier = (earlier | current) - accepted
    return {names[key]: reason for key, reason in settled.items()}
