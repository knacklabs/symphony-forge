"""Forge caps arguments delivered to Node runners at their process boundary."""
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT, _install, machine_cores

STORY = "FIX-NODE-TEST-BUDGET"
NODE = shutil.which("node")


def client(repo, gh, upgrade):
    if upgrade:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        old = (repo.path / "forge.toml").read_text("utf-8")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier release")
        repo.git("checkout", "-qb", "fix/client-budget")
        version = repo.forge("--version").stdout.split()[-1]
        repo.write("forge.toml", old.replace('version = "v1.2.2"', f'version = "{version}"'))
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        repo.git("checkout", "main")
    else:
        repo.git("checkout", "--orphan", "fresh")
        gh.respond("api", stderr="Branch not protected", exit=1)
        gh.respond("api", "--method", "PUT", stdout="{}")
        initialized = repo.forge("init")
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr


@pytest.mark.parametrize("setting,command,script,expected", [
    (setting, prefix + runner + options, None, expected)
    for setting in ("test", "fast_test")
    for runner in ("vitest", "jest")
    for prefix in ("", "npx ")
    for options, expected in ((" run", ["run", "--maxWorkers=2"]),
                              (" --maxWorkers=1", ["--maxWorkers=1"]),
                              (" --maxWorkers 8", ["--maxWorkers", "2"]))
] + [
    (setting, command, script, [serial])
    for setting in ("test", "fast_test")
    for serial in ("--runInBand", "-i")
    for command, script in (("jest " + serial, None), ("npx jest " + serial, None),
                            ("npm run check -- " + serial, "jest"))
] + [
    ("fast_test", "npm test", "jest " + serial, [serial])
    for serial in ("--runInBand", "-i")
] + [
    ("fast_test", manager + " run check", runner + " run", ["run", "--maxWorkers=2"])
    for manager in ("npm", "pnpm", "yarn") for runner in ("vitest", "jest")
] + [
    ("fast_test", manager + " run check", runner + " run --maxWorkers=8",
     ["run", "--maxWorkers=2"])
    for manager in ("npm", "pnpm", "yarn") for runner in ("vitest", "jest")
] + [
    ("test", "npm test", "vitest --maxWorkers=1", ["--maxWorkers=1"]),
    ("test", "jest --maxWorkers=1%", None, ["--maxWorkers=1%"]),
    ("fast_test", "vitest --maxWorkers=90%", None, ["--maxWorkers=2"]),
    ("test", "other vitest", None, ["vitest"]),
    ("test", "other --maxWorkers=8", None, ["--maxWorkers=8"]),
    ("test", "npm run check", "other vitest", ["vitest"]),
    ("test", "npm run check", "vitest && other", []),
    ("upgrade", "jest run", None, ["run", "--maxWorkers=2"]),
    ("upgrade", "jest --runInBand", None, ["--runInBand"]),
])
def test_1_node_runners_obey_the_machine_budget(repo, gh, monkeypatch, setting, command, script, expected):
    # These third-party executables only record arguments. Forge must choose the cap.
    assert NODE, "The Node runner contract requires Node.js"
    recorder = '''require('node:fs').writeFileSync('observed.json', JSON.stringify(process.argv.slice(2)))
'''
    for runner in ("vitest", "jest", "other"):
        path = repo.bin / runner
        path.write_text(f"#!{Path(NODE).as_posix()}\n" + recorder, "utf-8")
        path.chmod(0o755)
        if sys.platform == "win32":
            (repo.bin / (runner + ".cmd")).write_text(
                f'@"{Path(NODE).as_posix()}" "%~dp0{runner}" %*\n', "utf-8")
    dispatcher = '''import json, os, pathlib, shlex, subprocess, sys
args = sys.argv[1:]
if pathlib.Path(sys.argv[0]).stem != 'npx':
    name = args.pop(0)
    if name == 'run': name = args.pop(0)
    if name == 'exec' and args[:1] == ['--no']: args.pop(0)
    if args[:1] == ['--']: args.pop(0)
    command = args.pop(0) if name == 'exec' else json.loads(
        pathlib.Path('package.json').read_text('utf-8'))['scripts'][name]
else:
    command = args.pop(0)
command += ' ' + (subprocess.list2cmdline(args) if os.name == 'nt' else shlex.join(args))
raise SystemExit(subprocess.call(command, shell=True))
'''
    for manager in ("npm", "pnpm", "yarn", "npx"):
        _install(repo.bin, manager, f"#!{sys.executable}\n" + dispatcher)
    machine_cores(repo, 8)
    monkeypatch.setenv("FORGE_TEST_CPUS", "2")
    client(repo, gh, setting == "upgrade")
    if setting == "upgrade":
        setting = "test"
    config = (repo.path / "forge.toml").read_text("utf-8")
    if setting == "fast_test":
        config = 'fast_test = ' + json.dumps(command) + '\n' + config
    else:
        config = re.sub(r'^test = .*$', 'test = ' + json.dumps(command), config, flags=re.M)
    repo.write("forge.toml", config)
    if script:
        repo.write("package.json", json.dumps({"scripts": {"check": script, "test": script}}))
    ran = repo.forge("test")
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert json.loads((repo.path / "observed.json").read_text("utf-8")) == expected


