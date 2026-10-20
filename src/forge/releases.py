"""Release dates and membership from version tags on the default branch."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from forge import board_facts, repo

VERSION = re.compile(r"v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z][0-9A-Za-z.+-]*)?")


def collect(top: Path, history: dict[str, Any], maps: list[dict[str, Any]],
            items: dict[str, Any]) -> dict[str, Any]:
    from forge.board import STATE

    landed = history["landed"]
    tags = []
    for line in repo.git("for-each-ref", f"--merged={landed}",
                         "--format=%(refname:strip=2)%00%(objecttype)%00%(taggerdate:iso-strict)",
                         "refs/tags", cwd=top).splitlines():
        tag, kind, date = line.split("\0")
        if VERSION.fullmatch(tag):
            tags.append({"tag": tag, "date": date if kind == "tag" else None, "items": []})
    released = {}
    if tags:
        # Ancestry orders releases even when dates are unknown or clocks disagree.
        order = {commit: n for n, commit in enumerate(repo.git(
            "rev-list", "--topo-order", "--reverse", landed, cwd=top).splitlines())}
        tips = {entry["tag"]: repo.git("rev-parse", f"refs/tags/{entry['tag']}^{{commit}}", cwd=top)
                for entry in tags}
        tags.sort(key=lambda entry: (order[tips[entry["tag"]]], entry["tag"]))

        def published(_now: Any) -> dict[str, str] | None:
            if not shutil.which("gh"):
                return None
            done = repo.run("gh", "api", "repos/{owner}/{repo}/releases", "--paginate", "--slurp", cwd=top)
            try:
                pages = json.loads(done.stdout) if not done.returncode else []
                return {release["tag_name"]: release["published_at"] for page in pages for release in page
                        if release.get("published_at") and not release.get("draft")}
            except (ValueError, TypeError, KeyError, AttributeError):
                return None

        dates = board_facts._cached(top, "release-dates", published) or {}
        merges = {}
        log = repo.git("log", "--first-parent", "--diff-filter=A", "--no-renames",
                       "--format=%x00%H%x00", "--name-only", landed, "--",
                       ".factory/stories", ".factory/fixes", cwd=top).split("\0")[1:]
        for commit, paths in zip(log[::2], log[1::2]):
            for path in paths.splitlines():
                match = STATE.fullmatch(path)
                state = history["states"].get(path)
                if match and state is not None and state.get("kind") != "story-done" and state.get("status") != "dropped":
                    if match["task"] or match["fix"]:
                        item = f"{match['key']}/{match['task']}" if match["task"] else match["fix"]
                        merges[item] = commit
        for entry in tags:
            entry["date"] = dates.get(entry["tag"]) or entry["date"] or None
            ancestors = set(repo.git("rev-list", tips[entry["tag"]], cwd=top).splitlines())
            for item, commit in merges.items():
                if item not in released and commit in ancestors:
                    released[item] = entry["tag"]
        positions = {entry["tag"]: n for n, entry in enumerate(tags)}
        for plan in maps:
            parts = [part["id"] for part in plan["parts"]]
            if plan.get("stage") == "done" and parts and all(part in released for part in parts):
                released[plan["id"]] = max((released[part] for part in parts), key=positions.get)
        for entry in tags:
            entry["items"] = sorted(item for item, tag in released.items() if tag == entry["tag"])
    for parent in items.values():
        for row in [parent, *parent["children"]]:
            row["released_in"] = released.get(row["id"])
    return {"releases": tags, "release_note": None if tags else "no releases tagged"}
