"""Close runs related tests locally and leaves the full suite to the pull request."""
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from conftest import ROOT, _install, patient
from test_close import env, run  # noqa: F401
from test_machine_views import github, pull
from test_setup import _fresh_client
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FIX-TESTS-ONCE-PER-ROUND"

RULE = (
    "Close runs `fast_test` when set; otherwise it runs only changed test files and tests named "
    "after changed source files. CI runs the full suite."
)


@pytest.mark.parametrize("runner", ["pytest", "vitest", "jest", "exec-vitest", "exec-jest"])
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
        node_runner = runner.removeprefix("exec-")
        script = ("vitest run 'checks with spaces'" if node_runner == "vitest" else
                  "jest 'checks with spaces/unrelated.test.ts'")
        env.repo.write("package.json", json.dumps({"scripts": {"test": script}}))
        env.repo.write("src/cart page.ts", "export const value = 1;\n")
        for name in ("cart page.test.ts", "cart page.spec.ts", "changed.spec.ts", "unrelated.test.ts"):
            env.repo.write("checks with spaces/" + name, "// Existing test\n")
        command = "npm exec " + script if runner.startswith("exec-") else "npm test"
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
        # Runner file filters keep inherited roots or explicit test paths from bringing
        # the unrelated file back into the run. Verify the protocol, not flag ordering.
        prefix = (["exec", "--", node_runner] + (["run", "checks with spaces"] if node_runner == "vitest" else [
            "checks with spaces/unrelated.test.ts"])
                  if runner.startswith("exec-") else ["test", "--"])
        assert calls[0][:len(prefix)] == prefix
        arguments = calls[0][len(prefix):]
        if node_runner == "jest":
            arguments.remove("--runTestsByPath")
            flag, suffix = "--filter", ".cjs"
        else:
            flag, suffix = "--config", ".mjs"
        index = arguments.index(flag)
        assert arguments[index + 1].endswith(suffix)
        del arguments[index:index + 2]
        assert sorted(arguments) == [
            "checks with spaces/cart page.spec.ts", "checks with spaces/cart page.test.ts",
            "checks with spaces/changed.spec.ts",
        ]
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Checks failed on the pull request: tests." in closed.stderr
    assert f"Next: forge work {item}" in closed.stderr
    # Next reads GitHub's current PR head through GraphQL, separately from close's check API.
    failed = pull(7, f"fix/{item}", conclusion="FAILURE")
    failed["headRefOid"] = env.repo.git("rev-parse", "HEAD", cwd=where)
    failed["commits"]["nodes"][0]["commit"]["oid"] = failed["headRefOid"]
    github(env.gh, [failed])
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


def test_3_close_runs_source_named_and_touched_go_tests_with_the_shipped_default(env, tmp_path):
    # Forge ships a package-pattern command. Appending test filenames to it mixes
    # Go's invocation modes; running the whole package also runs unrelated tests.
    assert shutil.which("go"), "The Go client command regression requires Go."
    receipts = tmp_path / "go-test-receipts"
    receipts.mkdir()
    env.repo.write("go.mod", "module example.com/cart\n\ngo 1.20\n")
    env.repo.write("helper.go", "package cart\n\nfunc amount() int { return 2 }\n")
    env.repo.write("cart.go", "package cart\n\nfunc Cart() int { return 1 }\n")
    for filename, name in (("cart_test.go", "Cart"), ("discount_test.go", "Discount")):
        env.repo.write(filename, 'package cart\n\nimport ("os"; "testing")\n\n'
                       'const quote' + name + ' = \'"\'\n'
                       f"func Test{name}(t *testing.T) {{\n"
                       '    t.Log("selected client test")\n'
                       '    if Cart() != sharedAmount() { t.Fatal("wrong amount") }\n'
                       f"    if err := os.WriteFile({json.dumps(str(receipts / name))}, "
                       '[]byte("ran"), 0600); err != nil { t.Fatal(err) }\n}\n')
    env.repo.write("unrelated_test.go", 'package cart\n\nimport "testing"\n\n'
                   'func sharedAmount() int { return 2 }\n'
                   'func TestUnrelated(t *testing.T) { t.Fatal("unrelated root test ran") }\n')
    env.repo.write("inactive_test.go", '//go:build ignored_by_forge_fixture\n\npackage cart\n\n'
                   'import "testing"\nfunc TestUnrelated(t *testing.T) {}\n')
    env.repo.write("other/other.go", "package other\n\nconst Value = 1\n")
    env.repo.write("other/other_test.go", 'package other\n\nimport "testing"\n\n'
                   'func TestOther(t *testing.T) { t.Fatal("unrelated package ran") }\n')
    command = "go test -v ./..."
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.repo.write("forge.toml", config + "test = " + json.dumps(command) + "\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "-m", "Existing Go client tests")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix({
        "cart.go": "package cart\n\nfunc Cart() int { return amount() }\n",
        "discount_test.go": (env.repo.path / "discount_test.go").read_text("utf-8")
                            + "// Changed discount test\n",
        "inactive_test.go": (env.repo.path / "inactive_test.go").read_text("utf-8") + "// Changed inactive test\n",
    })

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert sorted(path.name for path in receipts.iterdir()) == ["Cart", "Discount"]
    assert env.review_calls(), "Go's local selection must reach review."
    assert (where / "forge.toml").read_text("utf-8").endswith(
        "test = " + json.dumps(command) + "\n")


