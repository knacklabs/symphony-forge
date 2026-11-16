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
    """Drop a story task's `Not done` note on builder guidance and repeats of a title in one round."""
    owned, seen, kept = approved(top, item), set(), []
    for finding in findings:
        title = re.sub(r"^\[P[0-3]\]\s*", "", finding["title"])
        missed = re.match(r"Not done\s*:\s*(.*)", title, re.I)
        if "/" in item and missed and not any(sentence(missed[1]).startswith(a) for a in owned):
            continue
        key = (finding["file"], sentence(title))
        if key not in seen:
            seen.add(key)
            kept.append(finding)
    return kept
