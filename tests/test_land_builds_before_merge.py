"""Land builds an amended, unbuilt fix but keeps record-only work valid."""

import json
import re
import sys

import pytest

from conftest import GH_STUB, _install
from test_close import env  # noqa: F401
from test_land import GH, ITEM, URL, _agent, _fix, _land, _workers, land  # noqa: F401
from test_stacked_fixes_count_only_their_own_changes import configured
from test_tools_session_hold import Session

STORY = "land-builds-before-merge"


@pytest.mark.parametrize("previous,worked", [(False, False), (True, False), (False, True)],
                         ids=["new", "previously-adopted", "record-only-work"])
def test_1_land_builds_unbuilt_fixes_and_accepts_record_only_work(land, previous, worked):
    configured(land, previous)
    _install(land.repo.bin, "gh", GH.format(
        python=sys.executable, remote=land.repo.git("remote", "get-url", "origin"), url=URL)
        + GH_STUB.format(python=sys.executable).split("\n", 1)[1])
    _agent(land)
    where = _fix(land)
    if worked:
        land.commit(where, "plans/result.md", "The requested record\n", "Write the requested record")
    amended = land.repo.forge("fix", "amend", ITEM, "--done", "The requested record exists",
                             "--because", "Clarify the result", cwd=where)
    assert amended.returncode == 0, amended.stdout + amended.stderr
    expected = f"Next: forge {'close' if worked else 'work'} {ITEM}"
    next_step = land.repo.forge("next", cwd=where)
    assert next_step.returncode == 0, next_step.stdout + next_step.stderr
    done = _land(land)
    assert done.returncode == 0, done.stdout + done.stderr
    assert len(_workers(land)) == (0 if worked else 1)
    assert len(land.gh_calls("pr", "merge")) == 1
    if worked:
        assert land.repo.git("show", "origin/main:plans/result.md") == "The requested record"
    else:
        assert done.stdout.index(f"Building {ITEM}.") < done.stdout.index(f"Closing {ITEM}.")
        assert land.repo.git("show", "origin/main:work-1.txt") == "worked"
    assert expected in amended.stdout
    assert expected in next_step.stdout


@pytest.mark.platform
@pytest.mark.parametrize("tool", ["codex", "claude"])
def test_2_land_uses_completed_native_round_without_a_commit(land, monkeypatch, tmp_path, tool):
    _agent(land)
    config = land.repo.path / "forge.toml"
    # Preserve the native handback contract with an explicit Fast opt-in.
    land.commit(land.repo.path, "forge.toml", ('codex_fast = "needed"\n' if tool == "codex" else "")
        + config.read_text("utf-8").replace(
            'workers = "claude"', f'workers = "{tool}"\ntools = "{tool}"'))
    land.repo.git("push", "-q", "origin", "main")
    where = _fix(land)
    home = tmp_path / "native-home"
    home.mkdir()
    (home / "config.toml").write_text(
        f'[projects.{json.dumps(str(where))}]\ntrust_level = "trusted"\n', "utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    data = tmp_path / "without-sdk"
    data.mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    if tool == "claude":
        monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
        monkeypatch.setenv("CLAUDECODE", "1")
    host = Session(land.repo, tmp_path / "native-host", tool + "-session")
    try:
        started = host.forge("land", ITEM)
        assert started.returncode == 0, started.stdout + started.stderr
        assert "background fixer subagent" in started.stdout
        number = re.search(r"--round (\d+)", started.stdout)[1]
        head = land.repo.git("rev-parse", "HEAD", cwd=where)
        finished = host.forge("handback", ITEM, "--round", number, "--subagent", "worker-one",
                              input="The round is complete.")
        assert finished.returncode == 0, finished.stdout + finished.stderr
        assert land.repo.git("rev-parse", "HEAD", cwd=where) == head
        resumed = host.forge("land", ITEM)
        assert f"Closing {ITEM}." in resumed.stdout, resumed.stdout + resumed.stderr
        assert f"Building {ITEM}." not in resumed.stdout
        # Completion without a product diff no longer permits an empty merge.
        assert resumed.returncode != 0, resumed.stdout + resumed.stderr
        assert "The build round did not finish." in resumed.stderr
        assert f"forge work {ITEM}" in resumed.stderr
        assert not land.gh_calls("pr", "merge")
    finally:
        host.close()
