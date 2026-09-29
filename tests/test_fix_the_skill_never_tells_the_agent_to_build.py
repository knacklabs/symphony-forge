"""The skill's prototype steps cover demo data, the customer's words and the demo toolbar."""

import subprocess

STORY = "FIX-THE-SKILL-NEVER-TELLS-THE-AGENT-TO-BUILD"

RULES = ("build the demo-data loader in the first version",
         "`## Words they use`", "for screen labels",
         "click an element in the demo build, write what's wrong and paste the output to the agent")


def _prototype(path):
    skills = [(path / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")
              for host in (".claude", ".codex")]
    assert skills[0] == skills[1]
    return " ".join(skills[0].split("\n## Prototype\n")[1].split("\n## ")[0].split())


def test_1_synced_skill_tells_the_agent_the_prototype_steps(repo):
    repo.git("checkout", "-q", "-b", "fix/skill-guidance")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ntest = "true"\n')
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    prototype = _prototype(repo.path)
    for rule in RULES:
        assert rule in prototype, rule


def test_2_new_client_skill_tells_the_agent_the_prototype_steps(repo, gh, tmp_path):
    client, remote = tmp_path / "client", tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    gh.respond("api", stdout="{}")
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')
    made = repo.forge("init", cwd=client)
    assert made.returncode == 0, made.stderr
    prototype = _prototype(client)
    for rule in RULES:
        assert rule in prototype, rule
