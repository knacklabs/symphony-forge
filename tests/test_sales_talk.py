"""The salesperson sees demo guidance and the next step from the real Forge command."""

import json

from test_close import GREEN, env, run

STORY = "FORGE-SALES-1"


def test_3_sync_teaches_demo_rounds_and_platform_handoff(repo):
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\n')
    repo.git("checkout", "-q", "-b", "fix/demo-guidance")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    for host in (".claude", ".codex"):
        skill = (repo.path / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")
        prototype = skill.split("\n## Prototype\n")[1].split("\n## ")[0]
        for instruction in ("one conversation", "one prototype fix", "demo round",
                            "next version is live", "reviewer found", "deploy platform",
                            "sign-off decision"):
            assert instruction in prototype


def test_4_next_reminds_of_platform_from_fetched_default_branch(env):
    repo = env.repo
    repo.write("Dockerfile", "FROM scratch\n")
    repo.write("docs/product/BRIEF.md", "# Brief\n\n## Answers\n\n## Demo\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Set up prototype")
    repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    env.open_pr("", draft=True)
    env.checks([run("tests", None, "in_progress"), run("forge-pr-check")])
    pending = env.close(item)
    assert pending.returncode == 1
    assert f"Next: forge close {item}" in pending.stderr

    # CI has turned green, but close has not saved a ready receipt yet.
    url = "https://github.com/acme/shop/pull/7"
    repo_pr = {"headRefName": "fix/tidy-readme", "url": url, "isDraft": False,
               "statusCheckRollup": [
                   {"name": name, "conclusion": "SUCCESS",
                    "completedAt": "2026-09-28T16:00:00+00:00"}
                   for name in ("tests", "forge-pr-check")]}
    env.gh.respond("pr", "list", "--state", "open", stdout=json.dumps([repo_pr]))
    green = repo.forge("next", cwd=where)
    assert green.returncode == 0, green.stderr
    assert f"Next: forge close {item}" in green.stdout
    assert f"Next: merge {url}" not in green.stdout

    env.checks(GREEN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    assert closed.stdout.splitlines()[-1] == f"Next: forge merge {item}"

    missing = repo.forge("next", cwd=where)
    assert missing.returncode == 0, missing.stderr
    assert f"Next: forge merge {item}" in missing.stdout
    assert "connect the repo" in missing.stdout
    assert "deploy platform" in missing.stdout
    assert "subdomain" in missing.stdout
    assert "docs/product/BRIEF.md" in missing.stdout

    # The checkout's unmerged address cannot suppress the default branch reminder.
    (where / "docs/product/BRIEF.md").write_text(
        "# Brief\n\n## Demo\n- Address: https://demo.example\n", encoding="utf-8")
    assert "connect the repo" in repo.forge("next", cwd=where).stdout
    repo.write("docs/product/BRIEF.md", "# Brief\n\n## Demo\n- Address: https://demo.example\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Record demo address")
    repo.git("push", "-q", "origin", "main")
    assert "connect the repo" not in repo.forge("next", cwd=where).stdout
    repo.write("docs/product/BRIEF.md", "# Brief\n\n## Demo\n")
    repo.write("docs/decisions/0001-client-signoff.md", "---\nstatus: accepted\n---\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Record sign-off")
    repo.git("push", "-q", "origin", "main")
    signed = repo.forge("next", cwd=where)
    assert "connect the repo" not in signed.stdout
    assert f"Next: merge {url}, then forge next" in signed.stdout
