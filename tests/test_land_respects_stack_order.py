"""Stack dependencies take priority over start dates in the real land queue."""

from conftest import machine_cores
from test_close import env  # noqa: F401
from test_queue_land_all import _all, _first, _fix, _number, client  # noqa: F401

STORY = "land-stacked-order"


def test_1_land_lands_a_stacked_fix_after_its_base(client, monkeypatch):
    env = client
    machine_cores(env.repo, 4)
    base = _fix(env, monkeypatch, "base", 2, {"base.py": "BASE = True\n"})
    main = env.repo.path
    try:
        env.repo.path = base
        # A clock difference makes the child older, despite being started on the base.
        _fix(env, monkeypatch, "child", 1, {"child.py": "CHILD = True\n"})
    finally:
        env.repo.path = main

    done = _all(env)
    assert done.returncode == 0, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    assert lines.index("base merged.") < lines.index("Starting child."), done.stdout
    assert _first(env, "pr", "merge", _number("fix/base")) < _first(
        env, "pr", "merge", _number("fix/child"))
    assert env.repo.git("show", "origin/main:base.py") == "BASE = True"
    assert env.repo.git("show", "origin/main:child.py") == "CHILD = True"