@pytest.mark.parametrize("runner", ["vitest", "jest"])
@pytest.mark.parametrize("selected_count", [2, 250], ids=["small-change", "large-change"])
def test_4_close_keeps_node_selection_within_the_windows_shell_limit(
        env, tmp_path, monkeypatch, runner, selected_count):
    # The old command grew with every unrelated file. This transparent npm boundary
    # records transport size and delegates execution to the real installed runner.
    npm = shutil.which("npm")
    assert npm, "The Node client regression requires npm."
    for name in list(os.environ):
        if name.lower().startswith("npm_config_"):
            monkeypatch.delenv(name)
    for kind in ("user", "global"):
        config = env.repo.write(f"npm-{kind}.rc", "")
        monkeypatch.setenv(f"NPM_CONFIG_{kind.upper()}CONFIG", config.as_posix())
    log = tmp_path / "npm-transport.jsonl"
    output = tmp_path / "npm-output.txt"
    _install(env.repo.bin, "npm", f"#!{sys.executable}\n"
             "import json, os, subprocess, sys\nfrom pathlib import Path\n"
             f"with Path({json.dumps(str(log))}).open('a', encoding='utf-8') as out:\n"
             "    out.write(json.dumps(sys.argv[1:]) + '\\n')\n"
             f"words = [{json.dumps(npm)}, *sys.argv[1:]]\n"
             "ran = subprocess.run(subprocess.list2cmdline(words) if os.name == 'nt' else words, "
             "shell=os.name == 'nt', capture_output=True, text=True, encoding='utf-8')\n"
             f"with Path({json.dumps(str(output))}).open('a', encoding='utf-8') as out:\n"
             "    out.write(ran.stdout + ran.stderr)\n"
             "print(ran.stdout, end='')\nprint(ran.stderr, end='', file=sys.stderr)\nsys.exit(ran.returncode)\n")
    root = "client tests with long names"
    receipts = tmp_path / "node-receipts"
    receipts.mkdir()
    selected = ["cart", "changed"] + [f"changed-{index:03}" for index in range(selected_count - 2)]
    for name in selected:
        env.repo.write(f"{root}/{name}.test.js", "const fs = require('node:fs');\n"
                       f"test('client', () => fs.writeFileSync({json.dumps(str(receipts / name))}, 'ran'));\n")
    for index in range(250):
        env.repo.write(f"{root}/unrelated-{index:03}.test.js",
                       "test('unrelated', () => { throw new Error('unrelated test ran'); });\n")
    env.repo.write("package.json", '{"name":"client","version":"1.0.0"}\n')
    env.repo.write("cart.js", "const value = 1;\n")
    if runner == "vitest":
        config_file = "vitest.config.mjs" if selected_count == 2 else "client-vitest.config.mjs"
        env.repo.write(config_file, "export default { root: " + json.dumps(root) + " };\n")
        command = ("npm exec --yes --package=vitest@3.2.4 -- vitest run " + json.dumps(root)
                   + " --globals --maxWorkers=1 --no-file-parallelism --pool=threads --no-isolate")
        if selected_count > 2:
            command += " --config=" + config_file
    else:
        command = ("npm exec --yes --package=jest@30.2.0 -- jest "
                   + json.dumps(f"{root}/unrelated-000.test.js") + " --runInBand")
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.repo.write("forge.toml", config + "test = " + json.dumps(command) + "\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "-m", "Existing Node client tests")
    env.repo.git("push", "-q", "origin", "main")
    changes = {"cart.js": "const value = 2;\n"}
    for name in selected[1:]:
        filename = f"{root}/{name}.test.js"
        changes[filename] = (env.repo.path / filename).read_text("utf-8") + "// Changed test\n"
    item, _ = env.start_fix(changes)

    closed = env.close(item)

    assert closed.returncode == 0, (closed.stdout + closed.stderr
                                   + (output.read_text('utf-8') if output.exists() else ""))
    if log.exists():
        calls = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
        for arguments in calls:
            assert len(subprocess.list2cmdline([npm, *arguments])) < 8191, arguments
        assert len(calls) == 1 if selected_count == 2 else len(calls) > 1
    assert sorted(path.name for path in receipts.iterdir()) == sorted(selected)
