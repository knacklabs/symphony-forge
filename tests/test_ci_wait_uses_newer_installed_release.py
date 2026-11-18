"""Pinned commands recover CI with the installed release and keep pinned review.

Audit: historical checks refuse failed groups. Existing recovery tests run a
single release. This test fakes package acquisition and GitHub only, exercises
the real command, and needs no test-only production seam.
"""
import json
import re
import shutil
import sys
import tomllib

import pytest

from conftest import IDLE_MACHINE, ROOT, _install
from test_close import GREEN, env  # noqa: F401
from test_close_reruns_cancelled_ci import OTHER, RUN_LIST, _check, _workflow
from test_land import ITEM, RUNS, _agent, _fix, _queue, _runs, land  # noqa: F401
from test_land_waits_for_check_progress import clock  # noqa: F401

STORY = "ci-wait-newest-release"


@pytest.mark.parametrize("command", ["close", "merge", "land"])
@pytest.mark.parametrize("second", ["success", "failure"])
@pytest.mark.parametrize("first", ["failure", "cancelled"])
def test_1_pinned_commands_use_newer_ci_recovery_and_keep_pinned_review(clock, command, second, first):
    repo = clock.repo
    _agent(clock)
    config = (repo.path / "forge.toml").read_text("utf-8")
    clock.commit(repo.path, "forge.toml", re.sub(r'version = "[^"]+"', 'version = "v1.2.42"', config))
    repo.git("push", "-q", "origin", "main")
    where = _fix(clock, "working", worked=True)
    source = clock.tmp / "earlier-source"
    shutil.copytree(ROOT / "src/forge", source / "forge",
                    ignore=shutil.ignore_patterns("__pycache__"))
    packaging = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    for original, packaged in packaging["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"].items():
        target = source / packaged
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / original, target)
    version = source / "forge/__init__.py"
    version.write_text(re.sub(r'__version__ = "[^"]+"', '__version__ = "1.2.42"',
                             version.read_text("utf-8")), encoding="utf-8")
    shutil.copyfile(ROOT / "tests/fixtures/checks-before-failed-groups.txt", source / "forge/checks.py")
    review = source / "forge/review.py"
    review.write_text(review.read_text("utf-8") + '''
original_run = run
def run(*args, **kwargs):
    print("Pinned review implementation ran", flush=True)
    return original_run(*args, **kwargs)
    ''',
                      encoding="utf-8")
    # Acquisition alone is fake. Both command paths execute the selected package.
    startup = "import os\nif hasattr(os, 'getloadavg'): os.getloadavg = lambda: (0.0, 0.0, 0.0)\n" + IDLE_MACHINE
    _install(repo.bin, "uv", f'''#!{sys.executable}
import os, subprocess, sys
args = sys.argv[1:]
os.environ["PYTHONPATH"] = {json.dumps(source.as_posix())} + os.pathsep + os.environ.get("PYTHONPATH", "")
if args[:3] == ["tool", "run", "--from"]:
    args = ["-c", "from forge.cli import main; raise SystemExit(main())", *args[5:]]
else:
    args = args[args.index("python") + 1:]
    if args[0] == "-I":
        args = args[1:]
args[1] = {startup!r} + args[1]
sys.exit(subprocess.call([sys.executable, *args]))
''')
    if command == "merge":
        clock.checks(GREEN)
        closed = repo.forge("close", ITEM, cwd=where)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert "Pinned review implementation ran" in closed.stdout
    repo.git("push", "-q", "-u", "origin", "fix/tidy-readme", cwd=where)
    failed = [_check("test group 1 of 2", first), _check("tests", "failure"), OTHER]
    running = [_check("test group 1 of 2", None, status="in_progress"),
               _check("tests", "failure"), OTHER]
    final = GREEN if second == "success" else [
        _check("test group 1 of 2", "failure"), _check("tests", "failure"), OTHER]
    _queue(clock, RUNS, *_runs(failed, running, final))
    _queue(clock, RUN_LIST, _workflow(5, 77, first),
           _workflow(5, 77, None, "in_progress", attempt=2), _workflow(5, 77, second, attempt=2))
    clock.gh.respond("run", "rerun")
    clock.gh.respond("run", "view", stdout='{"attempt": 2}')

    done = repo.forge(command, ITEM, cwd=where)

    assert clock.gh_calls("run", "rerun") == [["run", "rerun", "77", "--failed"]], done.stdout + done.stderr
    if second == "failure":
        assert done.returncode != 0, done.stdout + done.stderr
        assert "Checks failed on the pull request" in done.stdout + done.stderr
        assert f"forge work {ITEM}" in done.stdout + done.stderr
        return
    assert done.returncode == 0, done.stdout + done.stderr
    if command != "merge":
        assert "Pinned review implementation ran" in done.stdout
    if command == "close":
        assert 'version = "v1.2.42"' in (where / "forge.toml").read_text("utf-8")
