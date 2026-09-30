"""A GitHub plan without branch protection skips it with one line; other failures still refuse."""

import json
import subprocess

import test_migrate

STORY = "FIX-FORGE-INIT-AND-A-MIGRATION-S-CLOSE-STOP"
ENDPOINT = "repos/{owner}/{repo}/branches/main/protection"
# What gh prints when the repo's plan has no branch protection (a private repo on a free plan).
UPGRADE = "Upgrade to GitHub Pro or make this repository public to enable this feature."
SKIPPED = ("Branch protection on main was skipped: this repository's GitHub plan doesn't offer it. "
           "Forge's own close and merge still wait for the tests and forge-pr-check checks.\n")


def _plan_answer(gh):
    gh.respond("api", ENDPOINT, exit=1, stderr=f"gh: {UPGRADE} (HTTP 403)\n",
               stdout=json.dumps({"message": UPGRADE, "status": "403"}))


def _init(repo, gh, tmp_path, answer):
    """forge init on a new repo whose protection read gets answer's reply."""
    client, remote = tmp_path / "client", tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    gh.respond("api", stdout="{}")
    answer(gh)
    return client, repo.forge("init", cwd=client)


def test_1_init_skips_protection_the_plan_does_not_offer(repo, gh, tmp_path):
    client, initialized = _init(repo, gh, tmp_path, _plan_answer)
    assert initialized.returncode == 0, initialized.stderr
    assert SKIPPED in initialized.stdout
    assert "refs/heads/main" in repo.git("ls-remote", "origin", cwd=client)
    assert not [call for call in gh.calls() if call[:3] == ["api", "--method", "PUT"]]


def test_2_init_still_refuses_another_protection_error(repo, gh, tmp_path):
    _, initialized = _init(repo, gh, tmp_path, lambda gh: gh.respond(
        "api", ENDPOINT, exit=1, stderr="gh: Resource not accessible (HTTP 403)\n",
        stdout='{"message":"Resource not accessible","status":"403"}'))
    assert initialized.returncode == 1
    assert initialized.stderr.startswith(
        "Branch protection on main was not set: gh: Resource not accessible (HTTP 403).\n")
    assert "skipped" not in initialized.stdout


def test_3_migration_close_skips_protection_the_plan_does_not_offer(
        repo, gh, tmp_path, monkeypatch):
    test_migrate._copied_client(repo, tmp_path, monkeypatch)
    moved = repo.forge("migrate")
    assert moved.returncode == 0, moved.stderr
    repo.git("merge", "-q", "--no-ff", "-m", "Move to Forge v1", "forge/migrate-v1")
    repo.git("update-ref", "refs/remotes/origin/main", "HEAD")
    gh.respond("pr", "list", stdout=json.dumps([{"number": 7, "state": "MERGED", "body": ""}]))
    gh.respond("api", "--method", "PUT", stdout="{}")
    _plan_answer(gh)

    closed = repo.forge("close", "migrate-v1")
    assert closed.returncode == 0, closed.stderr
    assert SKIPPED in closed.stdout
    assert not [call for call in gh.calls() if call[:3] == ["api", "--method", "PUT"]]


def test_4_doctor_says_the_plan_offers_no_protection_instead_of_comparing_checks(
        repo, gh, tmp_path):
    client, initialized = _init(repo, gh, tmp_path, _plan_answer)
    assert initialized.returncode == 0, initialized.stderr
    gh.respond("auth", "status")
    checked = repo.forge("doctor", cwd=client)
    assert f"- Note: {SKIPPED}" in checked.stdout, checked.stdout
    assert "branch protection's required checks" not in checked.stdout
