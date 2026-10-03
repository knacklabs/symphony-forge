"""forge init sets fast_test to a changed-only command when the repo's test tool has one built
in (vitest, jest), and leaves it unset otherwise."""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo

STORY = "FIX-REPOS-ONLY-GET-CHANGE-BASED-TEST-RUNS-AT"
ROOT = Path(__file__).parents[1]


def _init(repo, gh, tmp_path, files: dict[str, str]) -> dict:
    client = _new_repo(repo, gh, tmp_path)
    for rel, text in files.items():
        (client / rel).write_text(text, encoding="utf-8")
    result = repo.forge("init", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    return tomllib.loads((client / "forge.toml").read_text("utf-8"))


def _node(dev: str) -> dict[str, str]:
    return {"package.json": json.dumps({"devDependencies": {dev: "^1.0.0"}}),
            "package-lock.json": "{}"}


def test_1_init_in_a_vitest_repo_sets_vitest_changed(repo, gh, tmp_path):
    cfg = _init(repo, gh, tmp_path, _node("vitest"))
    assert cfg["fast_test"] == "npm ci && npx vitest run --changed {base} --passWithNoTests"


def test_2_init_in_a_jest_repo_sets_jest_changed_since(repo, gh, tmp_path):
    cfg = _init(repo, gh, tmp_path, _node("jest"))
    assert cfg["fast_test"] == "npm ci && npx jest --changedSince {base} --passWithNoTests"


def test_3_init_in_a_pytest_repo_leaves_fast_test_unset(repo, gh, tmp_path):
    cfg = _init(repo, gh, tmp_path, {"pyproject.toml": "[project]\nname = 'shop'\n"})
    assert cfg["test"] == "uv run pytest" and "fast_test" not in cfg


def test_4_the_skill_tells_the_agent_to_propose_a_fast_test():
    text = " ".join((ROOT / "src/forge/templates/skill.md").read_text("utf-8").split())
    assert "has no `fast_test`, propose one" in text
