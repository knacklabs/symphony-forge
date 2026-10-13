"""Pace, go-live and weekly trends for the board's team facts.

board_facts calls `facts` once per board with the weekly merged pull request searches.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def facts(top: Path, history: dict[str, Any], items: list[dict[str, Any]],
          github: dict[str, Any] | None) -> tuple[dict[str, Any], str | None]:
    """The team keys `pace`, `go_live`, `trends` and `around_forge`, and the sentence's go-live
    clause. Unknown until they are worked out."""
    return {"pace": None, "go_live": None, "trends": None, "around_forge": None}, None
