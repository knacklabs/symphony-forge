"""Forge's data for the /forge pane: who needs the person, and what runs now on this laptop.

Real commands and real git; only the model programs are held or scripted at their edge.
`forge lanes --json` is the one read the pane makes.
"""
import json
import shlex
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, machine_cores
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _other_repo, _until
from test_hotspot_stop import rounds, seed
from test_lanes_agents import finish, hold_agents, make_work, start
from test_story import approved_constitution, worktree
from test_worker import install_claude

pytestmark = pytest.mark.platform

STORY = "FORGE-PANE-1"
QUESTION = "\n\nQuestion: May I reuse the basket parser?"
FIX = {"kind": "fix", "done_when": "It works"}
STOPPED_READ = "---\nround: 2\npassed: no\n---\n\n## Round 2\n\n1. Blocking: The basket has no size limit.\n"


def client(env, previous):
    """A client on the current release: new, or adopted on an earlier release and upgraded."""
    repo = env.repo
    if previous:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        version = repo.forge("--version").stdout.split()[-1]
        config = (repo.path / "forge.toml").read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{version}"').replace('workers = "codex"', 'workers = "claude"')
        env.commit(repo.path, "forge.toml", config, "Use the current release")
        repo.git("push", "-q", "origin", "main")
    approved_constitution(repo)
    repo.git("add", "-A")
    install_claude(repo)
    machine_cores(repo, 8)
    assert repo.forge("next").returncode == 0  # a successful next remembers the repo on this laptop


def lanes(env, where=None):
    done = env.repo.forge("lanes", "--json", cwd=where)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def waiting(env, where=None):
    return [(row["title"], row["repo_name"]) for row in lanes(env, where)["needs_you"]]


@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier adopted"])
def test_3_lanes_say_who_needs_the_person_and_what_runs_now(env, tmp_path, monkeypatch, previous):
    client(env, previous)
    repo = env.repo
    assert lanes(env)["needs_you"] == [] and lanes(env)["busy"] is False

    # A worker's question puts the item on the list; the list reads the same from anywhere.
    item, name = make_work(repo, "Asks about parsers")
    folder = worktree(repo, "fix/" + item)
    monkeypatch.setenv("STUB_CLAUDE_RESULT", QUESTION)
    asked = repo.forge("work", item)
    assert asked.returncode == 0 and "May I reuse the basket parser?" in asked.stdout, asked.stderr
    monkeypatch.delenv("STUB_CLAUDE_RESULT")
    shown = [{"title": "Asks about parsers", "repo_name": repo.path.name,
              "repo_root": repo.path.resolve().as_posix()}]
    assert lanes(env)["needs_you"] == shown
    outside = tmp_path / "outside"
    outside.mkdir()
    for where in (repo.path, folder, outside):
        assert lanes(env, where)["needs_you"] == shown, where

    # A build round that runs hides it; a round that fails brings it back; a test run does not hide it.
    hold_agents(env)
    monkeypatch.setenv("STUB_CLAUDE_EXIT", "1")
    process, _ = start(folder, tmp_path / "run-note", repo, "work", item, "--note", "Yes, reuse it")
    _until(lambda: (repo.bin / f"started-{name}").exists(), "the build round")
    assert lanes(env)["needs_you"] == []
    finish(repo, [process])
    monkeypatch.delenv("STUB_CLAUDE_EXIT")
    assert lanes(env)["needs_you"] == shown

    # A removed worktree takes its question away.
    repo.git("worktree", "remove", "--force", str(folder))
    assert lanes(env)["needs_you"] == []

    # A review-loop stop waits for the owner, even while a test run of the item goes on.
    seed(env, "src/a.py")
    _, loop = env.start("loop", "fix/loop", ".factory/fixes/loop.json", {**FIX, "why": "Loop"}, {"loop.py": "x\n"})
    rounds(env, "loop", loop, ["src/a.py"])
    mine = {"repo_name": repo.path.name, "repo_root": repo.path.resolve().as_posix()}
    loops = [{"title": "Loop", **mine}]
    assert lanes(env)["needs_you"] == loops
    gate = repo.bin / "go-test"
    code = f"import pathlib, time\nwhile not pathlib.Path({gate.as_posix()!r}).exists(): time.sleep(0.05)"
    command = json.dumps(subprocess.list2cmdline([sys.executable, "-c", code]) if sys.platform == "win32"
                         else shlex.join([sys.executable, "-c", code]))
    config = "\n".join(line for line in (loop / "forge.toml").read_text("utf-8").splitlines()
                       if line.partition("=")[0].strip() not in ("test", "fast_test")) + "\n"
    env.commit(loop, "forge.toml", f"test = {command}\nfast_test = {command}\n" + config, "Hold the tests")
    tester, _ = start(loop, tmp_path / "tests-run", repo, "test")
    _until(lambda: lanes(env)["tests"]["entries"], "the test run")
    assert [row["item"] for row in lanes(env)["tests"]["entries"]] == ["loop"]
    assert lanes(env)["needs_you"] == loops
    gate.touch()
    assert tester.wait(timeout=60) == 0

    # A cold read stopped at its round limit lists the plan's title; a wait in a second remembered
    # repo with no run is listed; so is a wait in a forge/migrate-v1 checkout.
    assert repo.forge("story", "new", "BASKET", "Shoppers can save a basket").returncode == 0
    (worktree(repo, "story/BASKET") / "plans/BASKET.read.md").write_text(STOPPED_READ, "utf-8")
    other = _other_repo(tmp_path, repo.bin)
    assert other.forge("next").returncode == 0
    (worktree(other, "story/SHOP") / "plans/SHOP.read.md").write_text(STOPPED_READ, "utf-8")
    migrate = tmp_path / "migrate"
    repo.git("worktree", "add", "-q", "-b", "forge/migrate-v1", str(migrate))
    env.commit(migrate, ".factory/fixes/migrate-v1.json", json.dumps({
        **FIX, "why": "Move to Forge v1", "branch": "forge/migrate-v1", "status": "hotspot",
        "stop": {"question": "Choose how to go on.", "tool": "claude"}}), "Stop the move")
    theirs = {"repo_name": other.path.name, "repo_root": other.path.resolve().as_posix()}
    expected = [*loops, {"title": "Move to Forge v1", **mine}, {"title": "Shoppers can save a basket", **mine},
                {"title": "Shoppers can save a basket", **theirs}]
    assert sorted(map(json.dumps, lanes(env)["needs_you"])) == sorted(map(json.dumps, expected))

    # A fix branch checked out in the main checkout counts, and a worktree that is gone does not.
    repo.git("worktree", "remove", "--force", str(loop))
    repo.git("worktree", "remove", "--force", str(migrate))
    made = make_work(repo, "In place")[0]
    repo.git("worktree", "remove", "--force", str(worktree(repo, "fix/" + made)))
    repo.git("switch", "-q", "fix/" + made)
    monkeypatch.setenv("STUB_CLAUDE_RESULT", QUESTION)
    assert repo.forge("work", made).returncode == 0
    monkeypatch.delenv("STUB_CLAUDE_RESULT")
    titles = [row["title"] for row in lanes(env)["needs_you"] if row["repo_name"] == repo.path.name]
    assert "In place" in titles and "Loop" not in titles and "Move to Forge v1" not in titles
