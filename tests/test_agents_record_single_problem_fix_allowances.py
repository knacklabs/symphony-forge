"""Init and upgrade sync deliver the allowance rule; close gives reviewers its reason.

This docs contract permits one problem across a repo, while retaining the five-file limit.
It fails if either host misses the guide or the actual review prompt loses the audit rule.
Only the external reviewer and GitHub are faked; no production test seam is needed.
"""
import json
import shutil
from pathlib import Path

import pytest

import conftest
from test_close import GREEN, env
from test_setup import _fresh_client
from test_story import worktree

STORY = "agent-allowance"


@pytest.mark.parametrize("adoption", ["new", "earlier release"])
def test_1_agents_record_single_problem_allowances_and_review_checks_the_reason(env, tmp_path,
                                                                            adoption):
    repo = env.repo
    config = (repo.path / "forge.toml").read_text("utf-8") + '\nrepo = "client"\n'
    if adoption == "new":
        client, made = _fresh_client(repo, env.gh, tmp_path)
        assert made.returncode == 0, made.stderr
        repo = env.repo = conftest.Repo(client, repo.bin)
    else:
        shutil.copytree(conftest.ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        assert 'version = "v1.2.2"' in (repo.path / "forge.toml").read_text("utf-8")
    repo.git("switch", "-q", "-c", "fix/refresh-guide")
    repo.write(".factory/fixes/refresh-guide.json", json.dumps({
        "kind": "fix", "status": "working", "branch": "fix/refresh-guide",
        "why": "Refresh the guide", "done_when": "The guide is current"}))
    repo.write("forge.toml", config)
    if adoption == "earlier release":
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stderr
    for host in (".codex", ".claude"):
        guide = " ".join((repo.path / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        for rule in (
            "five-code-file limit",
            'run `forge fix allow-large "<reason>"` yourself, without asking the human',
            "corrects one kind of problem in every place it appears and changes no interface",
            "Name that problem in the reason",
            "Anything else needs the human's allowance or a story",
        ):
            assert rule in guide, rule
    # Init's guide was checked before sync; now refresh the changed test configuration.
    if adoption == "new":
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stderr
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Refresh the coordinator guide")
    repo.git("push", "-q", "origin", "HEAD:refs/heads/refreshed")
    remote = Path(repo.git("remote", "get-url", "origin"))
    repo.git("update-ref", "refs/heads/main", repo.git("rev-parse", "HEAD"), cwd=remote)
    repo.git("fetch", "-q", "origin", "main")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/refresh-guide")
    started = repo.forge("fix", "start", "Repair missing labels", "--done", "Labels are present")
    assert started.returncode == 0, started.stderr
    folder = worktree(repo, "fix/repair-missing-labels")
    reason = "Repair missing labels in every place they appear without changing an interface"
    allowed = repo.forge("fix", "allow-large", reason, cwd=folder)
    assert allowed.returncode == 0, allowed.stderr
    env.commit(folder, "README.md", "# Labels are present\n")
    env.checks(GREEN)
    closed = env.close("repair-missing-labels")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    prompt = " ".join(env.prompt().split())
    assert f"Recorded allowance: {reason}" in prompt
    assert ("Report as P1 an allowance whose reason doesn't match the diff: more than one kind "
            "of problem, or an interface change") in prompt
