"""Your own Linux machine for Codex rounds: setup and turn-off, against a stand-in for the machine."""
import os
import subprocess
from pathlib import Path

import pytest

from conftest import ROOT, _install
from ssh_host import machine
from test_codex_worker import PIN, sdk_data  # noqa: F401

pytestmark = pytest.mark.skipif(os.name == "nt", reason="the test machine runs shell scripts")

STORY = "REMOTE-1"


def _repo(repo, monkeypatch, sdk_data, boxes="ssh"):
    _install(repo.bin, "codex-app-server",
             (ROOT / "tests/stubs/codex-app-server").read_text(encoding="utf-8"))
    monkeypatch.setenv("CODEX_BIN", str(repo.bin / "codex-app-server"))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\nboxes = "{boxes}"\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-qm", "Turn on a machine you own")
    repo.git("push", "-q", "origin", "main")
    return version


def _setup(repo, *args):
    return repo.forge("lanes", "--box", "setup", *args)


def _clone(host) -> Path:
    return next(host.home.glob("forge-host/*/clone"))


def test_1_setup_checks_the_machine_and_says_what_is_missing(repo, monkeypatch, sdk_data):
    version = _repo(repo, monkeypatch, sdk_data)
    host = machine(repo)
    done = _setup(repo)
    assert done.returncode == 1 and "Name your machine: forge lanes --box setup --host" in done.stderr
    done = _setup(repo, "--host=-oProxyCommand=x")
    assert "is not a name ssh takes" in done.stderr
    assert host.calls() == []
    done = _setup(repo, "--host", "nowhere")
    assert "Forge cannot reach nowhere with ssh: ssh: Could not resolve hostname nowhere" in done.stderr
    host.forge(version="v0.0.1")
    done = _setup(repo, "--host", "devbox")
    assert f"devbox has Forge v0.0.1, and this repo pins Forge {version}." in done.stderr
    assert "uv tool install" in done.stderr or "Next: on devbox:" in done.stderr
    host.forge()
    done = _setup(repo, "--host", "devbox")
    assert "Codex is not signed in on devbox." in done.stderr and "codex login --device-auth" in done.stderr
    host.sign_in()
    done = _setup(repo, "--host", "devbox")
    assert f"Installing the Codex kit {PIN} on devbox with uv (about 300 MB)." in done.stdout
    steps = (host.home / "uv.log").read_text("utf-8").splitlines()
    assert steps[0].startswith("venv --python 3.11") and f"openai-codex=={PIN}" in steps[1]
    print("STDERR", done.stderr, done.stdout)
    clone = _clone(host)
    assert f"Codex on devbox does not trust {clone}" in done.stderr
    assert str(host.home / ".codex/config.toml") in done.stderr
    host.trust(str(clone))
    done = _setup(repo, "--host", "devbox")
    assert done.returncode == 0, done.stderr
    assert "devbox is set up for this repo (4 processors). Codex build rounds start there while it has room" in done.stdout
    folders = sorted(p.name for p in host.home.glob("forge-host/*/*"))
    again = _setup(repo)  # the saved name
    assert again.returncode == 0 and "is set up for this repo" in again.stdout
    assert (host.home / "uv.log").read_text("utf-8").splitlines() == steps
    assert sorted(p.name for p in host.home.glob("forge-host/*/*")) == folders
    assert host.git("-C", str(clone), "symbolic-ref", "refs/remotes/origin/HEAD") == "refs/remotes/origin/main"
    name = subprocess.run(["git", "config", "user.name"], cwd=repo.path, capture_output=True, text=True).stdout.strip()
    assert host.git("-C", str(clone), "config", "user.name") == name
    # the commit check runs on the machine: a branch Forge did not start is refused
    host.git("-C", str(clone), "fetch", "-q", str(repo.path), "main")
    work = host.home / "wt"
    host.git("-C", str(clone), "worktree", "add", "-q", "-b", "other", str(work), "FETCH_HEAD")
    done = host.run(f"cd {work} && echo x > x.txt && git add x.txt && git commit -qm x")
    assert done.returncode != 0 and "was not started by Forge" in done.stderr
    other = _setup(repo, "--host", "elsewhere")
    assert "This clone is set up on devbox; turn that off first." in other.stderr
    misuse = repo.forge("lanes", "--host", "devbox")
    assert "Use --host only with --box setup." in misuse.stderr
    assert not any("auth.json" in call for call in host.calls())


