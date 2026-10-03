"""At most two Forge agent runs go at once on one machine, whatever the repo: the rest wait in line,
first come, first served, saying their place, and a run that dies frees its place."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from conftest import _install
from test_worker import calls

STORY = "forge-runs-on-several-repos-at-once-can"
# A claude that records its folder, like the shared stub, then runs until a file go-<its folder's
# name> appears beside it.
HOLDING_CLAUDE = """#!{python}
import json, os, pathlib, sys, time
here = pathlib.Path(__file__).resolve().parent
sys.stdin.read()
with open(here / "claude-calls.jsonl", "a", encoding="utf-8") as calls:
    calls.write(json.dumps({{"args": sys.argv[1:], "cwd": os.getcwd()}}) + "\\n")
while not (here / f"go-{{pathlib.Path.cwd().name}}").exists():
    time.sleep(0.05)
print("stub claude: built it")
"""
FIXES = ["fix-the-login-typo", "fix-the-footer-link", "fix-the-help-page", "fix-the-menu-order"]


def _line(place: int) -> str:
    return (f"2 Forge agents already run on this machine, so this one waits its turn: it is number "
            f"{place} in line.")


def _fixes(repo, count: int) -> tuple[Path, list[str]]:
    """Claude workers and `count` started fixes; each claude runs until the test lets it end."""
    _install(repo.bin, "claude", HOLDING_CLAUDE.format(python=sys.executable))
    log = repo.bin / "claude-calls.jsonl"
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
                             'workers = "claude"\ntest = "pytest -q"\n'
                             'models.lite = { model = "sonnet", effort = "medium" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")
    titles = ["Fix the login typo", "Fix the footer link", "Fix the help page", "Fix the menu order"]
    for title in titles[:count]:
        started = repo.forge("fix", "start", title, "--done", f"{title} is done")
        assert started.returncode == 0, started.stderr
    return log, FIXES[:count]


def _work(repo, tmp_path: Path, fix: str) -> tuple[subprocess.Popen, Path]:
    out = tmp_path / f"{fix}.out"
    with out.open("w", encoding="utf-8") as sink:
        run = subprocess.Popen([sys.executable, str(repo.bin / "forge"), "work", fix],
                               cwd=repo.path, stdin=subprocess.DEVNULL, stdout=sink,
                               stderr=subprocess.STDOUT)
    return run, out


def _until(check, what: str) -> None:
    """Wait for real state: the stub's recorded calls or a run's output."""
    deadline = time.monotonic() + 60
    while not check():
        assert time.monotonic() < deadline, f"timed out waiting for {what}"
        time.sleep(0.05)


def _building(log: Path) -> list[str]:
    """The fixes whose stub claude has started, in the order they started."""
    return [Path(call["cwd"]).name for call in calls(log)]


def _end(repo, fix: str, run: subprocess.Popen) -> None:
    """Let the fix's agent end once it has started, and see its forge work succeed."""
    log = repo.bin / "claude-calls.jsonl"
    _until(lambda: any(name.endswith(fix) for name in _building(log)), f"{fix}'s agent to start")
    (repo.bin / f"go-{next(name for name in _building(log) if name.endswith(fix))}").touch()
    assert run.wait(timeout=60) == 0


def test_1_a_third_run_waits_in_line_until_one_of_two_ends_then_runs(repo, gh, tmp_path):
    log, fixes = _fixes(repo, 3)
    runs = []
    for count, fix in enumerate(fixes[:2], 1):
        runs.append(_work(repo, tmp_path, fix))
        _until(lambda: len(calls(log)) == count, f"{fix}'s agent to start")

    runs.append(_work(repo, tmp_path, fixes[2]))
    third, out = runs[2]
    _until(lambda: _line(1) in out.read_text("utf-8"), "the third run to say its place")

    # Two agents run and the third waits; it says its place once, and starts none.
    assert len(calls(log)) == 2 and third.poll() is None
    assert out.read_text("utf-8").count("in line.") == 1

    _end(repo, fixes[0], runs[0][0])
    _until(lambda: len(calls(log)) == 3, "the third run's agent to start")
    assert _building(log)[2].endswith(fixes[2])
    for fix, (run, _) in zip(fixes[1:], runs[1:]):
        _end(repo, fix, run)
    assert out.read_text("utf-8").count("in line.") == 1


def test_2_a_run_that_dies_frees_its_place_and_the_line_moves_up(repo, gh, tmp_path):
    log, fixes = _fixes(repo, 4)
    runs = []
    for count, fix in enumerate(fixes[:2], 1):
        runs.append(_work(repo, tmp_path, fix))
        _until(lambda: len(calls(log)) == count, f"{fix}'s agent to start")
    for place, fix in enumerate(fixes[2:], 1):
        runs.append(_work(repo, tmp_path, fix))
        out = runs[-1][1]
        _until(lambda: _line(place) in out.read_text("utf-8"), f"{fix} to say it is number {place}")
    assert len(calls(log)) == 2

    # The first run's forge dies outright; its agent is left running, but its place is free.
    runs[0][0].kill()
    runs[0][0].wait()
    _until(lambda: len(calls(log)) == 3, "the third run's agent to start")
    assert _building(log)[2].endswith(fixes[2])
    last = runs[3][1]
    _until(lambda: _line(1) in last.read_text("utf-8"), "the fourth run to move up to number 1")
    assert last.read_text("utf-8").count("in line.") == 2
    assert len(calls(log)) == 3

    (repo.bin / f"go-{_building(log)[0]}").touch()  # lets the dead run's agent end
    for fix, (run, _) in zip(fixes[1:], runs[1:]):
        _end(repo, fix, run)
    assert _building(log)[3].endswith(fixes[3])
