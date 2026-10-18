"""Forge caps arguments delivered to Node runners at their process boundary."""
import json
import re
import shutil
import sys

import pytest

from conftest import ROOT, _install, machine_cores

STORY = "FIX-NODE-TEST-BUDGET"


@pytest.mark.parametrize("setting,command,script,expected", [
    (setting, prefix + runner + options, None, expected)
    for setting in ("test", "fast_test")
    for runner in ("vitest", "jest")
    for prefix in ("", "npx ")
    for options, expected in ((" run", ["run", "--maxWorkers=2"]),
                              (" --maxWorkers=1", ["--maxWorkers=1"]),
                              (" --maxWorkers 8", ["--maxWorkers", "2"]))
] + [
    ("fast_test", manager + " run check", runner + " run", ["run", "--maxWorkers=2"])
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
])
def test_1_node_runners_obey_the_machine_budget(repo, gh, monkeypatch, setting, command, script, expected):
    # These third-party executables only record arguments. Forge must choose the cap.
    recorder = '''import json, pathlib, sys
pathlib.Path('observed.json').write_text(json.dumps(sys.argv[1:]), encoding='utf-8')
'''
    for runner in ("vitest", "jest", "other"):
        _install(repo.bin, runner, f"#!{sys.executable}\n" + recorder)
    dispatcher = '''import json, os, pathlib, shlex, subprocess, sys
args = sys.argv[1:]
if pathlib.Path(sys.argv[0]).stem != 'npx':
    name = args.pop(0)
    if name == 'run': name = args.pop(0)
    if args[:1] == ['--']: args.pop(0)
    command = json.loads(pathlib.Path('package.json').read_text('utf-8'))['scripts'][name]
else:
    command = args.pop(0)
command += ' ' + (subprocess.list2cmdline(args) if os.name == 'nt' else shlex.join(args))
raise SystemExit(subprocess.call(command, shell=True))
'''
    for manager in ("npm", "pnpm", "yarn", "npx"):
        _install(repo.bin, manager, f"#!{sys.executable}\n" + dispatcher)
    machine_cores(repo, 8)
    monkeypatch.setenv("FORGE_TEST_CPUS", "2")
    if setting == "upgrade":
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
        setting = "test"
    else:
        repo.git("checkout", "--orphan", "fresh")
        gh.respond("api", stderr="Branch not protected", exit=1)
        gh.respond("api", "--method", "PUT", stdout="{}")
        initialized = repo.forge("init")
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
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
