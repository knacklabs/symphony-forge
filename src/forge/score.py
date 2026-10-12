"""Gain, Work and Harm: the reviewer's and reader's scores on each note, the Harm floor and the bar.

The score line is `Gain <g>, Work <w>, Harm <h>`, each 1 to 5: a review finding's body carries it
as its first line, a cold-read note as its last. A note without one has no scores: a saved review
is judged by priority and a saved read note by its label, as before scores.
"""
from __future__ import annotations

import re

# Each score is one integer 1 to 5; "Harm 1.5" or "Harm 12" is no score line.
LINE = re.compile(r"^([ \t]*)Gain ([1-5]), Work ([1-5]), Harm ([1-5])(?:[ \t].*)?$", re.M)
FLOORS = ((re.compile(r"^[ \t]*Raise:[ \t]*Security\b", re.I | re.M), "security"),
          (re.compile(r"^[ \t]*Raise:[ \t]*Data loss\b", re.I | re.M), "data loss"),
          (re.compile(r"\bmigrations?\b", re.I), "migration"))
Scores = tuple[int, int, int]


def parse(text: str) -> Scores | None:
    """The (gain, work, harm) on a text's score line, or None when it has none in range."""
    found = LINE.search(text)
    return (int(found[2]), int(found[3]), int(found[4])) if found else None


def normalise(title: str, body: str) -> tuple[Scores | None, str]:
    """The scores with the Harm floor applied, and the body with its score line rewritten: a
    security, data-loss or migration note never scores Harm below 4."""
    scores = parse(body)
    if not scores:
        return None, body
    gain, work, harm = scores
    why = next((name for pattern, name in FLOORS
                if pattern.search(body if name != "migration" else f"{title}\n{body}")), "")
    line = f"Gain {gain}, Work {work}, Harm {harm}"
    if why and harm < 4:
        harm, line = 4, f"Gain {gain}, Work {work}, Harm 4 (floor: {why})"
    return (gain, work, harm), LINE.sub(lambda match: match[1] + line, body, count=1)


def strip(body: str) -> str:
    """A body without its score line, for names, slugs and one-line summaries."""
    return LINE.sub("", body, count=1).strip("\n")


def notes(said: str) -> str:
    """A reader's numbered notes with the Harm floor applied to each scored one."""
    def one(block: str) -> str:
        title, _, body = block.partition("\n")
        return f"{title}\n{normalise(title, body)[1]}" if body else block
    return "".join(one(block) for block in re.split(r"(?=^\d+\.[ \t])", said, flags=re.M))


def bar(scores: Scores | None) -> str | None:
    """What a scored note does: `block` and `fix now` hold the work; `follow-up` and `live with`
    don't. None for a note with no scores."""
    if not scores:
        return None
    gain, work, harm = scores
    if harm >= 4 or gain == 5:
        return "block"
    if gain >= 3:
        return "fix now" if work <= 2 else "follow-up"
    return "live with"


def table(rows: list[tuple[str, Scores | None]]) -> list[str]:
    """The open notes as a stop question lists them: each row is (problem, scores)."""
    # ponytail: today's bullets; the ranked table replaces them when every row has scores.
    return [f"- {problem}" for problem, _ in rows]
