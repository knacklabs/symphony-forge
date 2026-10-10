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
        assert "expands compound npm test scripts to select files in each workspace and in Playwright" in guide
        assert "NestJS `.e2e-spec` files count" in guide
    # This shipped workflow is an independent GitHub runner contract, not a source detail.
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    full_command = tomllib.loads((client / "forge.toml").read_text("utf-8"))["test"]
    assert "run: " + json.dumps(full_command) in workflow
    assert "fast_test" not in workflow


def test_3_close_runs_source_named_and_touched_go_tests_with_the_shipped_default(env, tmp_path, monkeypatch):
    # Forge ships a package-pattern command. Appending test filenames to it mixes
    # Go's invocation modes; running the whole package also runs unrelated tests.
    assert shutil.which("go"), "The Go client command regression requires Go."
    # Cached Go successes can replay output without rewriting receipts outside the module.
    monkeypatch.setenv("GOCACHE", str(tmp_path / "go-cache"))
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
    assert sorted(path.name for path in receipts.iterdir()) == ["Cart", "Discount"], closed.stdout + closed.stderr
    assert env.review_calls(), "Go's local selection must reach review."
    assert (where / "forge.toml").read_text("utf-8").endswith(
        "test = " + json.dumps(command) + "\n")

    # Confirm why the receipt fixture needs its own cache: unchanged Go inputs replay success.
    for receipt in receipts.iterdir():
        receipt.unlink()
    env.commit(where, "settings.json", "{}\n")
    again = env.close(item)
    assert again.returncode == 0, again.stdout + again.stderr
    assert "(cached)" in env.prompt(), env.prompt()
    assert list(receipts.iterdir()) == []


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


@pytest.mark.timeout(300)
def test_5_close_selects_tests_through_the_documented_workspace_and_playwright_command(env, tmp_path, monkeypatch):
    npm = shutil.which("npm")
    assert npm
    for name in list(os.environ):
        if name.lower().startswith("npm_config_"):
            monkeypatch.delenv(name)
    for kind in ("user", "global"):
        config = env.repo.write(f"npm-{kind}.rc", "")
        monkeypatch.setenv(f"NPM_CONFIG_{kind.upper()}CONFIG", config.as_posix())
    receipts = tmp_path / "workspace-receipts"
    receipts.mkdir()
    env.repo.write(".gitignore", "node_modules/\ntest-results/\nplaywright-report/\n")
    setup = tmp_path / "setup.jsonl"
    for tool, allowed in (("npx", [["playwright", "install", "--with-deps", "chromium"]]),
                          ("docker", [["compose", "-p", "forge-tests", "-f", "compose.test.yml", "down", "--volumes"],
                                      ["compose", "-p", "forge-tests", "-f", "compose.test.yml", "up", "-d", "--build", "--wait"]])):
        # Only external service/browser installation is faked; every test runner is real.
        _install(env.repo.bin, tool, f"#!{sys.executable}\nimport json, sys\nfrom pathlib import Path\n"
                 f"assert sys.argv[1:] in {allowed!r}, sys.argv\n"
                 f"with Path({json.dumps(str(setup))}).open('a', encoding='utf-8') as out:\n"
                 f"    out.write(json.dumps([{tool!r}, *sys.argv[1:]]) + '\\n')\n")
    script = ("npm run lint --workspaces --if-present && npm run typecheck --workspaces --if-present && "
              "npm run test --workspaces --if-present && playwright test")
    env.repo.write("package.json", json.dumps({"name": "client", "workspaces": ["frontend", "backend"],
                   "scripts": {"test": script}, "devDependencies": {"@playwright/test": "1.51.1"}}))
    for folder, runner in (("frontend", "vitest"), ("backend", "jest")):
        runner_script = ("npm exec --yes --package=vitest@3.2.4 -- vitest run --globals --maxWorkers=1 --pool=threads --no-isolate"
                         if runner == "vitest" else "npm exec --yes --package=jest@30.2.0 -- jest --runInBand")
        env.repo.write(f"{folder}/package.json", json.dumps({"name": folder, "scripts": {"test": runner_script}}))
        env.repo.write(f"{folder}/cart.test.js", "const fs = require('node:fs');\n"
                       f"test('selected', () => fs.writeFileSync({json.dumps(str(receipts / folder))}, 'ran'));\n")
        env.repo.write(f"{folder}/unrelated.test.js", "test('unrelated', () => { throw new Error('unrelated workspace ran'); });\n")
    env.repo.write("playwright.config.js", "module.exports = { testDir: './e2e', workers: 1 };\n")
    for name in ("cart", "unrelated"):
        action = (f"require('node:fs').writeFileSync({json.dumps(str(receipts / 'browser'))}, 'ran');"
                  if name == "cart" else "throw new Error('unrelated browser test ran');")
        env.repo.write(f"e2e/{name}.spec.js", "const {test} = require('@playwright/test');\n"
                       f"test('client', () => {{ {action} }});\n")
    env.repo.write("cart.js", "const value = 1;\n")
    locked = subprocess.run([npm, "install", "--package-lock-only", "--ignore-scripts"],
                            cwd=env.repo.path, capture_output=True, text=True, shell=os.name == "nt")
    assert locked.returncode == 0, locked.stdout + locked.stderr
    command = ("npm ci && npx playwright install --with-deps chromium && "
               "docker compose -p forge-tests -f compose.test.yml down --volumes && "
               "docker compose -p forge-tests -f compose.test.yml up -d --build --wait && npm test")
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.repo.write("forge.toml", config + "test = " + json.dumps(command) + "\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "-m", "Existing workspace client")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix({"cart.js": "const value = 2;\n"})
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert sorted(path.name for path in receipts.iterdir()) == ["backend", "browser", "frontend"]
    assert len(setup.read_text('utf-8').splitlines()) == 3
    assert (where / "forge.toml").read_text('utf-8').endswith("test = " + json.dumps(command) + "\n")


@pytest.mark.parametrize("change", ["touched-test", "source-named"])
def test_6_close_runs_conventional_nest_end_to_end_test_files(env, tmp_path, change):
    receipts = tmp_path / "nest-receipts"
    receipts.mkdir()
    env.repo.write("package.json", '{"name":"client"}\n')
    env.repo.write("app.ts", "const value = 1;\n")
    for name in ("app", "unrelated"):
        action = (f"require('node:fs').writeFileSync({json.dumps(str(receipts / 'app'))}, 'ran');"
                  if name == "app" else "throw new Error('unrelated e2e test ran');")
        env.repo.write(f"tests/{name}.e2e-spec.ts", f"test('client', () => {{ {action} }});\n")
    env.repo.write("jest.config.json", json.dumps({"testRegex": "[.]e2e-spec[.]ts$", "transform": {}}))
    command = 'npm exec --yes --package=jest@30.2.0 -- jest --runInBand --config=jest.config.json'
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.repo.write("forge.toml", config + "test = " + json.dumps(command) + "\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "-m", "Existing Nest client")
    env.repo.git("push", "-q", "origin", "main")
    changed = "tests/app.e2e-spec.ts" if change == "touched-test" else "app.ts"
    item, _ = env.start_fix({changed: (env.repo.path / changed).read_text('utf-8') + "// Changed\n"})
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert [path.name for path in receipts.iterdir()] == ["app"], env.prompt()
