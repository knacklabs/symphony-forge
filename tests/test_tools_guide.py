"""The shipped coordinator and worker prompts explain the tools setting."""
from conftest import ROOT

STORY = "FORGE-TOOLS-1"


def test_9_synced_guides_explain_tools_and_the_session_handoff(repo):
    # Prompt text is the public contract here; exercise its delivery through sync too.
    repo.git("checkout", "-q", "-b", "fix/tools-guide")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ntest = "true"\n')
    template = (ROOT / "src/forge/templates/skill.md").read_text(encoding="utf-8")
    # Fixture sync cannot detect stale guides delivered in this checkout.
    for host in (".claude", ".codex"):
        assert (ROOT / host / "skills/forge/SKILL.md").read_text(encoding="utf-8") == template
    for adopted in (False, True):
        if adopted:
            for host in (".claude", ".codex"):
                path = f"{host}/skills/forge/SKILL.md"
                previous = ROOT / "tests/fixtures/adopted-v1.2.2/client" / path
                repo.write(path, previous.read_text(encoding="utf-8"))
        result = repo.forge("sync")
        assert result.returncode == 0, result.stdout + result.stderr
        for host in (".claude", ".codex"):
            skill = (repo.path / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")
            assert skill == template
            for intent, setting in (("Run everything in Claude", 'tools = "claude"`, `workers = "claude"'),
                                    ("Run everything in Codex", 'tools = "codex"`, `workers = "codex"'),
                                    ("Use both", 'tools = "both"')):
                row = next(line for line in skill.splitlines() if f'"{intent}"' in line)
                assert "Ask, then in a fix:" in row and setting in row
                assert "forge close <fix>" in row
                if intent != "Use both":
                    assert "forge sync" in row
            tools = skill.split("## Tools\n", 1)[1].split("\n## ", 1)[0]
            assert len(tools.splitlines()) <= 40
            tools = " ".join(tools.split())
            for contract in ("the app the developer opens", "both", "workers",
                             "background subagent", "other tool", "kit", "Codex app server",
                             "Claude Agent SDK", "Autoreview", "default model and effort",
                             "forge handback", "last message and id", "continue the named subagent",
                             "nudge", "never edit the brief", "Upgrade Forge", "before adding"):
                assert contract in tools, contract
    brief = (ROOT / "src/forge/templates/brief.md").read_text(encoding="utf-8")
    assert "A subagent never runs `forge handback`, `forge work` or `forge stop` itself." in brief
