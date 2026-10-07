"""The repository's pytest entry owns Claude's native plugin checks too.

The real pinned runtime validates the public artifacts and executes the native
tests. A broken manifest or native assertion fails the ordinary repository run.
"""
import os
import shutil
import subprocess

from conftest import ROOT, patient


def run_native_plugin_checks(tmp_path):
    home = tmp_path / "native-claude-home"
    patient(lambda: home.mkdir())
    environment = os.environ.copy()
    environment.update(HOME=str(home), USERPROFILE=str(home),
                       CLAUDE_CONFIG_DIR=str(home / ".claude"),
                       CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
    environment.pop("CLAUDE_CODE_PLUGIN_DIRS", None)
    npm = shutil.which("npm")
    assert npm, "Node and npm are required for the pinned Claude plugin checks."
    for args in (
        ["validate", "--strict", ".claude-plugin/marketplace.json"],
        ["validate", "--strict", "src/forge/mod"],
        ["test", "src/forge/mod"],
    ):
        checked = subprocess.run(
            [npm, "exec", "--yes", "--package=@anthropic-ai/claude-code@2.1.291", "--",
             "claude", "plugin", *args],
            cwd=ROOT, env=environment, capture_output=True, encoding="utf-8", timeout=120)
        assert checked.returncode == 0, checked.stdout + checked.stderr
