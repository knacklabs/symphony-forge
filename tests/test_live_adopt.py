"""forge init in a repo with history adopts it on a fix branch, in one pull request."""
from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path

import pytest

from test_close import run
from test_migrate import _review_and_checks

STORY = "FORGE-LIVE-1"
BRANCH, ITEM = "fix/adopt-forge", "adopt-forge"
TEAM_AGENTS = "# Shop agents\n\nRun npm test before you push.\n"
ANSWERS = ("--test", "npm ci && npm test", "--checks", "build", "--checks", "lint",
           "--interfaces", "api/routes/**", "--interfaces", "db/migrations/**",
           "--approver", "Priya", "--merger", "Sam", "--never-touch", "billing/")
ENDPOINT = "repos/{owner}/{repo}/branches/main/protection"


def _live_app(repo) -> None:
    """A live app with history: its own AGENTS.md, routes, migrations and Claude settings."""
    repo.write("AGENTS.md", TEAM_AGENTS)
    repo.write("api/routes/orders.js", "module.exports = {};\n")
    repo.write("db/migrations/0001_orders.sql", "CREATE TABLE orders (id int);\n")
    repo.write(".claude/settings.json", json.dumps({"permissions": {"allow": ["Bash(npm test)"]}}))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "The shop")
    repo.git("push", "-q", "origin", "main")


def _snapshot(repo) -> list[str]:
    hooks = Path(repo.git("rev-parse", "--path-format=absolute", "--git-path", "hooks"))
    return [repo.git("status", "--porcelain", "--ignored", "-uall"), repo.git("for-each-ref"),
            repo.git("worktree", "list", "--porcelain"), " ".join(sorted(os.listdir(hooks)))]


def _adopts(repo, gh, tmp_path, monkeypatch) -> None:
    _live_app(repo)
    main = repo.git("rev-parse", "main")
    adopted = repo.forge("init", *ANSWERS)
    assert adopted.returncode == 0, adopted.stdout + adopted.stderr
    where = repo.path.parent / f"{repo.path.name}-fix-adopt-forge"
    assert f"Next: your tests in {where}, then forge close {ITEM}" in adopted.stdout

    # The default branch is untouched; the work is one commit on the fix branch.
    assert repo.git("rev-parse", "main", "origin/main").split() == [main, main]
    assert repo.git("rev-list", f"main..{BRANCH}").count("\n") == 0
    cfg = tomllib.loads(repo.git("show", f"{BRANCH}:forge.toml"))
    assert (cfg["repo"], cfg["stage"], cfg["merge"], cfg["test"]) == (
        "client", "live", "human", "npm ci && npm test")
    assert cfg["checks"] == ["build", "lint", "forge-pr-check"]
    assert cfg["interfaces"] == ["api/routes/**", "db/migrations/**"]
    # The team's lines stay; the house rules sit outside Forge's block.
    agents = repo.git("show", f"{BRANCH}:AGENTS.md")
    team, _, forge_block = agents.partition("<!-- forge:begin -->")
    assert team.startswith(TEAM_AGENTS)
    assert ("## House rules\n\n- Approves stories: Priya\n- Merges pull requests: Sam\n"
            "- Never touch: billing/\n") in team
    assert "Working here with Forge" in forge_block
    settings = json.loads(repo.git("show", f"{BRANCH}:.claude/settings.json"))
    assert settings["permissions"] == {"allow": ["Bash(npm test)"]} and "hooks" in settings
    assert repo.git("show", f"{BRANCH}:.claude/skills/forge/SKILL.md")
    assert "forge hook pre-commit" in (Path(repo.git(
        "rev-parse", "--path-format=absolute", "--git-path", "hooks")) / "pre-commit").read_text()
    # A live app gets no prototype skeleton, and nothing touched GitHub's protection yet.
    assert "Dockerfile" not in repo.git("ls-tree", "-r", "--name-only", BRANCH)
    assert not [call for call in gh.calls() if call[:1] == ["api"]]

    # It closes like a migration: Forge's own check waits until Forge is on the default branch,
    # and a human merges.
    _review_and_checks(repo, gh, tmp_path, monkeypatch)
    gh.respond("api", "--paginate", "--jq", ".check_runs[]",
               stdout="".join(json.dumps(run(name)) + "\n" for name in ("build", "lint")))
    closed = repo.forge("close", ITEM, cwd=where)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert closed.stdout.splitlines()[-1] == (
        f"Ready: {ITEM} has a clean review and green checks. A human merges its pull request.")
    assert not [call for call in gh.calls() if call[:3] == ["api", "--method", "PUT"]]

    # Once it merged, close switches protection on, keeping the team's own rules.
    gh.respond("pr", "list", stdout=json.dumps([{"number": 7, "state": "MERGED", "body": ""}]))
    gh.respond("api", "--method", "PUT", stdout="{}")
    gh.respond("api", ENDPOINT, stdout=json.dumps({
        "required_status_checks": {"strict": True, "contexts": ["build"]},
        "required_pull_request_reviews": {"required_approving_review_count": 2}}))
    merged = repo.forge("close", ITEM, cwd=where)
    assert merged.returncode == 0, merged.stderr
    assert "Its other rules stay as they were." in merged.stdout
    [put] = [call for call in gh.calls() if call[:3] == ["api", "--method", "PUT"]]
    body = json.loads(Path(put[put.index("--input") + 1]).read_text("utf-8"))
    assert body["required_status_checks"] == {"strict": True, "checks": [
        {"context": "build"}, {"context": "lint"}, {"context": "forge-pr-check"}]}
    assert body["required_pull_request_reviews"] == {"required_approving_review_count": 2}


