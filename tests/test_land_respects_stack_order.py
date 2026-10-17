"""Stack dependencies take priority over start dates in the real land queue."""

import pytest

from conftest import machine_cores
from test_close import env  # noqa: F401
from test_queue_land_all import _all, _edit, _first, _fix, _number, client  # noqa: F401

STORY = "land-stacked-order"


@pytest.mark.parametrize("base_state", ["reviewing", "working", "stopped"])
def test_1_land_lands_a_stacked_fix_after_its_base(client, monkeypatch, base_state):
    env = client
    machine_cores(env.repo, 4)
    stopped = ({"stop": {"question": "Choose how to repair the base", "tool": "claude"}}
               if base_state == "stopped" else {})
    base = _fix(env, monkeypatch, "base", 2, {"base.py": "BASE = True\n"},
                status="hotspot" if stopped else base_state, **stopped)
    main = env.repo.path
    try:
        env.repo.path = base
        # A clock difference makes the child older, despite being started on the base.
        _fix(env, monkeypatch, "child", 1, {"child.py": "CHILD = True\n",
                                           "shared.py": _edit(1, "child")})
    finally:
        env.repo.path = main
    # Sharing a file makes queue order matter even with two places for concurrent closes.
    _fix(env, monkeypatch, "other", 3, {"other.py": "OTHER = True\n",
                                       "shared.py": _edit(7, "other")})

    done = _all(env)
    lines = done.stdout.splitlines()
    assert "other merged." in lines, done.stdout + done.stderr
    if base_state != "reviewing":
        assert done.returncode == 1, done.stdout + done.stderr
        assert "Starting child." not in lines, done.stdout
        assert not any(call[:3] == ["pr", "merge", _number("fix/child")]
                       for call in env.gh.calls()), done.stdout
        assert any(line.startswith("- child: ") for line in lines), done.stdout
        if base_state == "working":
            assert "- child: its base base is not merged." in lines, done.stdout
            assert "  Next: forge land base" in lines, done.stdout
        return

    assert done.returncode == 0, done.stdout + done.stderr
    assert lines.index("base merged.") < lines.index("Starting child."), done.stdout
    assert lines.index("child merged.") < lines.index("Starting other."), done.stdout
    assert _first(env, "pr", "merge", _number("fix/base")) < _first(
        env, "pr", "merge", _number("fix/child"))
    assert env.repo.git("show", "origin/main:base.py") == "BASE = True"
    assert env.repo.git("show", "origin/main:child.py") == "CHILD = True"
