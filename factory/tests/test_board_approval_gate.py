"""Native plan approval is independent of the read-only board."""
from __future__ import annotations

import sys
from pathlib import Path

from test_gates import HARNESS, repo, run  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))


def test_the_board_port_is_named_once(repo: Path):
    from forge_cli.board import DEFAULT_PORT  # noqa: E402

    forge = (HARNESS / "factory" / "scripts" / "forge.py").read_text(
        encoding="utf-8")
    assert "default=board_mod.DEFAULT_PORT" in forge
    assert "default=8765" not in forge
    assert isinstance(DEFAULT_PORT, int)


def test_native_approval_no_longer_routes_through_board_or_manual_approve(repo: Path):
    code, out = run(repo, "forge.py", "task", "approve", "T1", "--by", "Nobody")
    assert code != 0 and "invalid choice" in out
    code, out = run(repo, "forge.py", "plan", "approve", "--by", "Nobody")
    assert code != 0 and "invalid choice" in out
    phase = (HARNESS / "factory/scripts/forge_cli/phase.py").read_text(encoding="utf-8")
    assert "consume its approval" in phase
    assert "task approve {id}" not in phase
