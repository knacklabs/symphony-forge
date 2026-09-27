"""A new owner direction is resolved before the coordinator changes the repo."""
import subprocess

STORY = "FIX-OWNER-DIRECTION"


def test_1_new_direction_is_grilled_before_changes_in_both_synced_skills(repo, gh, tmp_path):
    client, remote = tmp_path / "client", tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    gh.respond("api", stdout="{}")
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')
    started = repo.forge("init", cwd=client)
    assert started.returncode == 0, started.stderr

    skills = [(client / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")
              for host in (".claude", ".codex")]
    assert skills[0] == skills[1]
    rule = " ".join(skills[0].split("\n## New directions\n")[1].split("\n## ")[0].split())
    for instruction in ("direction, principle or value", "grill", "before changing anything",
                        "one question at a time", "recommended answer", "look up facts in the repo",
                        "until the plan for applying it is agreed", "then make the changes"):
        assert instruction in rule, instruction
