"""Findings the builder never needs: a story task's `Not done` on builder guidance, and repeats."""
import re
from pathlib import Path
from typing import Any


def sentence(text: str) -> str:
    text = re.sub(r"^\d+[.)]\s*", "", text.replace("**", "").replace("`", "").strip())
    return " ".join(text.casefold().split()).rstrip(".").strip('"\u201c\u201d\u2018\u2019\'').rstrip(".")


def approved(top: Path, item: str, commit: str | None = None) -> set[str]:
    """The task's covered, owner-approved Done-when sentences; empty for a fix."""
    from forge import review, story

    if "/" not in item:
        return set()
    text, _, row = review.task(top, item, commit)
    doc = story.parse(text)
    covers = {int(n) for n in re.findall(r"\d+", row.get("covers", ""))}
    return {sentence(doc["done"][n]) for n in covers if n in doc["done"]}


def drop(top: Path, item: str, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop a story task's `Not done` note on builder guidance (never a security or data-loss one)
    and exact repeats in one round, keeping the higher priority of two repeats."""
    from forge import score

    owned, kept = approved(top, item), {}
    for finding in findings:
        title = re.sub(r"^\[P[0-3]\]\s*", "", finding["title"].strip())
        missed = re.match(r"Not done\s*:\s*(.*)", title, re.I)
        said = sentence(missed[1]) if missed else ""
        if (not score.holds(finding, "P0") and "/" in item and missed and not finding.get("follow_up")
                and not any(said in a or a in said for a in owned if a)
                and not any(p.search(finding["body"]) for p, _ in score.FLOORS[:2])):
            continue
        key = tuple(str(finding.get(k, "")).strip() for k in ("title", "file", "line", "body"))
        if key not in kept or finding["priority"] < kept[key]["priority"]:
            kept[key] = finding
    return list(kept.values())
