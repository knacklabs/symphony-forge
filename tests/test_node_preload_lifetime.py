"""Node replacement processes keep their preload after an installation changes."""
import json
import re
import shutil

import pytest

from conftest import ROOT
from test_node_test_worker_budget import NODE, client

STORY = "FIX-PLAYWRIGHT-WORKERS-FIND-PRELOAD"


@pytest.mark.platform
@pytest.mark.parametrize("upgrade", [False, True], ids=["new", "earlier-adopted"])
@pytest.mark.parametrize("arguments", [(), ("--change",)])
def test_1_remaining_workers_run_after_failure_and_install_removal(repo, gh, upgrade, arguments):
    # Audit: protects inherited preloads across a real Node process replacement.
    # Existing budget tests never remove the installation during the command.
    # A copied installation isolates removal without adding a production seam.
    assert NODE, "The preload lifetime contract requires Node.js"
    client(repo, gh, upgrade)
    installed = repo.path.parent / "installed Forge"
    shutil.copytree(ROOT / "src/forge", installed / "forge")
    launcher = repo.bin / "forge"
    launcher.write_text(launcher.read_text("utf-8").replace(
        repr(str(ROOT / "src")), repr(str(installed))), "utf-8")
    original = installed / "forge/node_workers.cjs"
    repo.write("first.cjs", "const fs = require('node:fs');\n"
               f"fs.unlinkSync({json.dumps(original.as_posix())});\n"
               "fs.appendFileSync('events', 'first failed\\n'); process.exit(1);\n")
    repo.write("remaining.cjs", "require('node:fs').appendFileSync('events', 'remaining ran\\n');\n")
    repo.write("run.cjs", "const {spawnSync} = require('node:child_process');\n"
               "const first = spawnSync(process.execPath, ['first.cjs'], {stdio: 'inherit'});\n"
               "const remaining = spawnSync(process.execPath, ['remaining.cjs'], {stdio: 'inherit'});\n"
               "process.exit(first.status === 1 && remaining.status === 0 ? 1 : 2);\n")
    config = (repo.path / "forge.toml").read_text("utf-8")
    repo.write("forge.toml", re.sub(r'^test = .*$', 'test = "node run.cjs"', config, flags=re.M))
    ran = repo.forge("test", *arguments)
    assert (repo.path / "events").read_text("utf-8").splitlines() == [
        "first failed", "remaining ran"], ran.stdout + ran.stderr
    assert ran.returncode == 1, ran.stdout + ran.stderr
