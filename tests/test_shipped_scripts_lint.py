"""Shipped browser tools must coexist with a client's whole-tree JavaScript lint."""
import json
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, FORGE_SHIM, _install
from test_setup import _fresh_client, _version

STORY = "skill-scripts-pass-client-lint"


# Test-audit: protects lint and executable syntax after real init/sync. Shipping
# unannotated vendor scripts regresses it; delivery inventories never run ESLint.
# Uses the public commands and real ESLint, with no new production seam.
@pytest.mark.platform
@pytest.mark.parametrize("case", ["typescript", "python", "previous release"])
def test_1_shipped_skill_scripts_allow_whole_tree_lint(repo, gh, tmp_path, case):
    if case != "previous release":
        args = ("--starter", "python") if case == "python" else ("--starter",)
        client, made = _fresh_client(repo, gh, tmp_path, *args)
    else:
        old = tmp_path / "previous-release"
        shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
        (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
        _install(repo.bin, "old-forge", FORGE_SHIM.format(python=sys.executable, src=str(old / "src")))
        gh.respond("api", stdout="{}")
        made = subprocess.run(
            [sys.executable, str(repo.bin / "old-forge"), "init", "--test", "echo ok",
             "--checks", "tests", "--interfaces", "api/routes/**", "--approver", "Owner",
             "--merger", "Owner"], cwd=repo.path, capture_output=True, text=True)
        client = repo.path.parent / "repo-fix-adopt-forge"
    assert made.returncode == 0, made.stdout + made.stderr
    # A client-owned whole-tree config: no ignores for either host's skills.
    config = client / "eslint.config.mjs"
    config.write_text("export default [{rules: {'no-undef': 'error', "
                      "'no-unused-vars': 'error', 'no-empty': 'error'}}];\n", encoding="utf-8")
    if case == "previous release":
        pin = client / "forge.toml"
        pin.write_text(pin.read_text(encoding="utf-8").replace(
            'version = "v1.2.2"', f'version = "{_version(repo)}"'), encoding="utf-8")
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        assert config.read_text(encoding="utf-8").startswith("export default [{rules:")
    npm = shutil.which("npm")
    assert npm, "Node and npm are required to check the shipped JavaScript"
    lint = subprocess.run([npm, "exec", "--yes", "--package=eslint@9.39.1", "--",
                           "eslint", ".", "--format", "json"], cwd=client,
                          capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert lint.returncode in (0, 1), lint.stdout + lint.stderr
    reports = json.loads(lint.stdout)
    scripts = [report for report in reports if "/skills/impeccable/scripts/" in
               report["filePath"].replace("\\", "/")]
    assert len(scripts) == 10, lint.stdout
    # Security validators also ship into both hosts. Whole-tree lint must cover
    # them; running their CLI on invalid input proves they still execute.
    validators = [report for report in reports if "/skills/security-audit/" in
                  report["filePath"].replace("\\", "/")]
    assert len(validators) == 4, lint.stdout
    assert not any(report["messages"] for report in validators), validators
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{}\n", encoding="utf-8")
    for report in validators:
        checked = subprocess.run([shutil.which("node"), report["filePath"], str(invalid)],
                                 capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert checked.returncode == 1, checked.stdout + checked.stderr
        assert "Error" not in checked.stderr, checked.stderr
    assert not any(report["messages"] for report in scripts), scripts
    # Load every delivered script with the actual JS runtime. The live overlay
    # has a supported no-window exit; the helpers and screenshot bundle load.
    for report in scripts:
        checked = subprocess.run([shutil.which("node"), "-e",
                                 "require('node:vm').runInNewContext("
                                 "require('node:fs').readFileSync(process.argv[1], 'utf8'), {});",
                                 report["filePath"]],
                                 capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert checked.returncode == 0, checked.stdout + checked.stderr
