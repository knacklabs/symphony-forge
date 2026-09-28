"""Branch protection follows the workflows left by migration and origin's repository."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import test_migrate


STORY = "FIX-FORGE-S-BRANCH-PROTECTION-KEEPS-REQUIRED"


def test_1_drops_required_checks_whose_workflows_migration_deletes(
        repo, gh, tmp_path, monkeypatch):
    fixture = tmp_path / "fixture"
    shutil.copytree(test_migrate.FIXTURE, fixture)
    old = fixture / "source/.github/workflows/pr-ticket-check.yml"
    old.write_text("name: old checks\non: pull_request\njobs:\n  old-check:\n"
                   "    runs-on: ubuntu-latest\n    steps: []\n  lint:\n"
                   "    runs-on: ubuntu-latest\n    steps: []\n  keep-check:\n"
                   "    runs-on: ubuntu-latest\n    steps: []\n", encoding="utf-8")
    (fixture / "client/.github/workflows/ci.yml").write_text(
        "name: ci\non: pull_request\njobs:\n  lint:\n"
        "    name: frontend-lint # client check\n    runs-on: ubuntu-latest\n    steps: []\n"
        "  keep-check:\n"
        "    runs-on: ubuntu-latest\n    steps: []\n", encoding="utf-8")
    monkeypatch.setattr(test_migrate, "FIXTURE", fixture)
    test_migrate._copied_client(repo, tmp_path, monkeypatch)
    moved = repo.forge("migrate")
    assert moved.returncode == 0, moved.stderr
    repo.git("merge", "-q", "--no-ff", "-m", "Move to Forge v1", "forge/migrate-v1")
    repo.git("update-ref", "refs/remotes/origin/main", "HEAD")
    gh.respond("pr", "list", stdout=json.dumps([{"number": 7, "state": "MERGED", "body": ""}]))
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", stdout=json.dumps({
        "required_status_checks": {"checks": [{"context": "old-check"},
                                               {"context": "lint"},
                                               {"context": "frontend-lint"},
                                               {"context": "keep-check"},
                                               {"context": "tests"}]}}))
    gh.respond("api", "--method", "PUT", stdout="{}")

    closed = repo.forge("close", "migrate-v1")
    assert closed.returncode == 0, closed.stderr
    [put] = [call for call in gh.calls() if call[:3] == ["api", "--method", "PUT"]]
    rule = json.loads(Path(put[put.index("--input") + 1]).read_text(encoding="utf-8"))
    assert rule["required_status_checks"]["checks"] == [
        {"context": "frontend-lint"}, {"context": "keep-check"}, {"context": "tests"},
        {"context": "forge-pr-check"}]


@pytest.mark.parametrize("origin_url", [
    "https://github.com/acme/shop.git",
    "ssh://git@ssh.github.com:443/acme/shop.git",
    "ssh://git@other.example/acme/shop.git",
])
def test_2_names_origin_repository_in_each_branch_protection_api_call(
        repo, gh, tmp_path, origin_url):
    client = tmp_path / "new-client"
    client.mkdir()
    repo.git("init", "-q", "-b", "main", cwd=client)
    remote = tmp_path / "new-remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    repo.git("remote", "add", "origin", origin_url, cwd=client)
    repo.git("remote", "set-url", "--push", "origin", str(remote), cwd=client)
    repo.git("remote", "add", "other", "https://github.com/elsewhere/wrong.git", cwd=client)
    gh.respond("api", "repos/acme/shop/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected"}')
    gh.respond("api", "--method", "PUT", "repos/acme/shop/branches/main/protection",
               stdout="{}")

    initialized = repo.forge("init", cwd=client)
    if "other.example" in origin_url:
        assert initialized.returncode == 1
        assert initialized.stderr == ("Forge cannot identify a GitHub repository from origin.\n"
                                      "Next: git remote set-url origin <GitHub repository URL>\n")
        assert not gh.calls()
        return
    assert initialized.returncode == 0, initialized.stderr
    assert [call[:4] for call in gh.calls() if call[0] == "api"] == [
        ["api", "repos/acme/shop/branches/main/protection"],
        ["api", "--method", "PUT", "repos/acme/shop/branches/main/protection"]]
