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

[models.grill.claude]
model = "opus"
effort = "high"

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


def _settings(top: Path, name: str) -> tuple[tuple, tuple]:
    """A role's ((model, effort) on Codex, (model, effort) on Claude Code)."""
    codex, claude = _codex(top, name), _claude(top, name)[0]
    return ((codex.get("model"), codex.get("model_reasoning_effort")),
            (claude.get("model"), claude.get("effort")))


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
        # Today's rules: building roles test first, commit and never push or merge; the rest
        # change nothing.
        rules = (("Write the end-to-end test first and watch it fail",
                  "A file outside the task's Scope that the change needs you may change; name it "
                  "and why in your handoff.",
                  "commit your own work with a short plain-English message",
                  "never commit to the default branch, skip the git hooks, push or merge")
                 if ROLES[name] == "build" else ("Change no files",))
        for rule in rules:
            assert rule in instructions, (name, rule)
    # Every role's (model, effort) on each host, from its kind; None means left out, so the
    # session's own applies on Codex. Claude implementations default to Sonnet, planning uses
    # grill, and diagnostics use Opus independently of legacy review settings.
    by_kind = {"build": ((None, "medium"), ("claude-opus-5-5", "medium")),
               "lite": (("gpt-6-luna", "ultra"), ("claude-sonnet-5-5", "xhigh")),
               "design": (("gpt-6.1-sol", "xhigh"), ("opus", "high")),
               "review": (("gpt-6-sol", None), ("claude-opus-5-5", "high"))}
    for name, kind in ROLES.items():
        assert _settings(repo.path, name) == by_kind[kind], name

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


def test_4_missing_design_leaves_codex_unpinned_and_claude_planning_uses_grill(repo):
    without_design = re.sub(r"\[models\.design\.\w+\]\n[^[]*", "", MODELS)
    assert "design" not in without_design and "[models.review]" in without_design

    assert _synced(repo, without_design).returncode == 0

    for name in ("planner", "architect"):
        assert _settings(repo.path, name) == ((None, None), ("opus", "high")), name
    assert _settings(repo.path, "worker") == ((None, "medium"), ("claude-opus-5-5", "medium"))


def test_5_a_value_from_forge_toml_stays_one_setting_and_grill_keeps_its_own_model(repo):
    # An escaped newline in a valid TOML string must not add a tools line to a Claude role, and
    # a plan-read entry's model is used as given, whatever its name looks like.
    models = MODELS.replace('model = "opus"', 'model = "custom-opus"').replace(
        'effort = "medium"', 'effort = "medium\\ntools: Bash"', 1)

    assert _synced(repo, models).returncode == 0

    for name in ROLES:
        text = (repo.path / f".claude/agents/{name}.md").read_text(encoding="utf-8")
        front = text.split("---\n")[1]
        assert not re.search(r"^tools:", front, re.M) and "permissionMode" not in front, name
    assert _claude(repo.path, "worker")[0]["effort"] == "medium\\ntools: Bash"
    for name in ("planner", "architect"):
        assert _settings(repo.path, name)[1] == ("custom-opus", "high"), name


def test_6_codex_roles_without_a_model_are_not_pinned_by_old_subagent_defaults(repo):
    # The old Forge's Codex config: a role that leaves its model out would run on these defaults
    # instead of the session's model.
    repo.git("checkout", "-q", "-b", "fix/roles")
    repo.write(".codex/config.toml", '[agents]\nmax_depth = 1\n'
                                     'default_subagent_model = "gpt-6-luna"\n'
                                     'default_subagent_reasoning_effort = "max"\n\n'
                                     '[agents.worker]\nconfig_file = "agents/worker.toml"\n')

    assert _synced(repo).returncode == 0

    config = tomllib.loads((repo.path / ".codex/config.toml").read_text(encoding="utf-8"))
    assert config["agents"] == {"max_depth": 1,
                                "worker": {"config_file": "agents/worker.toml"}}
    assert _settings(repo.path, "worker")[0] == (None, "medium")
    assert repo.forge("sync").stdout.startswith("Nothing to change")
