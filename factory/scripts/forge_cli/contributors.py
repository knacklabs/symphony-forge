"""Who commits to this repo, and how much of it goes through Forge.

A repo can be worked by people who drive the factory and people who commit
straight to it. The board's Contributors view shows both, from facts the repo
already holds:

- git history: author names and emails (with `.mailmap` applied, git's own
  alias file), dates, and whether a commit carries Forge's fingerprints -- a
  story/task scope in the subject or a Forge trailer in the body;
- GitHub handles, read from GitHub's no-reply commit emails
  (`123+handle@users.noreply.github.com`), so no network call is needed;
- Forge records under `.factory/` and `plans/`, which name the human who
  approved a plan (`approved_by`), confirmed a decision (`by`) or ran a stage
  (`actor`).

One person usually commits under several identities (work and personal email,
the GitHub web editor's no-reply address, a first name on one laptop and a full
name on another). Identities are merged when they share an email, a GitHub
handle or a recognisably similar name; anything git cannot tell apart is fixed
the standard way, with a `.mailmap` entry.

Memoised against git's refs and the record trees, so the view costs one
`git log` per new commit, not per poll.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

from . import fscache

# A Forge commit names its story/task in the subject -- `WF-2 T1: task proof`,
# `feat(WF-2/T1): ...`, `PURCHASE-1 T2a ...` -- or carries a Forge trailer.
STORY_SCOPE = re.compile(
    r"(?:^|\()(?P<story>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)(?:[ /]T\d+[a-z]?\b)")
FORGE_TRAILER = re.compile(
    r"^(?:Confirmed-by|Proof|Ticket:\s*Q-|Forge-[A-Za-z-]+|Stage|Task-proof)\b",
    re.MULTILINE)
NOREPLY = re.compile(r"^(?:\d+\+)?(?P<handle>[A-Za-z0-9-]+)@users\.noreply\.github\.com$",
                     re.IGNORECASE)
# Automation that commits under its own identity: not a contributor.
BOT = re.compile(r"\[bot\]|^forge-|noreply@anthropic|^codex|^claude|^github-actions|^dependabot",
                 re.IGNORECASE)
# A git author name shaped like a GitHub handle (`kl-nandeeshwar`).
HANDLE_LIKE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$|^[a-z]+[0-9]+$")
# Record fields that name a human, and what that human did.
ROLE_FIELDS = {"approved_by": "Approves plans", "by": "Confirms decisions",
               "actor": "Runs tasks"}
ROLE_VALUE = re.compile(r'"(approved_by|by|actor)"\s*:\s*"([^"]{1,80})"')
# Values those fields take when an agent, not a person, acted.
AGENT_NAMES = {"orchestrator", "autoreview", "implementer", "griller", "human",
               "planner", "reviewer", "codex", "claude", "forge", "system",
               "coordinator", "worker", "ci"}
WINDOWS = {"30": 30, "90": 90}
RECORD_ROOTS = (".factory", "plans")
RECORD_FILE_LIMIT = 20000


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _is_agent(value: str) -> bool:
    low = value.strip().lower()
    return (not low or low in AGENT_NAMES or ":" in low
            or low.startswith(("gpt", "claude", "codex")))


def _git_log(base: Path) -> list[dict]:
    """Every non-merge commit reachable from any ref, bots left out."""
    fmt = "%aN%x1f%aE%x1f%as%x1f%s%x1f%b%x1e"
    try:
        out = subprocess.run(
            ["git", "-C", str(base), "-c", "i18n.logOutputEncoding=UTF-8",
             "log", "--all", "--no-merges", f"--format={fmt}"],
            capture_output=True, check=True, timeout=120,
        ).stdout.decode("utf-8")
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return []
    commits = []
    for chunk in out.split("\x1e"):
        parts = chunk.strip("\n").split("\x1f")
        if len(parts) < 5:
            continue
        name, email, day, subject, body = (part.strip() for part in parts[:5])
        if BOT.search(name) or BOT.search(email):
            continue
        story = STORY_SCOPE.search(subject)
        noreply = NOREPLY.match(email)
        commits.append({
            "name": name, "email": email.lower(), "date": day,
            # Kept in the case its owner chose; GitHub matches it either way.
            "handle": noreply.group("handle") if noreply else None,
            "forge": bool(story or FORGE_TRAILER.search(body)),
            "story": story.group("story") if story else None,
        })
    return commits


def _record_names(base: Path) -> dict[str, set[str]]:
    """Human name -> the roles Forge records credit them with."""
    found: dict[str, set[str]] = {}
    seen = 0
    for root in RECORD_ROOTS:
        for parent, _dirs, names in os.walk(base / root):
            for name in names:
                if not name.endswith(".json"):
                    continue
                seen += 1
                if seen > RECORD_FILE_LIMIT:
                    return found
                try:
                    text = Path(parent, name).read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                for field, value in ROLE_VALUE.findall(text):
                    if not _is_agent(value):
                        found.setdefault(value.strip(), set()).add(ROLE_FIELDS[field])
    return found


class _Union:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, key: str) -> str:
        self.parent.setdefault(key, key)
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def join(self, a: str, b: str) -> None:
        self.parent[self.find(a)] = self.find(b)


def _join_similar_names(union: _Union, names: set[str]) -> None:
    """Fold the spellings one person leaves across machines: `Prashant`,
    `Prashant Anand` and `prashant-caw`; `AayushbajajCAW` and `Aayush Bajaj`.
    A bare first name, a handle segment, or a name another full name starts
    with all point at the same person. Two people who really share a first
    name are told apart with a `.mailmap` entry giving each a full name."""
    first_word: dict[str, list[str]] = {}
    for name in names:
        words = name.split()
        if len(words) > 1:
            first_word.setdefault(_norm(words[0]), []).append(name)
    full = {_norm(n) for n in names if len(n.split()) > 1 and len(_norm(n)) >= 6}
    for name in names:
        key = _norm(name)
        tokens = {key} if len(name.split()) == 1 else set()
        if "-" in name:
            tokens |= {_norm(t) for t in name.split("-") if len(t) >= 4}
        for token in tokens:
            for other in first_word.get(token, []):
                union.join(f"n:{_norm(other)}", f"n:{key}")
        for other in full:
            if key != other and key.startswith(other):
                union.join(f"n:{other}", f"n:{key}")


def _display_name(names: dict[str, int], handle: str | None) -> str:
    """The most human of a person's names: a full name first, then one not
    shaped like a handle, then the most used."""
    candidates = [n for n in names if not handle or _norm(n) != _norm(handle)] or list(names)
    return max(candidates, key=lambda n: (" " in n, not HANDLE_LIKE.match(n), names[n], len(n)))


def build(base: Path, today: date | None = None) -> dict:
    commits = _git_log(base)
    union = _Union()
    _join_similar_names(union, {c["name"] for c in commits})
    for commit in commits:
        ident = f"e:{commit['email']}"
        union.join(f"n:{_norm(commit['name'])}", ident)
        if commit["handle"]:
            union.join(f"h:{commit['handle'].lower()}", ident)
            # The GitHub web editor authors as the handle itself.
            union.join(f"n:{_norm(commit['handle'])}", ident)

    today = today or date.today()
    cutoffs = {key: (today - timedelta(days=days)).isoformat() for key, days in WINDOWS.items()}
    people: dict[str, dict] = {}
    for commit in commits:
        person = people.setdefault(union.find(f"e:{commit['email']}"), {
            "names": {}, "emails": set(), "handles": set(), "stories": {},
            "first": commit["date"], "last": commit["date"],
            "windows": {key: {"commits": 0, "forge": 0} for key in (*WINDOWS, "all")},
        })
        person["names"][commit["name"]] = person["names"].get(commit["name"], 0) + 1
        person["emails"].add(commit["email"])
        if commit["handle"]:
            person["handles"].add(commit["handle"])
        person["first"] = min(person["first"], commit["date"])
        person["last"] = max(person["last"], commit["date"])
        if commit["story"]:
            person["stories"][commit["story"]] = max(
                person["stories"].get(commit["story"], ""), commit["date"])
        for key, counts in person["windows"].items():
            if key == "all" or commit["date"] >= cutoffs[key]:
                counts["commits"] += 1
                counts["forge"] += commit["forge"]

    roles_by_name = _record_names(base)
    out = []
    for person in people.values():
        # Without a no-reply email, a git name shaped like a handle is the best
        # local guess at one.
        guesses = sorted(person["handles"], key=str.lower) or sorted(
            n for n in person["names"] if HANDLE_LIKE.match(n))
        handle = guesses[0] if guesses else None
        name = _display_name(person["names"], handle)
        # A record names someone however they typed it ("Nandu", "Prashant
        # Anand"): match any of their names, or the first word of their name.
        keys = {_norm(n) for n in person["names"]} | {_norm(h) for h in person["handles"]}
        first = _norm(name.split()[0])
        roles: set[str] = set()
        for recorded, credited in roles_by_name.items():
            if _norm(recorded) in keys or _norm(recorded.split()[0]) == first:
                roles |= credited
        out.append({
            "name": name,
            "handle": handle,
            "emails": sorted(person["emails"]),
            "aliases": sorted(n for n in person["names"] if n != name),
            "first_commit": person["first"],
            "last_commit": person["last"],
            "roles": sorted(roles),
            "stories": [story for story, _ in sorted(
                person["stories"].items(), key=lambda kv: kv[1], reverse=True)][:8],
            "windows": person["windows"],
        })
    out.sort(key=lambda p: (-p["windows"]["all"]["commits"], p["name"].lower()))
    return {"generated_on": today.isoformat(), "people": out}


def _stamp(base: Path) -> tuple:
    git = base / ".git"
    return (
        fscache.file_stamp(git / "HEAD"),
        fscache.file_stamp(git / "packed-refs"),
        fscache.tree_stamp(git / "refs"),
        fscache.file_stamp(base / ".mailmap"),
        tuple(fscache.tree_stamp(base / root) for root in RECORD_ROOTS),
        date.today().isoformat(),  # the 30/90-day windows roll at midnight
    )


def contributors(base: Path) -> dict:
    return fscache.cached(f"contributors:{base}", _stamp(base), lambda: build(base))


def contributors_json(base: Path) -> bytes:
    return json.dumps(contributors(base)).encode()
