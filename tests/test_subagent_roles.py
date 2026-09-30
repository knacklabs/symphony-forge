"""forge sync writes Forge's subagent roles for Codex and Claude Code from forge.toml's models."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

STORY = "a-codex-or-claude-session-opened-directl"
ROOT = Path(__file__).resolve().parents[1]
ROLES = {"worker": "build", "coder": "build", "frontend": "build", "tester": "build",
         "refactorer": "build", "explorer": "lite", "planner": "design", "architect": "design",
         "debugger": "review", "security": "review", "performance": "review"}
MODELS = """
[models.build]
model = "claude-opus-5-5"
effort = "medium"

[models.lite]
model = "gpt-6-luna"
effort = "ultra"

[models.design.claude]
model = "opus"
effort = "high"

[models.design.codex]
model = "gpt-6.1-sol"
effort = "xhigh"

[models.review]
model = "gpt-6-sol"
"""


def _synced(repo, models: str = MODELS):
    if repo.git("branch", "--show-current") == "main":
        repo.git("checkout", "-q", "-b", "fix/roles")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ntest = "make check"\n{models}')
    return repo.forge("sync")


def _codex(top: Path, name: str) -> dict:
    return tomllib.loads((top / f".codex/agents/{name}.toml").read_text(encoding="utf-8"))


def _claude(top: Path, name: str) -> tuple[dict, str]:
    """A Claude Code role's frontmatter fields and its instructions."""
    text = (top / f".claude/agents/{name}.md").read_text(encoding="utf-8")
    front, body = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S).groups()
    fields = dict(line.split(": ", 1) for line in front.splitlines() if not line.startswith("#"))
    return {key: value.strip('"') for key, value in fields.items()}, body.strip()


def test_1_sync_writes_eleven_roles_for_both_hosts_from_forge_toml(repo):
    result = _synced(repo)

    assert result.returncode == 0, result.stderr
    for name in ROLES:
        assert f"Wrote .codex/agents/{name}.toml" in result.stdout
        assert f"Wrote .claude/agents/{name}.md" in result.stdout
        codex = _codex(repo.path, name)
        claude, instructions = _claude(repo.path, name)
        assert codex["name"] == claude["name"] == name
        assert codex["description"] == claude["description"] != ""
        assert codex["developer_instructions"] == instructions != ""
        # Roles set no tools, sandbox or permission mode: they inherit the session's.
        assert set(codex) <= {"name", "description", "developer_instructions", "model",
                              "model_reasoning_effort"}
        assert set(claude) <= {"name", "description", "model", "effort"}
        for old in ("constitution", "write scope", "Luna/max"):
            assert old not in instructions
    # Build roles take build's Claude model; on Codex it's the other family, so the model is left
    # out and the session's model applies, while the effort stays.
    assert _claude(repo.path, "coder")[0] == {"name": "coder", "description": _claude(
        repo.path, "coder")[0]["description"], "model": "claude-opus-5-5", "effort": "medium"}
    assert "model" not in _codex(repo.path, "coder")
    assert _codex(repo.path, "coder")["model_reasoning_effort"] == "medium"
    # The explorer takes lite's Codex model; Codex's ultra effort becomes max on Claude.
    assert (_codex(repo.path, "explorer")["model"],
            _codex(repo.path, "explorer")["model_reasoning_effort"]) == ("gpt-6-luna", "ultra")
    assert "model" not in _claude(repo.path, "explorer")[0]
    assert _claude(repo.path, "explorer")[0]["effort"] == "max"
    # Planner and architect take each host's own design entry.
    for name in ("planner", "architect"):
        assert (_codex(repo.path, name)["model"],
                _codex(repo.path, name)["model_reasoning_effort"]) == ("gpt-6.1-sol", "xhigh")
        assert (_claude(repo.path, name)[0]["model"], _claude(repo.path, name)[0]["effort"]) == (
            "opus", "high")
    # Review roles take review's model; review sets no effort, so none is written.
    for name in ("debugger", "security", "performance"):
        assert _codex(repo.path, name)["model"] == "gpt-6-sol"
        assert "model_reasoning_effort" not in _codex(repo.path, name)
        assert "model" not in _claude(repo.path, name)[0] and "effort" not in _claude(repo.path, name)[0]

    # A second sync changes nothing.
    before = {path: path.read_bytes() for path in repo.path.glob(".*/agents/*")}
    second = repo.forge("sync")
    assert second.returncode == 0, second.stderr
    assert second.stdout.startswith("Nothing to change")
    assert before == {path: path.read_bytes() for path in repo.path.glob(".*/agents/*")}

    # A changed model in forge.toml reaches the roles on the next sync.
    repo.write("forge.toml", (repo.path / "forge.toml").read_text(encoding="utf-8").replace(
        '"claude-opus-5-5"', '"sonnet"'))
    assert repo.forge("sync").returncode == 0
    assert _claude(repo.path, "worker")[0]["model"] == "sonnet"


def test_2_sync_refuses_to_overwrite_a_role_file_forge_did_not_write(repo):
    repo.git("checkout", "-q", "-b", "fix/own-role")
    ours = "---\nname: tester\ndescription: Our own tester\n---\n\nTest our way.\n"
    repo.write(".claude/agents/tester.md", ours)
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Our own tester role")

    result = _synced(repo)

    assert result.returncode == 1
    assert (".claude/agents/tester.md is a role of your own that Forge didn't write, and forge sync "
            "writes a role of that name; rename or delete your file, then sync again." in result.stderr)
    assert "Next: forge sync" in result.stderr
    # Nothing changed: only the forge.toml the test wrote is new.
    assert repo.git("status", "--porcelain", "-uall").splitlines() == ["?? forge.toml"]
    assert (repo.path / ".claude/agents/tester.md").read_text(encoding="utf-8") == ours


def test_3_forge_s_own_repo_has_the_roles_sync_writes_from_its_forge_toml(repo):
    own = (ROOT / "forge.toml").read_text(encoding="utf-8")
    models = own[own.index("[models."):]

    assert _synced(repo, models).returncode == 0

    for name in ROLES:
        for rel in (f".codex/agents/{name}.toml", f".claude/agents/{name}.md"):
            assert (ROOT / rel).read_text(encoding="utf-8") == (repo.path / rel).read_text(
                encoding="utf-8"), rel
