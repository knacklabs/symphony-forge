"""Close selects supported runners locally and leaves the full suite to CI."""
import json
import os
import shutil
import sys
import tomllib
from pathlib import Path

import pytest

from conftest import ROOT, _install, patient
from test_close import GREEN, env, run  # noqa: F401
from test_machine_views import github, pull
from test_setup import _fresh_client
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FIX-TESTS-ONCE-PER-ROUND"


def _command(env, command):
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.repo.write("forge.toml", config + "test = " + json.dumps(command) + "\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "-m", "Existing client tests")
    env.repo.git("push", "-q", "origin", "main")


def test_1_close_selects_pytest_tests_and_red_ci_returns_the_item(env, tmp_path):
    receipts = tmp_path / "test-receipts"
    receipts.mkdir()
    for name in ("app", "changed", "unrelated"):
        env.repo.write(f"tests/test_{name}.py", ("import app\n" if name == "app" else "") + "from pathlib import Path\n"
                       "def test_client():\n"
                       f"    Path({json.dumps(str(receipts / name))}).write_text('ran', encoding='utf-8')\n")
    env.repo.write("app.py", "VALUE = 1\n")
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q'
    _command(env, command)
    item, where = env.start_fix({
        "app.py": "VALUE = 2\n",
        "tests/test_changed.py": (env.repo.path / "tests/test_changed.py").read_text("utf-8")
                                 + "# Changed test\n",
    })
    env.checks([run("tests", "failure"), run("forge-pr-check")])

    closed = env.close(item)

    assert sorted(path.name for path in receipts.iterdir()) == ["app", "changed"], closed.stdout + closed.stderr
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Checks failed on the pull request: tests." in closed.stderr
    assert f"Next: forge work {item}" in closed.stderr
    failed = pull(7, f"fix/{item}", conclusion="FAILURE")
    failed["headRefOid"] = env.repo.git("rev-parse", "HEAD", cwd=where)
    failed["commits"]["nodes"][0]["commit"]["oid"] = failed["headRefOid"]
    github(env.gh, [failed])
    next_step = env.repo.forge("next")
    assert next_step.returncode == 0, next_step.stderr
    assert f"forge work {item}" in next_step.stdout
    assert "checks failed" in next_step.stdout
    assert (where / "forge.toml").read_text("utf-8").endswith("test = " + json.dumps(command) + "\n")


@pytest.mark.parametrize("previous", [False, True], ids=["init", "upgrade-and-sync"])
@pytest.mark.parametrize("runner", ["jest", "vitest"])
def test_2_new_and_previously_adopted_clients_receive_local_selection_and_full_ci(
        unsynced_up, tmp_path, monkeypatch, previous, runner):
    up, repo = unsynced_up, unsynced_up.repo
    command = "[ ! -f package.json ] || (npm ci && npm test)"
    if previous:
        patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client",
                                       repo.path, dirs_exist_ok=True))
        # The previous release shipped this same optional-package command to Node clients.
        config = (repo.path / "forge.toml").read_text("utf-8")
        old_command = tomllib.loads(config)["test"]
        repo.write("forge.toml", config.replace("test = " + json.dumps(old_command),
                                               "test = " + json.dumps(command)))
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Client adopted on an earlier release")
        repo.git("push", "-q", "origin", "main")
        upgraded = up.run(RELEASE)
        assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
        client = up.folder
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
    else:
        client, initialized = _fresh_client(repo, up.env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    for host in (".claude", ".codex"):
        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        for rule in ("pytest", "Vitest", "Jest", "--changed", "--changedSince", "full test command"):
            assert rule in guide, rule
        assert "Go and other runners run the full test command" in guide
        assert "optional-package Node command" in guide
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    full_command = tomllib.loads((client / "forge.toml").read_text("utf-8"))["test"]
    assert full_command == command
    assert not tomllib.loads((client / "forge.toml").read_text("utf-8")).get("fast_test")
    assert "run: " + json.dumps(full_command) in workflow
    assert "fast_test" not in workflow

    # App adoption must keep init's command and select real runner tests at close.
    # The unrelated throwing test makes a full-suite fallback observable.
    assert shutil.which("npm"), "The initialized Node client regression requires npm."
    repo.path = client
    for name in list(os.environ):
        if name.lower().startswith("npm_config_"):
            monkeypatch.delenv(name)
    for kind in ("user", "global"):
        config = repo.write(f"npm-{kind}.rc", "")
        monkeypatch.setenv(f"NPM_CONFIG_{kind.upper()}CONFIG", config.as_posix())
    receipt = tmp_path / "initialized-node-receipt"
    script = ("npm exec --yes --package=jest@30.2.0 -- jest --runInBand" if runner == "jest" else
              "npm exec --yes --package=vitest@3.2.4 -- vitest run --globals --maxWorkers=1 --pool=threads --no-isolate")
    repo.write("package.json", json.dumps({"name": "client", "version": "1.0.0", "scripts": {"test": script}}))
    repo.write("package-lock.json", json.dumps({"name": "client", "version": "1.0.0", "lockfileVersion": 3,
                                              "packages": {"": {"name": "client", "version": "1.0.0"}}}))
    repo.write(".gitignore", "node_modules/\n")
    selected = "__tests__/cart.js" if runner == "jest" else "checks/cart.test.js"
    unrelated = "__tests__/unrelated.js" if runner == "jest" else "checks/unrelated.test.js"
    imports = "const fs = require('node:fs');\n" if runner == "jest" else "import fs from 'node:fs';\n"
    repo.write(selected, imports + f"test('client', () => fs.writeFileSync({json.dumps(str(receipt))}, 'ran'));\n")
    repo.write(unrelated, "test('unrelated', () => { throw new Error('unrelated test ran'); });\n")
    repo.git("add", "-A")
    # Fixture setup represents the application already landed on the client's main.
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-q", "-m", "Add the client application")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "push", "-q", "origin", "HEAD:main")
    item, where = up.env.start_fix({selected: (client / selected).read_text("utf-8") + "// Changed\n"})
    up.env.checks(GREEN)

    closed = up.env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert receipt.read_text("utf-8") == "ran", closed.stdout + closed.stderr
    settings = tomllib.loads((where / "forge.toml").read_text("utf-8"))
    assert settings["test"] == command and not settings.get("fast_test")


@pytest.mark.parametrize("runner", ["go", "custom", "compound-npm", "pipe-npm"])
def test_3_close_keeps_the_full_command_for_other_runners(env, tmp_path, monkeypatch, runner):
    # The recorded narrow replaces selective Go and generic filename forwarding with
    # unchanged full commands, including helper-only test edits and custom launchers.
    receipts = tmp_path / "full-receipts"
    receipts.mkdir()
    if runner == "go":
        assert shutil.which("go"), "The Go client regression requires Go."
        monkeypatch.setenv("GOCACHE", str(tmp_path / "go-cache"))
        env.repo.write("go.mod", "module example.com/cart\n\ngo 1.20\n")
        env.repo.write("helpers_test.go", "package cart\n\nfunc amount() int { return 2 }\n")
        for folder, name in (("", "cart"), ("other/", "other")):
            env.repo.write(folder + name + ".go", f"package {name}\n")
            env.repo.write(folder + name + "_test.go", f'package {name}\n\nimport ("os"; "testing")\n'
                           f"func TestClient(t *testing.T) {{\n"
                           f"if err := os.WriteFile({json.dumps(str(receipts / name))}, "
                           '[]byte("ran"), 0600); err != nil { t.Fatal(err) }\n}\n')
        command, changed, expected = "go test -v ./...", "helpers_test.go", ["cart", "other"]
    elif runner in {"compound-npm", "pipe-npm"}:
        assert shutil.which("npm"), "The npm shell command regression requires npm."
        for name in list(os.environ):
            if name.lower().startswith("npm_config_"):
                monkeypatch.delenv(name)
        for kind in ("user", "global"):
            config = env.repo.write(f"npm-{kind}.rc", "")
            monkeypatch.setenv(f"NPM_CONFIG_{kind.upper()}CONFIG", config.as_posix())
        env.repo.write("__tests__/cart.js", "const fs = require('node:fs');\n"
                       f"test('client', () => fs.writeFileSync({json.dumps(str(receipts / 'jest'))}, 'ran'));\n")
        env.repo.write("client-check.py", "from pathlib import Path\nimport sys\n"
                       "assert len(sys.argv) == 1, sys.argv\n"
                       + ("sys.stdin.read()\n" if runner == "pipe-npm" else "")
                       + f"Path({json.dumps(str(receipts / 'custom'))}).write_text('ran', encoding='utf-8')\n")
        client = f'"{Path(sys.executable).as_posix()}" client-check.py'
        script = "npm exec --yes --package=jest@30.2.0 -- jest --runInBand"
        if runner == "compound-npm":
            script += " && " + client
        env.repo.write("package.json", json.dumps({"name": "client", "scripts": {"test": script}}))
        command = "npm test" + (" | " + client if runner == "pipe-npm" else "")
        changed, expected = "__tests__/cart.js", ["custom", "jest"]
    else:
        env.repo.write("client-check.py", "from pathlib import Path\nimport sys\n"
                       "assert len(sys.argv) == 1, sys.argv\n"
                       f"Path({json.dumps(str(receipts / 'all'))}).write_text('ran', encoding='utf-8')\n")
        command = f'"{Path(sys.executable).as_posix()}" client-check.py'
        changed, expected = "client-check.py", ["all"]
    _command(env, command)
    item, _ = env.start_fix({changed: (env.repo.path / changed).read_text("utf-8") + "\n"})

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert sorted(path.name for path in receipts.iterdir()) == expected


@pytest.mark.parametrize("runner", ["vitest", "jest"])
@pytest.mark.parametrize("change", ["touched-test", "dependency"])
def test_4_close_uses_native_node_changed_files_including_jest_tests_directories(
        env, tmp_path, monkeypatch, runner, change):
    # Native discovery owns __tests__ and import graphs. The source and test names
    # deliberately differ, so filename guesses cannot supply this receipt.
    npm = shutil.which("npm")
    assert npm, "The Node client regression requires npm."
    for name in list(os.environ):
        if name.lower().startswith("npm_config_"):
            monkeypatch.delenv(name)
    for kind in ("user", "global"):
        config = env.repo.write(f"npm-{kind}.rc", "")
        monkeypatch.setenv(f"NPM_CONFIG_{kind.upper()}CONFIG", config.as_posix())
    receipt = tmp_path / "node-receipt"
    env.repo.write("package.json", '{"name":"client","version":"1.0.0"}\n')
    env.repo.write("shared.js", "module.exports = {value: 1};\n" if runner == "jest" else "export const value = 1;\n")
    selected = "__tests__/cart.js" if runner == "jest" else "checks/cart.test.js"
    unrelated = "__tests__/unrelated.js" if runner == "jest" else "checks/unrelated.test.js"
    imports = ("const fs = require('node:fs');\nconst {value} = require('../shared');\n" if runner == "jest" else
               "import fs from 'node:fs';\nimport {value} from '../shared.js';\n")
    env.repo.write(selected, imports +
                   f"test('client', () => {{ expect(value).toBe(1); fs.writeFileSync({json.dumps(str(receipt))}, 'ran'); }});\n")
    env.repo.write(unrelated, "test('unrelated', () => { throw new Error('unrelated test ran'); });\n")
    command = ("npm exec --yes --package=vitest@3.2.4 -- vitest run --globals --maxWorkers=1 --pool=threads --no-isolate"
               if runner == "vitest" else "npm exec --yes --package=jest@30.2.0 -- jest --runInBand")
    _command(env, command)
    changed = selected if change == "touched-test" else "shared.js"
    item, _ = env.start_fix({changed: (env.repo.path / changed).read_text("utf-8") + "// Changed\n"})

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert receipt.read_text("utf-8") == "ran", closed.stdout + closed.stderr


@pytest.mark.parametrize("setup_command", ["uv sync", "npm ci"])
def test_5_close_preserves_setup_arguments_before_selecting_pytest(env, tmp_path, setup_command):
    receipt = tmp_path / "python-receipt"
    setup = tmp_path / "uv-setup.jsonl"
    # uv is faked only at the package-manager edge; the actual Python interpreter
    # runs pytest and the fixture never supplies its test receipt.
    _install(env.repo.bin, "uv", f"#!{sys.executable}\nimport json, subprocess, sys\nfrom pathlib import Path\n"
             f"with Path({json.dumps(str(setup))}).open('a', encoding='utf-8') as out:\n"
             "    out.write(json.dumps(sys.argv[1:]) + '\\n')\n"
             "if sys.argv[1] == 'sync':\n    assert sys.argv[1:] == ['sync'], sys.argv\n"
             "else:\n    assert sys.argv[1:3] == ['run', 'pytest'], sys.argv\n"
             "    sys.exit(subprocess.call([sys.executable, '-m', *sys.argv[2:]]))\n")
    if setup_command == "npm ci":
        _install(env.repo.bin, "npm", f"#!{sys.executable}\nimport json, sys\nfrom pathlib import Path\n"
                 "assert sys.argv[1:] == ['ci'], sys.argv\n"
                 f"with Path({json.dumps(str(setup))}).open('a', encoding='utf-8') as out:\n"
                 "    out.write(json.dumps(sys.argv[1:]) + '\\n')\n")
    env.repo.write("tests/test_cart.py", "from pathlib import Path\n"
                   "def test_cart():\n"
                   f"    Path({json.dumps(str(receipt))}).write_text('ran', encoding='utf-8')\n")
    env.repo.write("tests/test_unrelated.py", "def test_unrelated():\n    raise AssertionError('unrelated test ran')\n")
    _command(env, setup_command + " && uv run pytest tests -q")
    item, _ = env.start_fix({"tests/test_cart.py": (env.repo.path / "tests/test_cart.py").read_text("utf-8") + "# Changed\n"})

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert receipt.read_text("utf-8") == "ran"
    assert json.loads(setup.read_text("utf-8").splitlines()[0]) == [setup_command.split()[1]]
