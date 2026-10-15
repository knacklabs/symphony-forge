"""Gain, Work and Harm: the reviewer's and reader's scores on each note, the Harm floor and the bar.

The score line is `Gain <g>, Work <w>, Harm <h>`, each 1 to 5: a review finding's body carries it
as its first line, a cold-read note as its last. A note without one has no scores: a saved review
is judged by priority and a saved read note by its label, as before scores.
"""
from __future__ import annotations

import re
from typing import Any

# Each score is one integer 1 to 5; "Harm 1.5" or "Harm 12" is no score line.
LINE = re.compile(r"^([ \t]*)Gain ([1-5]), Work ([1-5]), Harm ([1-5])(?:[ \t].*)?$", re.M)
FLOORS = ((re.compile(r"^[ \t]*Raise:[ \t]*Security\b", re.I | re.M), "security"),
          (re.compile(r"^[ \t]*Raise:[ \t]*Data loss\b", re.I | re.M), "data loss"),
          (re.compile(r"\bmigrations?\b", re.I), "migration"))
ADVISORY = re.compile(r"^[ \t]*Advisory:[ \t]*\S", re.I)
HOLD = ("block", "fix now")
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
    """A reader's numbered notes, Harm floor applied and below-bar ones given their disposition."""
    def one(block: str) -> str:
        title, _, body = block.partition("\n")
        if not body:
            return block
        scores, body = normalise(title, body)
        if (outcome := bar(scores)) not in (None, *HOLD):
            kept = body.rstrip("\n")
            body = f"{kept}\n   Disposition: keep - below the bar ({outcome})" + body[len(kept):]
        return f"{title}\n{body}"
    return "".join(one(block) for block in re.split(r"(?=^\d+\.[ \t])", said, flags=re.M))


def bar(scores: Scores | None) -> str | None:
    """What a scored note does: `block` and `fix now` hold the work; `follow-up` and `live with`
    don't. None for a note with no scores."""
    if not scores:
        return None
    gain, work, harm = scores
    if harm >= 4 or gain == 5:
        return "block"
    if gain == 4 or (gain == 3 and harm == 3):
        return "fix now" if work <= 2 else "follow-up"
    if gain == 3:
        return "follow-up"
    return "live with"


def who(_rows: list[tuple[int, str, Scores | None]], ask: str) -> str:
    """The owner decides a stopped loop, whatever the scores."""
    return ask


WORDS = {"block": "fix now", "fix now": "fix this round", "follow-up": "follow-up fix", "live with": "live with"}


def table(rows: list[tuple[int, str, Scores | None]]) -> list[str]:
    """The open notes as a stop question lists them, each row (number, problem, scores): one table
    ranked by the bar, then Harm and Gain high first, then Work low first; bullets when any is unscored."""
    if not rows or any(scores is None for *_, scores in rows):
        return [f"- {problem}" for _, problem, _ in rows]
    order = list(WORDS)
    ranked = sorted(rows, key=lambda row: (order.index(bar(row[2])), -row[2][2], -row[2][0], row[2][1]))
    return ["| # | Problem, for whom | Gain | Work | Harm | Proposed |", "|---|---|---|---|---|---|",
            *(f"| {number} | {problem.replace('|', '/')} | {gain} | {work} | {harm} | {WORDS[bar((gain, work, harm))]} |"
              for number, problem, (gain, work, harm) in ranked)]


def of(finding: dict[str, Any]) -> Scores | None:
    return (finding["gain"], finding["work"], finding["harm"]) if "harm" in finding else None


def holds(finding: dict[str, Any], level: str | None = "P1") -> bool:
    """A finding holds work by the bar (only `block` at the P0-only level), or unscored by priority."""
    outcome = bar(of(finding))
    if outcome is None:
        return finding.get("priority") in (("P0",) if level == "P0" else ("P0", "P1"))
    return outcome == "block" if level == "P0" else outcome in HOLD


