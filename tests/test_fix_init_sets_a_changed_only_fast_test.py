"""forge init and adoption set fast_test to a changed-only command for the repo's test tool when
they recognise it, and leave it unset otherwise; Forge's own forge.toml uses the pytest one."""
from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_live_adopt import ANSWERS

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


def test_3_init_in_an_unknown_repo_leaves_fast_test_unset(repo, gh, tmp_path):
    cfg = _init(repo, gh, tmp_path, _node("mocha"))
    assert cfg["test"] and "fast_test" not in cfg


def test_4_adoption_sets_fast_test_for_a_vitest_repo(repo, gh):
    repo.write("package.json", json.dumps({"devDependencies": {"vitest": "^3.0.0"}}))
    repo.write("package-lock.json", "{}")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "The app")
    repo.git("push", "-q", "origin", "main")
    adopted = repo.forge("init", *ANSWERS)
    assert adopted.returncode == 0, adopted.stdout + adopted.stderr
    cfg = tomllib.loads(repo.git("show", "fix/adopt-forge:forge.toml"))
    assert cfg["fast_test"] == "npm ci && npx vitest run --changed {base} --passWithNoTests"


# Close runs the command through the shell; the multi-line python -c needs a POSIX shell.
@pytest.mark.skipif(sys.platform == "win32", reason="the pytest command needs a POSIX shell")
def test_5_init_in_a_pytest_repo_runs_changed_tests_and_their_importers(repo, gh, tmp_path):
    cfg = _init(repo, gh, tmp_path, {"pyproject.toml": "[project]\nname = 'shop'\n"})
    client = tmp_path / "client"
    git = lambda *args: subprocess.run(["git", *args], cwd=client, check=True,  # noqa: E731
                                       capture_output=True, text=True).stdout.strip()
    files = {"shop/__init__.py": "", "shop/orders.py": "TOTAL = 1\n", "shop/stock.py": "N = 1\n",
             "tests/test_orders.py": "from shop.orders import TOTAL\ndef test_total(): assert TOTAL\n",
             # These two fail, so the run passes only when it leaves them out.
             "tests/test_stock.py": "from shop import stock\ndef test_stock(): assert not stock\n",
             "tests/test_untouched.py": "def test_untouched(): assert False\n"}
    for rel, text in files.items():
        (client / rel).parent.mkdir(parents=True, exist_ok=True)
        (client / rel).write_text(text, encoding="utf-8")
    git("add", "-A")
    # The fixture's history, made outside Forge's lanes, so its git hooks are left out.
    git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-q", "-m", "The shop")
    base = git("rev-parse", "HEAD")

    def fast() -> subprocess.CompletedProcess[str]:
        # uv would build the client's environment; this interpreter already has pytest.
        command = cfg["fast_test"].replace("{base}", base).replace(
            "uv run python", f"'{sys.executable}'", 1)
        return subprocess.run(command, shell=True, cwd=client, capture_output=True, text=True)

    nothing = fast()
    assert nothing.returncode == 0, nothing.stdout + nothing.stderr
    assert "no tests ran" in nothing.stdout

    (client / "shop/orders.py").write_text("TOTAL = 2\n", encoding="utf-8")
    (client / "tests/test_new.py").write_text("def test_new(): assert True\n", encoding="utf-8")
    git("add", "-A")  # close runs on committed work, so the new test file is tracked
    ran = fast()
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert "2 passed" in ran.stdout  # test_orders imports the changed module, test_new changed

    git("rm", "-q", "shop/stock.py")  # a deleted module still picks the tests that import it
    broken = fast()
    assert broken.returncode != 0 and "test_stock" in broken.stdout, broken.stdout


def test_6_forge_s_own_forge_toml_uses_the_pytest_command(repo, gh, tmp_path):
    generated = _init(repo, gh, tmp_path, {"pyproject.toml": "[project]\nname = 'shop'\n"})
    own = tomllib.loads((ROOT / "forge.toml").read_text("utf-8"))
    assert own["fast_test"].startswith(
        generated["fast_test"].replace("uv run ", "uv run --python 3.11 ", 1))


def test_7_the_skill_tells_the_agent_to_propose_a_fast_test():
    text = " ".join((ROOT / "src/forge/templates/skill.md").read_text("utf-8").split())
    assert "has no `fast_test`, propose one" in text


@pytest.mark.skipif(sys.platform == "win32", reason="the pytest command needs a POSIX shell")
def test_8_adoption_keeps_an_interpreter_s_m_pytest(repo, gh):
    repo.write("pyproject.toml", "[project]\nname = 'shop'\n")
    repo.write("tests/test_old.py", "def test_old(): assert False\n")  # fails if picked
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "The app")
    repo.git("push", "-q", "origin", "main")
    answers = list(ANSWERS)
    answers[answers.index("--test") + 1] = f"'{sys.executable}' -m pytest tests"
    adopted = repo.forge("init", *answers)
    assert adopted.returncode == 0, adopted.stdout + adopted.stderr
    fast = tomllib.loads(repo.git("show", "fix/adopt-forge:forge.toml"))["fast_test"]
    assert fast.startswith(f"'{sys.executable}' -c \"")
    base = repo.git("rev-parse", "HEAD")
    repo.write("tests/test_new.py", "def test_new(): assert True\n")
    repo.git("add", "tests/test_new.py")
    ran = subprocess.run(fast.replace("{base}", base), shell=True, cwd=repo.path,
                         capture_output=True, text=True)
    assert ran.returncode == 0 and "1 passed" in ran.stdout, ran.stdout + ran.stderr
