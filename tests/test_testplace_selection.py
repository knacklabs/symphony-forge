"""A change test runs its lint and only its related pytest files at the command boundary.

Test-audit gate:
1. Protects `forge test --change` selection and the configured command's shell setup.
2. A regression can run unrelated tests, skip lint, or lose the `cd` before lint runs.
3. Existing picker tests cover selection rules, but not close's no-match shell context.
4. The test invokes Forge's commands in a client repo; it needs no production-only seam.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from test_close import GREEN, env  # noqa: F401 (pytest fixture)

STORY = "FORGE-TESTPLACE-1/CISEL"


@pytest.mark.platform
@pytest.mark.parametrize("place", ["ci", "local"])
def test_2_change_tests_run_once_in_one_place(env, tmp_path, monkeypatch, place):
    """Close and the change command run lint and only related tests in the chosen place."""
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    receipts = tmp_path / "test-receipts"
    receipts.mkdir()
    python = json.dumps(Path(sys.executable).as_posix())
    command = f'{python} lint.py && {python} -m pytest tests -q'

    config = (env.repo.path / "forge.toml").read_text("utf-8")
    config = "\n".join(line for line in config.splitlines()
                       if line.partition("=")[0].strip() not in {"checks", "test", "test_place"})
    checks = ["tests", "forge-pr-check"] if place == "ci" else []
    env.repo.write("forge.toml", config + "\nchecks = " + json.dumps(checks) + "\n"
                   "test_place = " + json.dumps(place) + "\n"
                   "test = " + json.dumps(command) + "\n")
    env.repo.write("lint.py", "from pathlib import Path\n"
                   "p = Path('lint-runs')\n"
                   "with p.open('a', encoding='utf-8') as runs:\n"
                   "    runs.write('ran\\n')\n"
                   "if Path('lint-fails').exists():\n"
                   "    raise SystemExit(19)\n")
    ignore = (env.repo.path / ".gitignore").read_text("utf-8") if (env.repo.path / ".gitignore").exists() else ""
    env.repo.write(".gitignore", ignore + "\n__pycache__/\n.pytest_cache/\nlint-runs\nlint-fails\n")
    env.repo.write("cart.py", "VALUE = 1\n")
    original_cart = (env.repo.path / "cart.py").read_bytes()
    env.repo.write("shipping.py", "VALUE = 1\n")
    env.repo.write("tests/test_cart.py", "from pathlib import Path\nfrom cart import VALUE\n"
                   f"RECEIPT = {json.dumps(str(receipts / 'cart'))}\n"
                   "def test_cart():\n"
                   "    assert VALUE == 2\n"
                   "    with Path(RECEIPT).open('a', encoding='utf-8') as runs:\n"
                   "        runs.write('ran\\n')\n")
    env.repo.write("tests/test_shipping.py", "from pathlib import Path\nfrom shipping import VALUE\n"
                   f"RECEIPT = {json.dumps(str(receipts / 'shipping'))}\n"
                   "def test_shipping():\n"
                   "    assert VALUE == 1\n"
                   "    with Path(RECEIPT).open('a', encoding='utf-8') as runs:\n"
                   "        runs.write('ran\\n')\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "-m", "Set up a client change test")
    env.repo.git("push", "-q", "origin", "main")

    _, where = env.start_fix({"cart.py": "VALUE = 2\n"})
    env.checks(GREEN)
    env.open_pr("")

    if place == "ci":
        ci_closed = env.close("tidy-readme")
        assert ci_closed.returncode == 0, ci_closed.stdout + ci_closed.stderr
        assert not (where / "lint-runs").exists()
        assert not list(receipts.iterdir())
        assert "CI runs the change's related tests on the pull request" in env.prompt()
        assert any(".check_runs[]" in call for call in env.gh.calls())
        return

    local_closed = env.close("tidy-readme")

    assert local_closed.returncode == 0, local_closed.stdout + local_closed.stderr
    assert (where / "lint-runs").read_text("utf-8").splitlines() == ["ran"]
    assert {path.name: path.read_text("utf-8").splitlines() for path in receipts.iterdir()} == {
        "cart": ["ran"]}

    before = {path.name: len(path.read_text("utf-8").splitlines()) for path in receipts.iterdir()}
    lint_before = len((where / "lint-runs").read_text("utf-8").splitlines())

    changed = env.repo.forge("test", "--change", cwd=where)

    assert changed.returncode == 0, changed.stdout + changed.stderr
    assert len((where / "lint-runs").read_text("utf-8").splitlines()) == lint_before + 1
    after = {path.name: len(path.read_text("utf-8").splitlines()) for path in receipts.iterdir()}
    assert {name: after.get(name, 0) - before.get(name, 0) for name in set(before) | set(after)} == {
        "cart": 1}

    # Restore the exact baseline, including Windows newlines, so only spare.py changes.
    env.commit(where, "cart.py", original_cart.decode("utf-8"), "Restore the source module")
    env.commit(where, "spare.py", "VALUE = 1\n", "Change an unrelated module")
    before = {path.name: len(path.read_text("utf-8").splitlines()) for path in receipts.iterdir()}
    lint_before = len((where / "lint-runs").read_text("utf-8").splitlines())

    no_tests = env.close("tidy-readme")

    assert no_tests.returncode == 0, no_tests.stdout + no_tests.stderr
    assert len((where / "lint-runs").read_text("utf-8").splitlines()) == lint_before + 1
    after = {path.name: len(path.read_text("utf-8").splitlines()) for path in receipts.iterdir()}
    assert after == before

    (where / "lint-fails").write_text("fail\n", encoding="utf-8")
    env.commit(where, "spare.py", "VALUE = 2\n", "Change the unrelated module again")
    lint_before = len((where / "lint-runs").read_text("utf-8").splitlines())

    lint_failed = env.close("tidy-readme")

    assert lint_failed.returncode != 0, lint_failed.stdout + lint_failed.stderr
    assert len((where / "lint-runs").read_text("utf-8").splitlines()) == lint_before + 1
    after = {path.name: len(path.read_text("utf-8").splitlines()) for path in receipts.iterdir()}
    assert after == before
    (where / "lint-fails").unlink()

    env.commit(where, "cart.py", "VALUE = 2\n", "Change the cart module")
    env.commit(where, "shipping.py", "VALUE = 1\n# revised\n", "Change the shipping module")
    before = {path.name: len(path.read_text("utf-8").splitlines()) for path in receipts.iterdir()}
    lint_before = len((where / "lint-runs").read_text("utf-8").splitlines())

    broad = env.close("tidy-readme")

    assert broad.returncode == 0, broad.stdout + broad.stderr
    assert len((where / "lint-runs").read_text("utf-8").splitlines()) == lint_before + 1
    after = {path.name: len(path.read_text("utf-8").splitlines()) for path in receipts.iterdir()}
    assert {name: after.get(name, 0) - before.get(name, 0) for name in set(before) | set(after)} == {
        "cart": 1, "shipping": 1}


@pytest.mark.platform
def test_3_no_matching_tests_keep_the_configured_shell_context(env, tmp_path, monkeypatch):
    """Close runs retained lint from its configured directory and skips unrelated pytest files."""
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    python = json.dumps(Path(sys.executable).as_posix())
    command = f'cd backend && {python} lint.py && {python} -m pytest tests -q'
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    config = "\n".join(line for line in config.splitlines()
                       if line.partition("=")[0].strip() not in {"checks", "test", "test_place"})
    env.repo.write("forge.toml", config + "\nchecks = []\ntest_place = \"local\"\n"
                   "test = " + json.dumps(command) + "\n")
    env.repo.write("backend/lint.py", "from pathlib import Path\n"
                   "p = Path('../lint-runs')\n"
                   "with p.open('a', encoding='utf-8') as runs:\n"
                   "    runs.write('ran\\n')\n")
    receipt = tmp_path / "unrelated-pytest-ran"
    env.repo.write("backend/tests/test_unrelated.py", "from pathlib import Path\n"
                   f"RECEIPT = {json.dumps(str(receipt))}\n"
                   "def test_unrelated():\n"
                   "    Path(RECEIPT).write_text('ran', encoding='utf-8')\n")
    ignore = (env.repo.path / ".gitignore").read_text("utf-8") if (env.repo.path / ".gitignore").exists() else ""
    env.repo.write(".gitignore", ignore + "\n__pycache__/\n.pytest_cache/\nlint-runs\nlint-fails\n")
    no_hooks = tmp_path / "setup-hooks"
    no_hooks.mkdir()
    hook_setting = f"core.hooksPath={no_hooks.as_posix()}"
    env.repo.git("-c", hook_setting, "add", "-A")
    env.repo.git("-c", hook_setting, "commit", "-q", "-m", "Set the shell-context test command")
    env.repo.git("-c", hook_setting, "push", "-q", "origin", "main")

    _, where = env.start_fix({"spare.py": "VALUE = 1\n"})
    env.checks(GREEN)
    env.open_pr("")
    closed = env.close("tidy-readme")

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert (where / "lint-runs").read_text("utf-8").splitlines() == ["ran"]
    assert not receipt.exists()