def test_5_rounds_on_a_machine_are_off_until_turned_on_and_off_deletes_forges_folder(repo, monkeypatch, sdk_data):
    version = _repo(repo, monkeypatch, sdk_data, boxes="off")
    host = machine(repo)
    host.sign_in()
    done = _setup(repo, "--host", "devbox")
    assert 'boxes = "off"' in done.stderr and host.calls() == []
    for guide in (".claude", ".codex"):
        text = (ROOT / guide / "skills/forge/SKILL.md").read_text("utf-8")
        assert "### Build rounds on a machine you own" in text
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\nboxes = "ssh"\n')
    first = _setup(repo, "--host", "devbox")
    host.trust(str(_clone(host)))
    assert _setup(repo, "--host", "devbox").returncode == 0, first.stderr
    clone = _clone(host)
    folder = clone.parent
    # a round that still runs, recorded in a .pid file
    runs = folder / "runs/TASK-ONE"
    runs.mkdir(parents=True)
    sleeper = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        start = " ".join(subprocess.run(["ps", "-o", "lstart=", "-p", str(sleeper.pid)],
                                        capture_output=True, text=True).stdout.split())
        (runs / "a1.pid").write_text(f"{sleeper.pid} {start}\n", encoding="utf-8")
        for args in (["--box", "off"], ["--box", "off", "--yes"]):
            done = repo.forge("lanes", *args)
            assert done.returncode == 1
            assert f"A round of TASK-ONE still runs on devbox (process {sleeper.pid}); turn off after it ends." in done.stderr
            assert folder.exists()
        (runs / "a1.pid").write_text(f"{sleeper.pid} Mon Jan  1 00:00:00 2001\n", encoding="utf-8")
        assert "still runs" not in repo.forge("lanes", "--box", "off").stderr
    finally:
        sleeper.kill()
        sleeper.wait()
    (runs / "a1.pid").unlink()
    # things only on the machine
    host.git("-C", str(clone), "fetch", "-q", str(repo.path), "main")
    run = runs / "a1"
    host.git("-C", str(clone), "worktree", "add", "-q", "-f", "-b", "task/TASK-ONE", str(run), "FETCH_HEAD")
    host.run(f"cd {run} && printf 'notes.txt\\nnode_modules/\\n' >> $(git rev-parse --git-common-dir)/info/exclude"
             " && echo n > notes.txt && mkdir node_modules && echo m > node_modules/m && echo u > loose.py"
             " && echo s > kept.py && git add kept.py && git stash -q"
             " && echo c > c.py && git add c.py && git -c user.name=x -c user.email=x@x commit -q --no-verify -m c")
    (run / "loose.py").write_text("u\n", encoding="utf-8")
    listed = repo.forge("lanes", "--box", "off")
    assert listed.returncode == 0 and folder.exists(), listed.stderr
    assert f"Turning off deletes Forge's folder {folder} on devbox, with everything in it:" in listed.stdout
    assert "loose.py" in listed.stdout and "notes.txt" in listed.stdout and "node_modules" not in listed.stdout
    assert "stash" in listed.stdout
    assert "task/TASK-ONE: 1 commits that have not come back" in listed.stdout
    assert "Next: forge lanes --box off --yes, once the developer agrees" in listed.stdout
    done = repo.forge("lanes", "--box", "off", "--yes")
    assert done.returncode == 0, done.stderr
    assert f"Deleted Forge's folder {folder} on devbox." in done.stdout
    assert not (host.home / "forge-host" / folder.name).exists()
    again = repo.forge("lanes", "--box", "off")
    assert "nothing to delete" in again.stdout
    # an unreachable machine keeps the record
    assert _setup(repo, "--host", "devbox").returncode == 0  # Codex's trust entry stayed
    folder = _clone(host).parent
    host.down()
    done = repo.forge("lanes", "--box", "off", "--yes")
    assert done.returncode == 1 and f"Could not delete {folder} on devbox:" in done.stderr
    host.down(False)
    assert repo.forge("lanes", "--box", "off", "--yes").returncode == 0
    assert not folder.exists()