def note_holds(note: str) -> bool:
    """A read note (text after its number) holds by the bar, or unscored unless `Advisory:`."""
    outcome = bar(parse(note))
    return outcome in HOLD if outcome else not ADVISORY.match(note)


def read_stops(notes: list[str]) -> bool:
    """A third blocked read stops on an unscored or disputed-keep note at the bar, or any Harm 3+."""
    for note in (re.sub(r"^\d+\.[ \t]+", "", note) for note in notes):
        scores, held = parse(note), note_holds(note)  # a note below the bar is settled by its disposition
        if held and (not scores or "disputed keep" in note.partition("\n")[0].casefold()) \
                or scores and scores[2] >= 3 and (held or "Disposition:" not in note):
            return True
    return False


def identity(file: Any, title: Any) -> tuple[str, str]:
    return " ".join(str(file).split()).casefold(), " ".join(str(title).split()).casefold()


def open_findings(result: dict[str, Any]) -> list[dict[str, Any]]:
    dismissed = {d.get("finding") for d in result.get("dismissals", []) if isinstance(d, dict)}
    return [f for n, f in enumerate(result.get("findings", []), 1) if n not in dismissed]


def loop_stops(result: dict[str, Any], known: list[dict[str, Any]], round_number: int) -> bool:
    """Close's three-round stop: an open Harm 3+, a repeat at the bar, or an unscored one that holds."""
    earlier = {identity(e["file"], e["title"]) for e in known if e.get("round", 0) < round_number}
    level = result.get("blocking_level")
    return any(holds(f, level) and (not of(f) or identity(f["file"], f["title"]) in earlier)
               or f.get("harm", 0) >= 3 for f in open_findings(result))


def remember(known: list[dict[str, Any]], result: dict[str, Any], round_number: int,
             areas: dict[tuple[str, str], str]) -> list[dict[str, Any]]:
    """Add a round to the known findings, never removed; only open or owner-accepted entries change."""
    because = {d["finding"]: d["because"] for d in result.get("dismissals", [])}
    by = {identity(e["file"], e["title"]): e for e in known}
    raised = set()
    for n, f in enumerate(result.get("findings", []), 1):
        raised.add(key := identity(f["file"], f["title"]))
        reason = because.get(n, "")
        outcome = ("lived with" if reason.startswith("settled area") else "accepted" if n in because
                   else "open" if holds(f, result.get("blocking_level"))
                   else "follow-up" if bar(of(f)) == "follow-up" else "lived with")
        if key not in by:
            known.append(by.setdefault(key, {
                "title": f["title"], "file": f["file"], "line": f["line"], "gain": f.get("gain"),
                "work": f.get("work"), "harm": f.get("harm"), "outcome": outcome, "reason": reason,
                "round": round_number, "area": areas.get(key, f["file"]), "security": bool(FLOORS[0][0].search(f["body"]))}))
        elif by[key]["outcome"] == "open" or any(d.get("accepted") and d["finding"] == n for d in result["dismissals"]):
            by[key].update(outcome=outcome, reason=reason)
    for key, entry in by.items():
        if entry["outcome"] == "open" and key not in raised:
            entry["outcome"] = f"fixed in round {round_number}"
    return known


def crowded(known: list[dict[str, Any]], result: dict[str, Any], settled: list[str],
            areas: dict[tuple[str, str], str]) -> str:
    """The unsettled area holding work this round with three distinct findings that held work."""
    for f in open_findings(result):
        area = areas.get(identity(f["file"], f["title"]), f["file"])
        if holds(f, result.get("blocking_level")) and area not in settled and sum(
                e.get("area") == area and e["outcome"] not in ("follow-up", "lived with") for e in known) >= 3:
            return area
    return ""


def move(known: list[dict[str, Any]], area: str) -> str:
    """The structural move a stopped area proposes; fail closed first after any security finding there."""
    moves = ["cut the code that invites these findings", "replace the cases with one general rule",
             "narrow that Done when item", "make it fail closed"]
    if any(e.get("area") == area and e.get("security") for e in known):
        moves.insert(0, moves.pop())
    return "; or ".join(moves)
