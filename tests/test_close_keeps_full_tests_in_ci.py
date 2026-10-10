"""Close runs related tests locally and leaves the full suite to the pull request."""
import json
import shutil
import sys
import tomllib
from pathlib import Path

import pytest

from conftest import ROOT, _install, patient
from test_close import env, run  # noqa: F401
from test_setup import _fresh_client
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FIX-TESTS-ONCE-PER-ROUND"

RULE = (
    "Close runs `fast_test` when set; otherwise it runs only changed test files and tests named "
    "after changed source files. CI runs the full suite."
)


@pytest.mark.parametrize("runner", ["pytest", "vitest", "jest"])
def test_1_close_runs_only_touched_and_source_named_tests_and_red_ci_returns_the_item(
        env, tmp_path, runner):
    # Old contract ran test in full without fast_test. The new contract keeps the full
    # command for CI even when shared inputs and explicit pytest roots also changed.
    receipts = tmp_path / "test-receipts"
    receipts.mkdir()
    if runner == "pytest":
        for name in ("app", "changed", "unrelated"):
            env.repo.write(f"tests/test_{name}.py", "from pathlib import Path\n"
                           "def test_client():\n"
                           f"    Path({json.dumps(str(receipts / name))}).write_text('ran', encoding='utf-8')\n")
        env.repo.write("app.py", "VALUE = 1\n")
        env.repo.write("conftest.py", "# Shared test setup\n")
        env.repo.write("pytest.ini", "[pytest]\naddopts = tests/test_unrelated.py\n")
        command = f'"{Path(sys.executable).as_posix()}" -m pytest tests tests/test_unrelated.py -q'
        changes = {
            "app.py": "VALUE = 2\n",
            "tests/test_changed.py": (env.repo.path / "tests/test_changed.py").read_text("utf-8")
                                     + "# Changed test\n",
            "conftest.py": "# Updated shared test setup\n",
        }
    else:
        # npm is an external boundary: its fake records the invocation, never selects
        # test files or supplies test receipts. The Python case proves actual execution.
        log = tmp_path / "npm-calls.jsonl"
        _install(env.repo.bin, "npm", f"#!{sys.executable}\n"
                 "import json, sys\nfrom pathlib import Path\n"
                 f"with Path({json.dumps(str(log))}).open('a', encoding='utf-8') as out:\n"
                 "    out.write(json.dumps(sys.argv[1:]) + '\\n')\n")
        env.repo.write("package.json", json.dumps({"scripts": {
            "test": "vitest run" if runner == "vitest" else "jest"}}))
        env.repo.write("src/cart page.ts", "export const value = 1;\n")
        for name in ("cart page.test.ts", "cart page.spec.ts", "changed.spec.ts", "unrelated.test.ts"):
            env.repo.write("checks with spaces/" + name, "// Existing test\n")
        command = "npm test"
        changes = {"src/cart page.ts": "export const value = 2;\n",
                   "checks with spaces/changed.spec.ts": "// Changed test\n"}
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.repo.write("forge.toml", config + "test = " + json.dumps(command) + "\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "-m", "Existing client tests")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix(changes)
    env.checks([run("tests", "failure"), run("forge-pr-check")])

    closed = env.close(item)

    if runner == "pytest":
        assert sorted(path.name for path in receipts.iterdir()) == ["app", "changed"], (
            closed.stdout + closed.stderr)
    else:
        calls = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
        assert len(calls) == 1, calls
        prefix = ["test", "--"] + (["--runTestsByPath"] if runner == "jest" else [])
        assert calls[0][:len(prefix)] == prefix
        assert sorted(calls[0][len(prefix):]) == [
            "checks with spaces/cart page.spec.ts", "checks with spaces/cart page.test.ts",
            "checks with spaces/changed.spec.ts",
        ]
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Checks failed on the pull request: tests." in closed.stderr
    assert f"Next: forge work {item}" in closed.stderr
    next_step = env.repo.forge("next")
    assert next_step.returncode == 0, next_step.stderr
    assert f"forge work {item}" in next_step.stdout
    assert "checks failed" in next_step.stdout
    assert (where / "forge.toml").read_text("utf-8").endswith(
        "test = " + json.dumps(command) + "\n")


@pytest.mark.parametrize("previous", [False, True], ids=["init", "upgrade-and-sync"])
def test_2_new_and_previously_adopted_clients_receive_local_selection_and_full_ci(
        unsynced_up, tmp_path, previous):
    up, repo = unsynced_up, unsynced_up.repo
    if previous:
        patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client",
                                       repo.path, dirs_exist_ok=True))
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Client adopted on an earlier release")
        repo.git("push", "-q", "origin", "main")
        upgraded = up.run(RELEASE)
        assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
        client = up.folder
    else:
        client, initialized = _fresh_client(repo, up.env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    for host in (".claude", ".codex"):
        guide = (client / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert RULE in " ".join(guide.split())
    # This shipped workflow is an independent GitHub runner contract, not a source detail.
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    full_command = tomllib.loads((client / "forge.toml").read_text("utf-8"))["test"]
    assert "run: " + json.dumps(full_command) in workflow
    assert "fast_test" not in workflow
