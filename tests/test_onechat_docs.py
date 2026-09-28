STORY = "FORGE-ONECHAT-1"

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_5_guide_and_synced_remote_skill_explain_one_chat_approval(repo):
    repo.git("checkout", "-q", "-b", "fix/one-chat-docs")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ntest = "true"\n')

    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr

    guide = (ROOT / "docs/guide.md").read_text(encoding="utf-8")
    approval = guide.split("## How a story runs\n", 1)[1].split("\n## ", 1)[0]
    assert "one main chat" in approval
    assert "every Forge repo this machine has used" in approval
    assert "Plan Mode" in approval

    skill = (repo.path / ".claude/skills/remote-approval/SKILL.md").read_text(
        encoding="utf-8")
    assert "story approval" not in skill.lower()
    assert "approving a story" not in skill.lower()
    assert "Plan Mode" not in skill
    assert "Client migration check" in skill
