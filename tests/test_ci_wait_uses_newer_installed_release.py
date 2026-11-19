"""Installed CI recovery survives historical close, queue and repin boundaries.

Audit: a post-upgrade refusal, a records push before recovery, a missing branch
argument, and a fresh interpreter each break a real command in an older release.
The previous proof copied today's close and missed these boundaries. Historical
command owners are text snapshots; support modules use the checkout. Only package
acquisition, GitHub, model review and elapsed time use the existing external fakes.
No production seam is added. The push hook observes when recovery really finished.
"""
import json
import re
import shutil
import sys
import tomllib
from pathlib import Path

import pytest

from conftest import IDLE_MACHINE, ROOT, _install
from test_close import GREEN, env  # noqa: F401
from test_close_pushes_record_after_code_ci import HOOK
from test_close_reruns_cancelled_ci import OTHER, RUN_LIST, _check, _workflow
from test_land import ITEM, RUNS, _agent, _fix, _queue, _runs, land  # noqa: F401
from test_land_waits_for_check_progress import clock  # noqa: F401

STORY = "ci-wait-newest-release"
pytestmark = pytest.mark.platform


def _historical_packages(repo, *versions):
    sources = {}
    for version in versions:
        source = repo.path.parent / ("release-" + version)
        if version == "v1.2.2":
            shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2/src/forge", source / "forge")
        else:
            shutil.copytree(ROOT / "src/forge", source / "forge",
                            ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "tests/fixtures/ci-wait-newest-release" / version / "forge",
                        source / "forge", dirs_exist_ok=True)
        if (source / "forge/cli-py.txt").exists():
            (source / "forge/cli.py").unlink(missing_ok=True)
            (source / "forge/cli-py.txt").rename(source / "forge/cli.py")
        resources = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
        for original, target in resources["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"].items():
            destination = source / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / original, destination)
        # Observe the released review runner, while still executing it and the real close.
        review = source / "forge/review.py"
        review.write_text(review.read_text("utf-8") +
            '\n_original_run = run\ndef run(*args, **kwargs):\n'
            f'    with open({(repo.bin / "pinned-reviews").as_posix()!r}, "a", encoding="utf-8") as log:\n'
            f'        log.write({version!r} + "\\n")\n'
            '    return _original_run(*args, **kwargs)\n', encoding="utf-8")
        sources[version] = source.as_posix()
    startup = "import os\nif hasattr(os, 'getloadavg'): os.getloadavg = lambda: (0., 0., 0.)\n" + IDLE_MACHINE
    runner = f'''#!{sys.executable}
import os, subprocess, sys
args = sys.argv[1:]
requirement = next(arg for arg in args if arg.startswith("git+"))
version = requirement.rsplit("@", 1)[1]
source = {sources!r}[version]
with open({(repo.bin / "release-calls").as_posix()!r}, "a", encoding="utf-8") as log:
    log.write(version + "\\n")
os.environ["PYTHONPATH"] = source + os.pathsep + os.environ.get("PYTHONPATH", "")
if args[:2] == ["tool", "run"]:
    command = ["-c", "from forge.cli import main; raise SystemExit(main())", *args[args.index("forge") + 1:]]
else:
    command = args[args.index("python") + 1:]
    if command[:1] == ["-I"]:
        command = command[1:]
command[1] = {startup!r} + command[1]
sys.exit(subprocess.call([sys.executable, *command]))
'''
    _install(repo.bin, "uv", runner)


def _pin(env, version):
    config = env.repo.path / "forge.toml"
    text = re.sub(r'(?m)^version = "[^"]+"$', f'version = "{version}"', config.read_text("utf-8"))
    env.commit(env.repo.path, "forge.toml", text, "Set the release")
    env.repo.git("push", "-q", "origin", "main")


def _published(env, where):
    repo = env.repo
    repo.git("push", "-q", "-u", "origin", f"fix/{ITEM}", cwd=where)
    parent = repo.git("rev-parse", "HEAD", cwd=where)
    log = repo.bin / "pushes.jsonl"
    remote = Path(repo.git("remote", "get-url", "origin"))
    if not remote.is_absolute():
        remote = repo.path / remote
    hook = remote / "hooks/pre-receive"
    (repo.bin / "gh-calls.jsonl").touch(exist_ok=True)
    hook.write_text(HOOK.format(python=sys.executable, parent=parent, log=log.as_posix(),
                                calls=(repo.bin / "gh-calls.jsonl").as_posix()), encoding="utf-8")
    hook.chmod(0o755)
    return parent, log


