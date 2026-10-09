"""Command proof: conflicts end CI waiting; land retries close's real default merge.

Audit: a missing mergeability check waits to timeout, and a dropped land retry never
merges the advanced default. Existing tests cover conflicts present before close,
not a default update during CI. Only GitHub and elapsed time are faked.
"""
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from conftest import GH_STUB, ROOT, _install
from test_close import GREEN, env  # noqa: F401
from test_land import BRANCH, GH, ITEM, RUNS, URL, _fix, _queue, _runs
from test_setup import _fresh_client

STORY = "conflicting-pr-check-waits"


@pytest.fixture(params=["new", "adopted"])
def client(env, request, monkeypatch):
    repo = env.repo
    config = (repo.path / "forge.toml").read_text(encoding="utf-8")
    if request.param == "new":
        path, made = _fresh_client(repo, env.gh, env.tmp)
        assert made.returncode == 0, made.stderr
        repo.path = path
        repo.git("switch", "-qc", "fix/upgrade-client")
    else:
        repo.git("switch", "-qc", "fix/upgrade-client")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier release")
    repo.write(".factory/fixes/upgrade-client.json", json.dumps({
        "kind": "fix", "branch": "fix/upgrade-client", "status": "working",
        "why": "Refresh client guidance", "done_when": "Guidance uses this release"}))
    env.commit(repo.path, "forge.toml", config)
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Refresh client guidance", "--allow-empty")
    remote = Path(repo.git("remote", "get-url", "origin")).as_posix()
    _publish_default(repo, remote)
    repo.git("switch", "main")
    repo.git("merge", "--ff-only", "fix/upgrade-client")
    _install(repo.bin, "gh", GH.format(python=sys.executable, remote=remote, url=URL)
             + GH_STUB.format(python=sys.executable).split("\n", 1)[1])
    env.checks(GREEN)
    # No real sleeps: the log proves conflict detection never entered the wait.
    folder = env.tmp / "clock"
    folder.mkdir()
    (folder / "sitecustomize.py").write_text(
        "import time\nfrom pathlib import Path\n"
        f"log = Path({json.dumps((folder / 'sleeps').as_posix())})\n"
        "real = time.monotonic\nelapsed = 0\n"
        "def sleep(seconds):\n"
        "    global elapsed\n    elapsed += seconds\n"
        "    with log.open('a') as file: file.write(str(seconds) + '\\n')\n"
        "time.sleep = sleep\ntime.monotonic = lambda: real() + elapsed\n",
        encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(folder) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "60")
    return env, folder / "sleeps", remote


def _publish_default(repo, remote):
    repo.git("push", "-q", "origin", "HEAD:refs/heads/prepared")
    repo.git("update-ref", "refs/heads/main", repo.git("rev-parse", "HEAD"), cwd=remote)
    repo.git("fetch", "-q", "origin", "main")


def _advance_during_ci(env, remote, conflict, *, during_merge=False):
    repo = env.repo
    repo.git("switch", "fix/upgrade-client")
    env.commit(repo.path, "app.py", "print('base')\n")
    guide = (repo.path / "AGENTS.md").read_text(encoding="utf-8")
    env.commit(repo.path, "AGENTS.md", guide.replace("Working here with Forge", "Old guide", 1))
    _publish_default(repo, remote)
    repo.git("switch", "main")
    repo.git("merge", "--ff-only", "fix/upgrade-client")
    where = _fix(env, "working", worked=True)
    env.commit(where, "AGENTS.md", guide)
    before = repo.git("rev-parse", "HEAD", cwd=where)
    repo.git("switch", "-qc", "fix/default-update")
    repo.write(".factory/fixes/default-update.json", json.dumps({
        "kind": "fix", "branch": "fix/default-update", "status": "working",
        "why": "Update the default", "done_when": "Default is updated"}))
    env.commit(repo.path, "app.py" if conflict else "default.txt",
               "print('default')\n" if conflict else "Default update\n")
    env.commit(repo.path, "AGENTS.md", guide.replace("Working here with Forge", "Default guide", 1))
    moved = repo.git("rev-parse", "HEAD")
    repo.git("push", "-q", "origin", "HEAD:refs/heads/default-update")
    # GitHub's first CI read races a default-branch update after close fetched it.
    # Subsequent responses follow the real remote heads, so only a real close
    # merge and push can restore checks.
    stub = repo.bin / "gh"
    script = '''
if args[:4] == ["api", "--paginate", "--jq", ".check_runs[]"]:
    if {during_merge} and not (here / "first-green").exists():
        (here / "first-green").touch()
        answer({green})
    subprocess.run(["git", "update-ref", "refs/heads/main", {moved}], cwd=remote, check=True)
    refs = heads()
    head = refs.get("refs/heads/" + {branch}, "")
    clean = subprocess.run(["git", "merge-tree", "--write-tree", refs["refs/heads/main"], head],
                           cwd=remote, capture_output=True).returncode == 0
    answer({green} if clean else "")
if args[:2] == ["pr", "view"] and "--json" in args and "mergeable" in args[args.index("--json") + 1]:
    refs = heads()
    head = refs.get("refs/heads/" + args[2], "")
    clean = subprocess.run(["git", "merge-tree", "--write-tree", refs["refs/heads/main"], head],
                           cwd=remote, capture_output=True).returncode == 0
    answer(json.dumps({{"mergeable": "MERGEABLE" if clean else "CONFLICTING", "headRefOid": head}}))
'''.format(moved=repr(moved), branch=repr(BRANCH), green=repr(_runs(GREEN)[0]),
           during_merge=repr(during_merge))
    stub.write_text(stub.read_text(encoding="utf-8").replace(
        'merged = here / "github-merged"', script + '\nmerged = here / "github-merged"'),
        encoding="utf-8")
    return where, before, moved