def _stops(repo, gh, case: str) -> None:
    """Adoption stops with the reason and changes nothing."""
    _live_app(repo)
    args = ANSWERS
    if case == "taken files":  # the team's own files where Forge would write whole files
        repo.write(".claude/skills/forge/SKILL.md", "# Our own forge skill\n")
        repo.write(".github/workflows/forge.yml", "name: our forge deploy\n")
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Our tools")
        repo.git("push", "-q", "origin", "main")
    elif case in ("state file", "foreign forge.toml"):  # the team's files at Forge's own paths
        repo.write(".factory/fixes/adopt-forge.json" if case == "state file" else "forge.toml",
                   '{"owner": "the shop"}\n' if case == "state file" else
                   '# the shop\'s deploy tool\n[deploy]\nregion = "eu"\n')
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Our tools")
        repo.git("push", "-q", "origin", "main")
    elif case == "missing answers":
        args = ANSWERS[:2]
    elif case == "uncommitted":
        repo.write("notes.txt", "half done\n")
    else:  # a second run finds the first one's branch
        assert repo.forge("init", *ANSWERS).returncode == 0
    before = _snapshot(repo)
    refused = repo.forge("init", *args)
    assert refused.returncode == 1
    if case == "taken files":
        assert refused.stderr == (
            "forge init won't write over files that Forge didn't write: "
            ".claude/skills/forge/SKILL.md, .github/workflows/forge.yml.\n"
            "Next: move or rename those files, then forge init again\n"), refused.stderr
    elif case in ("state file", "foreign forge.toml"):
        path = ".factory/fixes/adopt-forge.json" if case == "state file" else "forge.toml"
        assert refused.stderr == (
            f"forge init won't write over files that Forge didn't write: {path}.\n"
            "Next: move or rename those files, then forge init again\n"), refused.stderr
    elif case == "uncommitted":
        assert refused.stderr == (
            "This checkout isn't clean at origin/main, which forge init adopts, so it can't check "
            "that tree here.\nNext: commit or set aside your changes, git switch main && git pull, "
            "then forge init again\n"), refused.stderr
    elif case == "adopting":
        assert refused.stderr == (
            "fix/adopt-forge is already there, so Forge has started adopting this repo.\n"
            "Next: forge close adopt-forge\n"), refused.stderr
    else:
        assert refused.stderr.startswith(
            "This repo already has commits, so forge init adopts it on a fix branch, and it needs "
            "the answers you confirmed: --checks, --interfaces, --approver, --merger.\n"
            "Next: forge init --test"), refused.stderr
    assert _snapshot(repo) == before and gh.calls() == []


def _keeps_gitattributes(repo) -> None:
    """The team's .gitattributes is kept and gets Forge's roadmap rule, not listed as taken."""
    _live_app(repo)
    repo.write(".gitattributes", "*.png binary\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Binary images")
    repo.git("push", "-q", "origin", "main")
    adopted = repo.forge("init", *ANSWERS)
    assert adopted.returncode == 0, adopted.stdout + adopted.stderr
    assert repo.git("show", f"{BRANCH}:.gitattributes") == (
        "*.png binary\nplans/roadmap.json merge=forge-roadmap")


@pytest.mark.parametrize("case", ["adopts", "team gitattributes", "taken files", "state file",
                                  "foreign forge.toml", "missing answers", "uncommitted",
                                  "adopting"])
def test_4_a_repo_with_history_adopts_forge(repo, gh, tmp_path, monkeypatch, case):
    if case == "adopts":
        _adopts(repo, gh, tmp_path, monkeypatch)
    elif case == "team gitattributes":
        _keeps_gitattributes(repo)
    else:
        _stops(repo, gh, case)