@pytest.mark.parametrize("upgrade", [False, True], ids=["new", "earlier-adopted"])
def test_2_npm_script_caps_keep_their_lifecycle(repo, gh, monkeypatch, upgrade):
    # Real npm must run its hooks; the runner only records the arguments it receives.
    assert NODE and shutil.which("npm"), "The npm lifecycle contract requires Node.js and npm"
    machine_cores(repo, 8)
    monkeypatch.setenv("FORGE_TEST_CPUS", "2")
    client(repo, gh, upgrade)
    repo.write("prepare.cjs", "const fs = require('node:fs');\n"
               "fs.writeFileSync('fixture', 'ready'); fs.appendFileSync('events', 'pre\\n');\n")
    runner = repo.write("node_modules/.bin/vitest", f"#!{Path(NODE).as_posix()}\n"
        "const fs = require('node:fs'); const assert = require('node:assert/strict');\n"
        "assert.equal(fs.readFileSync('fixture', 'utf8'), 'ready');\n"
        "assert.equal(process.env.npm_lifecycle_event, 'test');\n"
        "fs.writeFileSync('observed.json', JSON.stringify(process.argv.slice(2)));\n"
        "fs.appendFileSync('events', 'test\\n');\n")
    runner.chmod(0o755)
    if sys.platform == "win32":
        repo.write("node_modules/.bin/vitest.cmd", f'@"{Path(NODE).as_posix()}" "%~dp0vitest" %*\n')
    repo.write("finish.cjs", "const fs = require('node:fs');\n"
               "fs.appendFileSync('events', 'post\\n'); fs.unlinkSync('fixture');\n")
    repo.write("package.json", json.dumps({"scripts": {
        "pretest": "node prepare.cjs", "test": "vitest run --maxWorkers=8",
        "posttest": "node finish.cjs"}}))
    config = (repo.path / "forge.toml").read_text("utf-8")
    repo.write("forge.toml", re.sub(r'^test = .*$', 'test = "npm test"', config, flags=re.M))
    # Keep a client's existing Node preload active alongside Forge's budget hook.
    repo.write("client-preload.cjs", "process.env.CLIENT_PRELOAD = 'kept';\n")
    monkeypatch.setenv("NODE_OPTIONS", "--require " + json.dumps(
        (repo.path / "client-preload.cjs").as_posix()))
    with (repo.path / "node_modules/.bin/vitest").open("a", encoding="utf-8") as stream:
        stream.write("assert.equal(process.env.CLIENT_PRELOAD, 'kept');\n")
    ran = repo.forge("test")
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert (repo.path / "events").read_text("utf-8").splitlines() == ["pre", "test", "post"]
    assert not (repo.path / "fixture").exists()
    assert json.loads((repo.path / "observed.json").read_text("utf-8")) == ["run", "--maxWorkers=2"]
