"""Printed recovery commands omit needless quotes and retain shell protection.

Test-audit: the release hook owns the observable next command. Always quoting
on Windows breaks its plain-filename contract; removing all quotes breaks names
with spaces or shell operators. Existing tests exercise only the host platform.
The launcher selects the quote function's OS without changing its logic or adding
a production seam. Only GitHub is faked at the external boundary.
"""
import json
import shutil

import pytest

from conftest import ROOT, _install
from test_testplace_fullrun import _set_status

STORY = "on-windows-the-printed-next-step-puts-do"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("platform,workflow,expected,adopted", [
    ("posix", "nightly.yml", "nightly.yml", False),
    ("nt", "nightly.yml", "nightly.yml", False),
    ("posix", "nightly & tests.yml", "'nightly & tests.yml'", False),
    ("nt", "nightly & tests.yml", '"nightly & tests.yml"', False),
    ("nt", "nightly.yml", "nightly.yml", True),
])
def test_1_nightly_next_command_quotes_only_when_needed(repo, gh, platform, workflow, expected, adopted):
    version = repo.forge("--version").stdout.split()[-1]
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Earlier adopted client")
    repo.write("forge.toml", f'version = "{version}"\nchecks = ["tests", "forge-pr-check"]\n'
               f'full_suite_workflow = {json.dumps(workflow)}\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Configure nightly tests")
    repo.git("push", "-q", "origin", "main")
    shim = (repo.bin / "forge").read_text("utf-8")
    override = (
        "from forge import repo\nfrom types import FunctionType, SimpleNamespace\n"
        "repo.quote = FunctionType(repo.quote.__code__, "
        f"dict(repo.quote.__globals__, os=SimpleNamespace(name={platform!r})))\n"
    )
    _install(repo.bin, "forge", shim.replace("from forge.cli import main", override + "from forge.cli import main"))
    sha = repo.git("rev-parse", "origin/main")
    _set_status(gh, sha, None)
    refused = repo.forge("hook", "pre-push", input=f"refs/tags/v1.0.0 {sha} refs/tags/v1.0.0 {'0' * 40}\n")
    assert refused.returncode != 0
    assert f"gh workflow run {expected} --ref main" in refused.stderr
