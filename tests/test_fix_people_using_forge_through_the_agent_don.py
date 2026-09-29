"""The skill coaches a person once at each Forge moment, in plain words."""

import subprocess

STORY = "FIX-PEOPLE-USING-FORGE-THROUGH-THE-AGENT-DON"

MOMENTS = ("A story plan shown for approval", "A cold read finding", "A part starting",
           "A pull request ready", "A merge", "A prototype demo", "Sign-off")
RULES = ("first time each of these happens for a person",
         "one plain sentence saying what just happened and what they can do next",
         "never repeat it", "never name commands unless they ask")


def _coaching(path):
    skills = [(path / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")
              for host in (".claude", ".codex")]
    assert skills[0] == skills[1]
    return skills[0].split("\n## Coaching\n")[1].split("\n## ")[0]


def _assert_coaches_each_moment(section):
    flat = " ".join(section.split())
    for rule in RULES:
        assert rule in flat, rule
    examples = {line.split(":", 1)[0].removeprefix("- "): line.split(":", 1)[1]
                for line in section.splitlines() if line.startswith("- ")}
    for moment in MOMENTS:
        example = examples[moment]
        assert example.strip().startswith('"') and "`" not in example, moment
        assert "forge " not in example.lower(), moment


def test_1_synced_skill_coaches_each_moment_once(repo):
    repo.git("checkout", "-q", "-b", "fix/skill-guidance")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ntest = "true"\n')
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    _assert_coaches_each_moment(_coaching(repo.path))


def test_1_new_client_skill_coaches_each_moment_once(repo, gh, tmp_path):
    client, remote = tmp_path / "client", tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    gh.respond("api", stdout="{}")
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')
    made = repo.forge("init", cwd=client)
    assert made.returncode == 0, made.stderr
    _assert_coaches_each_moment(_coaching(client))
