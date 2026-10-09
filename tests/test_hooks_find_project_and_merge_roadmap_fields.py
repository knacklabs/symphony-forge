"""Clients keep working outside the project and merge roadmap edits without losing fields."""
import json
import os
import shutil
import subprocess

import pytest

from conftest import ROOT
from test_setup import _fresh_client, _version
from test_fix_plans_roadmap_json_conflicts_on_almost_e import _git, _commit_roadmap

STORY = "skipped-sync-board"


@pytest.fixture(params=["new", "previous adoption"])
def client(repo, gh, tmp_path, request):
    if request.param == "new":
        top, done = _fresh_client(repo, gh, tmp_path)
        repo.path = top
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("checkout", "-q", "-b", "fix/upgrade-hooks")
        config = (repo.path / "forge.toml").read_text("utf-8")
        repo.write("forge.toml", config.replace('version = "v1.2.2"',
                                               f'version = "{_version(repo)}"'))
        done = repo.forge("sync")
    assert done.returncode == 0, done.stdout + done.stderr
    return repo


@pytest.mark.skipif(os.name == "nt", reason="Claude shell hooks run through POSIX sh")
def test_claude_hook_finds_project_before_current_folder(client, tmp_path):
    hooks = json.loads((client.path / ".claude/settings.json").read_text("utf-8"))["hooks"]
    command = hooks["PreToolUse"][0]["hooks"][0]["command"]
    outside = tmp_path / "outside project"
    outside.mkdir()
    environment = {**os.environ, "CLAUDE_PROJECT_DIR": client.path.as_posix(),
                   "XDG_BIN_HOME": client.bin.as_posix()}
    for bash, expected in [("pwd", 0), ("git commit --no-verify", 2)]:
        done = subprocess.run(["sh", "-c", command], cwd=outside, env=environment,
                              input=json.dumps({"tool_name": "Bash", "cwd": outside.as_posix(),
                                                "tool_input": {"command": bash}}),
                              capture_output=True, text=True, timeout=60)
        assert done.returncode == expected, done.stdout + done.stderr
        if expected:
            assert "git hooks must run" in done.stderr


@pytest.mark.parametrize("conflicting_field", [None, "title", "spec", "status"])
def test_roadmap_merges_fields_and_conflicts_on_shared_changes(client, conflicting_field):
    base = {"key": "SYNC-1", "title": "Original title", "spec": "docs/specs/original.md",
            "status": "pending", "order": 1}
    client.write("plans/roadmap.json", json.dumps({"items": [base]}, indent=2) + "\n")
    client.git("add", "-A")
    assert _git(client, "commit", "-qm", "Roadmap base").returncode == 0
    client.git("branch", "fix/other-fields")
    client.git("checkout", "-q", "-b", "fix/our-fields")
    mine = {**base, "title": "Our revised title"}
    other = {**base, "spec": "docs/specs/revised.md"}
    if conflicting_field:
        mine = {**base, conflicting_field: "started" if conflicting_field == "status" else "ours"}
        other = {**base, conflicting_field: "done" if conflicting_field == "status" else "theirs"}
    _commit_roadmap(client, [mine], "Our fields")
    client.git("checkout", "-q", "fix/other-fields")
    _commit_roadmap(client, [other], "Other fields")
    client.git("checkout", "-q", "fix/our-fields")
    done = _git(client, "merge", "-q", "--no-edit", "fix/other-fields")
    if conflicting_field:
        assert done.returncode != 0, done.stdout + done.stderr
        assert "plans/roadmap.json" in client.git("diff", "--name-only", "--diff-filter=U")
        assert json.loads((client.path / "plans/roadmap.json").read_text("utf-8"))["items"] == [mine]
    else:
        assert done.returncode == 0, done.stdout + done.stderr
        assert json.loads((client.path / "plans/roadmap.json").read_text("utf-8"))["items"] == [
            {**base, "title": "Our revised title", "spec": "docs/specs/revised.md"}]
