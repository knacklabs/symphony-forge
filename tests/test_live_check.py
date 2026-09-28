"""Live app CI contracts exercised through the forge command."""

from __future__ import annotations

import json

STORY = "FORGE-LIVE-1"
NOTE = ("Forge didn't start this branch, so it checks nothing here; "
        "the repo's own CI and review apply.")


def _configured(repo, checks: list[str]) -> None:
    repo.write("forge.toml", f'version = "{repo.forge("--version").stdout.split()[-1]}"\n'
               'repo = "client"\nworkers = "claude"\ntest = "make check"\n'
               f"checks = {json.dumps(checks)}\ninterfaces = []\n")
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Configure Forge")


def test_3_other_branches_pass_with_note_and_forge_branches_still_check(repo, tmp_path):
    _configured(repo, ["forge-pr-check"])
    base = repo.git("rev-parse", "HEAD")
    for branch in ("dependabot/npm/updates", "fix/untracked"):
        where = tmp_path / branch.replace("/", "-")
        repo.git("worktree", "add", "-q", "-b", branch, str(where))
        (where / "README.md").write_text(f"# {branch}\n", encoding="utf-8")
        repo.git("add", "README.md", cwd=where)
        repo.git("commit", "-q", "-m", "Update readme", cwd=where)
        checked = repo.forge("hook", "pr-check", "--base", base, "--head",
                             repo.git("rev-parse", "HEAD", cwd=where), "--branch", branch)
        if branch.startswith("fix/"):
            assert checked.returncode == 1
            assert "Forge did not start fix/untracked" in checked.stderr
        else:
            assert checked.returncode == 0, checked.stderr
            assert checked.stdout.strip() == NOTE


def test_5_only_named_tests_job_ships_and_doctor_compares_protection(repo, gh, tmp_path,
                                                                     monkeypatch):
    _configured(repo, ["lint", "forge-pr-check"])
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    repo.git("checkout", "-q", "-b", "fix/ci-configuration")
    assert repo.forge("sync").returncode == 0
    workflow = (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    assert "\n  tests:\n" not in workflow
    assert "\n  forge-pr-check:\n" in workflow

    endpoint = "repos/{owner}/{repo}/branches/main/protection"
    gh.respond("api", endpoint, stdout=json.dumps({"required_status_checks": {
        "checks": [{"context": "lint"}, {"context": "forge-pr-check"},
                   {"context": "security"}]}}))
    mismatch = repo.forge("doctor")
    assert "security" in mismatch.stdout
    assert "branch protection" in mismatch.stdout.lower()
    assert "forge.toml" in mismatch.stdout
    assert "impeccable is required" not in mismatch.stdout
    assert "emil-design-eng is required" not in mismatch.stdout

    gh.respond("api", endpoint, stdout=json.dumps({"required_status_checks": {
        "checks": [{"context": "lint"}, {"context": "forge-pr-check"}]}}))
    matching = repo.forge("doctor")
    assert "branch protection" not in matching.stdout.lower()

    repo.write("package.json", '{"dependencies":{"react":"*"}}\n')
    frontend = repo.forge("doctor")
    assert "impeccable is required for UI work" in frontend.stdout

    repo.write("forge.toml", (repo.path / "forge.toml").read_text(encoding="utf-8").replace(
        '["lint", "forge-pr-check"]', '["tests", "forge-pr-check"]'))
    assert repo.forge("sync").returncode == 0
    workflow = (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    assert "\n  tests:\n" in workflow
    assert '- run: "make check"' in workflow