def test_1_close_explains_conflicts_without_waiting_for_missing_checks(client):
    env, sleeps, remote = client
    _advance_during_ci(env, remote, conflict=True)
    done = env.repo.forge("close", ITEM)
    assert done.returncode == 1, done.stdout + done.stderr
    assert "GitHub runs no checks on a conflicting pull request" in done.stderr
    assert f"Next: forge close {ITEM}" in done.stderr
    assert "has not reported" not in done.stderr
    assert not sleeps.exists()
    assert len(env.gh_calls(*RUNS)) == 1


@pytest.mark.parametrize("conflict", [False, True], ids=["merges-default", "needs-person"])
def test_2_land_retries_close_to_merge_default_or_report_its_conflict(client, conflict):
    env, sleeps, remote = client
    where, before, moved = _advance_during_ci(env, remote, conflict)
    done = env.repo.forge("land", ITEM)
    assert done.stdout.count(f"Closing {ITEM}.") == 2, done.stdout + done.stderr
    assert not sleeps.exists()
    if conflict:
        assert done.returncode == 1
        assert "Merging main into fix/tidy-readme conflicts in AGENTS.md, app.py." in done.stderr
        assert "Next: git -C " in done.stderr and " merge origin/main" in done.stderr
        assert "has not reported" not in done.stderr
        assert not env.gh_calls("pr", "merge")
        assert env.repo.git("status", "--porcelain", cwd=where) == ""
    else:
        assert done.returncode == 0, done.stdout + done.stderr
        assert "clean review and green checks" in done.stdout
        env.repo.git("merge-base", "--is-ancestor", moved, "HEAD", cwd=where)
        env.repo.git("merge-base", "--is-ancestor", before, "HEAD", cwd=where)
        assert (where / "default.txt").read_text(encoding="utf-8") == "Default update\n"


@pytest.mark.parametrize("command", ["close", "land"])
def test_3_clean_pull_request_keeps_normal_waiting(client, command):
    env, sleeps, _ = client
    _fix(env, "working", worked=True)
    stub = env.repo.bin / "gh"
    stub.write_text(stub.read_text(encoding="utf-8").replace(
        'if args[:2] == ["pr", "view"]:',
        'if args[:2] == ["pr", "view"] and "--json" in args and '
        '"mergeable" in args[args.index("--json") + 1]:\n'
        '    answer(json.dumps({"mergeable": "MERGEABLE"}))\n'
        'if args[:2] == ["pr", "view"]:'), encoding="utf-8")
    _queue(env, RUNS, *_runs([], GREEN))
    done = env.repo.forge(command, ITEM)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "clean review and green checks" in done.stdout
    assert len(env.gh_calls(*RUNS)) == 2
    assert sleeps.read_text(encoding="utf-8").splitlines() == ["15"]


def test_4_land_recovers_a_conflict_during_merge_check_revalidation(client):
    env, sleeps, remote = client
    repo = env.repo
    repo.git("switch", "fix/upgrade-client")
    env.commit(repo.path, "forge.toml", (repo.path / "forge.toml").read_text(encoding="utf-8")
               + 'merge = "agent"\n')
    _publish_default(repo, remote)
    repo.git("switch", "main")
    repo.git("merge", "--ff-only", "fix/upgrade-client")
    _advance_during_ci(env, remote, conflict=False, during_merge=True)
    done = repo.forge("land", ITEM)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.count(f"Closing {ITEM}.") == 2
    assert len(env.gh_calls("pr", "merge")) == 1
    assert repo.git("show", "origin/main:default.txt") == "Default update"
    assert not sleeps.exists()


def test_5_land_stops_if_github_still_reports_a_conflict_after_close(client):
    env, sleeps, _ = client
    _fix(env, "working", worked=True)
    env.checks([])
    stub = env.repo.bin / "gh"
    stub.write_text(stub.read_text(encoding="utf-8").replace(
        'if args[:2] == ["pr", "view"]:',
        'if args[:2] == ["pr", "view"] and "--json" in args and '
        '"mergeable" in args[args.index("--json") + 1]:\n'
        '    answer(json.dumps({"mergeable": "CONFLICTING", '
        '"headRefOid": heads()["refs/heads/" + args[2]]}))\n'
        'if args[:2] == ["pr", "view"]:'), encoding="utf-8")
    done = env.repo.forge("land", ITEM)
    assert done.returncode == 1, done.stdout + done.stderr
    assert "GitHub runs no checks on a conflicting pull request" in done.stderr
    assert done.stdout.count(f"Closing {ITEM}.") == 2
    assert not sleeps.exists()
