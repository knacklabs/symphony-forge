"""The generated required check uses a Bash-safe result variable."""
import re
import shutil

import pytest

from test_fix_gate_on_split_checks import ROOT, bash, jobs
from test_setup import _fresh_client

STORY = "FIX-WORKFLOW-GROUPS-RENAME"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("kind", ["new", "previous"])
def test_1_init_and_sync_keep_the_required_tests_result(repo, gh, tmp_path, kind):
    if kind == "new":
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stderr
    else:
        client = tmp_path / "previous-client"
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", client)
        repo.git("init", "-q", "-b", "main", str(client))
        repo.git("add", "-A", cwd=client)
        repo.git("commit", "-q", "-m", "Previously adopted client", cwd=client)
        repo.git("switch", "-q", "-c", "fix/result-variable", cwd=client)
        settings = client / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        settings.write_text(settings.read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{version}"'), encoding="utf-8")
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stderr

    gate = jobs((client / ".github/workflows/forge.yml").read_text("utf-8"))["tests-passed"]
    # Use the environment key GitHub supplies, rather than choosing one in the test.
    variable = re.search(r"^          (\w+): \$\{\{ needs.tests.result \}\}$", gate, re.M)[1]
    assert variable == "TEST_GROUP_RESULT"
    command = re.search(r"run: (.+)$", gate, re.M)[1]
    for docs_check, result, docs_only, expected in [
        ("success", "success", "false", True),
        ("success", "failure", "false", False),
        ("success", "cancelled", "false", False),
        ("success", "skipped", "false", False),
        ("success", "skipped", "true", True),
        ("failure", "success", "false", False),
        ("failure", "skipped", "true", False),
    ]:
        checked = bash("-e", "-c", command, env={variable: result,
                       "DOCS_CHECK": docs_check, "DOCS_ONLY": docs_only})
        assert (checked.returncode == 0) == expected
