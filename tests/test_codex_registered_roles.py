"""Sync makes shipped Codex roles available and applies the team's subagent budget."""
import shutil
import tomllib
from pathlib import Path

import pytest

from conftest import patient

STORY = "codex-sessions-opened-in-client-repos-ha"
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_sync_registers_shipped_roles_and_keeps_team_roles(repo, adopted):
    if adopted:
        patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client",
                                         repo.path, dirs_exist_ok=True))
    repo.git("checkout", "-q", "-b", "fix/registered-roles")
    repo.write(".codex/config.toml", '# Team settings\n[agents]\nmax_depth = 2\n'
               '[agents.researcher]\nconfig_file = "team/researcher.toml"\n'
               'description = "Our research role"\n'
               '[agents.worker]\nconfig_file = "agents/worker.toml"\n')
    repo.write(".codex/team/researcher.toml", 'model = "gpt-6-luna"\n')
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ntest = "make check"\n')
    result = repo.forge("sync")
    assert result.returncode == 0, result.stderr
    config_path = repo.path / ".codex/config.toml"
    config = tomllib.loads(config_path.read_text("utf-8"))
    assert config["agents"]["max_depth"] == 2
    assert config["agents"]["researcher"] == {
        "config_file": "team/researcher.toml", "description": "Our research role"}
    assert (repo.path / ".codex/team/researcher.toml").read_text("utf-8") == 'model = "gpt-6-luna"\n'
    assert "# Team settings" in config_path.read_text("utf-8")
    shipped = list(repo.path.glob(".codex/agents/*.toml"))
    assert any(path.stem == "fixer" for path in shipped)
    for path in shipped:
        role = tomllib.loads(path.read_text("utf-8"))
        assert config["agents"][path.stem]["config_file"] == f"agents/{path.name}"
        assert config["agents"][path.stem]["description"] == role["description"]
    assert repo.forge("sync").stdout.startswith("Nothing to change")


@pytest.mark.parametrize("source,adopted", [("build", False), ("lite", False), ("flat", False),
                                          ("none", False), ("claude-only", False), ("lite", True)])
def test_2_sync_uses_build_subagents_then_lite_and_unsets_missing_defaults(repo, source, adopted):
    if adopted:
        patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client",
                                         repo.path, dirs_exist_ok=True))
    repo.git("checkout", "-q", "-b", "fix/subagent-budget")
    version = repo.forge("--version").stdout.split()[-1]
    build = ('[models.build.codex]\nmodel = "gpt-6-astra"\neffort = "high"\n')
    lite = ('[models.lite.codex]\nmodel = "gpt-6.1-sol"\neffort = "medium"\n')
    budget = 'subagents = "gpt-6-luna"\nsubagent_effort = "max"\n'
    models = (build + budget + lite + 'subagents = "gpt-6-sol"\nsubagent_effort = "low"\n'
              if source == "build" else build + lite + budget if source == "lite" else
              build.replace(".codex", "") + budget if source == "flat" else
              '[models.build.claude]\nmodel = "fable"\neffort = "high"\n' + budget
              if source == "claude-only" else build + lite)
    repo.write("forge.toml", f'version = "{version}"\ntest = "make check"\n{models}')
    if source != "flat":
        repo.write(".codex/config.toml", '[agents]\ndefault_subagent_model = "stale"\n'
                   'default_subagent_reasoning_effort = "low"\n')
    result = repo.forge("sync")
    assert result.returncode == 0, result.stderr
    agents = tomllib.loads((repo.path / ".codex/config.toml").read_text("utf-8"))["agents"]
    if source in ("none", "claude-only"):
        assert "default_subagent_model" not in agents
        assert "default_subagent_reasoning_effort" not in agents
    else:
        assert agents["default_subagent_model"] == "gpt-6-luna"
        assert agents["default_subagent_reasoning_effort"] == "max"
        # Explicit role settings must not override the hands-on subagent budget.
        for name in ("worker", "fixer", "coder", "frontend", "tester", "refactorer"):
            role = tomllib.loads((repo.path / f".codex/agents/{name}.toml").read_text("utf-8"))
            assert (role.get("model"), role.get("model_reasoning_effort")) == ("gpt-6-luna", "max")
    assert repo.forge("sync").stdout.startswith("Nothing to change")