def _recovery(env, first="failure", final="success", running_looks=2):
    failed = [_check("test group 1 of 2", first), _check("tests", "failure"), OTHER]
    running = [_check("test group 1 of 2", None, status="in_progress"),
               _check("tests", None, status="in_progress"), OTHER]
    last = GREEN if final == "success" else failed
    _queue(env, RUNS, *_runs(failed, *[running] * running_looks, last))
    _queue(env, RUN_LIST, _workflow(5, 77, first),
           _workflow(5, 77, None, "in_progress", 2), _workflow(5, 77, final, attempt=2))
    env.gh.respond("run", "rerun")
    env.gh.respond("run", "view", stdout='{"attempt":2}')


@pytest.mark.parametrize("upgrade,first,final", [(True, "failure", "success"),
    (True, "cancelled", "success"), (True, "cancelled", "cancelled"),
    (False, "failure", "success")])
def test_1_pinned_close_after_upgrade_recovers_before_the_review_record_push(clock, monkeypatch, upgrade, first, final):
    repo = clock.repo
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "600")
    installed = repo.forge("--version").stdout.split()[-1]
    _agent(clock)
    _pin(clock, "v1.2.42")
    where = _fix(clock, "working", worked=True)
    parent, log = _published(clock, where)
    if upgrade:
        _pin(clock, installed)
    _historical_packages(repo, "v1.2.42")
    _recovery(clock, first, final)

    done = repo.forge("close", ITEM, cwd=where)

    assert (done.returncode == 0) == (final == "success"), done.stdout + done.stderr
    assert clock.gh_calls("run", "rerun") == [["run", "rerun", "77", "--failed"]]
    assert (repo.bin / "pinned-reviews").read_text("utf-8").splitlines() == ["v1.2.42"]
    assert 'version = "v1.2.42"' in (where / "forge.toml").read_text("utf-8")
    pushes = [json.loads(line) for line in log.read_text("utf-8").splitlines()] if log.exists() else []
    records = [push for push in pushes if push[1] == parent]
    if final == "success":
        assert records and records[0][3] >= 4, "Review records cancelled the code's unfinished retry"
        (repo.bin / "gh-queues.json").write_text("[]", encoding="utf-8")
        _recovery(clock, "cancelled")
        merged = repo.forge("merge", ITEM, cwd=where)
        assert merged.returncode == 0, merged.stdout + merged.stderr
        assert len(clock.gh_calls("run", "rerun")) == 2
    else:
        assert not records
        assert "Checks failed on the pull request:" in done.stderr
        assert f"Next: forge work {ITEM}" in done.stderr


def test_2_earlier_wait_without_a_branch_argument_can_close(clock, monkeypatch):
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "600")
    _agent(clock)
    _pin(clock, "v1.2.2")
    where = _fix(clock, "working", worked=True)
    _published(clock, where)
    _historical_packages(clock.repo, "v1.2.2")
    done = clock.repo.forge("close", ITEM, cwd=where)
    assert done.returncode == 0, done.stdout + done.stderr
    assert clock.gh_calls(*RUNS)
    assert (clock.repo.bin / "pinned-reviews").read_text("utf-8").splitlines() == ["v1.2.2"]


def test_3_pinned_land_queue_keeps_recovery_in_its_child(land, monkeypatch):
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "600")
    _agent(land)
    _pin(land, "v1.2.42")
    where = _fix(land, "reviewing", worked=True)
    _published(land, where)
    _historical_packages(land.repo, "v1.2.42")
    # Queue and child use real time; the single-process fake clock is not atomic.
    _recovery(land, "cancelled", running_looks=0)
    done = land.repo.forge("land", "--all")
    assert done.returncode == 0, done.stdout + done.stderr
    assert land.gh_calls("run", "rerun") == [["run", "rerun", "77", "--failed"]]
    assert land.gh_calls("pr", "merge")


def test_4_a_repin_to_an_intermediate_release_keeps_installed_recovery(clock, monkeypatch):
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "600")
    _agent(clock)
    _pin(clock, "v1.2.40")
    where = _fix(clock, "working", worked=True)
    _published(clock, where)
    _pin(clock, "v1.2.42")
    clock.gh.respond("pr", "list", "--head", stdout=json.dumps([{
        "number": 7, "state": "OPEN", "body": "", "isDraft": False,
        "mergeStateStatus": "BEHIND", "baseRefName": "main"}]))
    _historical_packages(clock.repo, "v1.2.40", "v1.2.42")
    _recovery(clock, "cancelled")
    done = clock.repo.forge("close", ITEM, cwd=where)
    assert done.returncode == 0, done.stdout + done.stderr
    assert (clock.repo.bin / "release-calls").read_text("utf-8").splitlines() == ["v1.2.40", "v1.2.42"]
    assert clock.gh_calls("run", "rerun") == [["run", "rerun", "77", "--failed"]]
    assert 'version = "v1.2.42"' in (where / "forge.toml").read_text("utf-8")
