"""Client commands and hooks do not pay for Forge checkout release lookup."""
import shutil

import pytest

from conftest import ROOT

STORY = "lazy-forwarding-imports"


@pytest.mark.parametrize("adopted,words", [
    (False, ["--version"]),
    (False, ["hook", "pre-push"]),
    (True, ["hook", "pre-push"]),
], ids=["new-command", "new-hook", "adopted-v1.2.2-hook"])
@pytest.mark.platform
def test_1_client_startup_skips_release_lookup(repo, monkeypatch, adopted, words):
    if adopted:
        # The current executable also serves clients with an earlier adoption's files.
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    monkeypatch.setenv("PYTHONPROFILEIMPORTTIME", "1")

    ran = repo.forge(*words)

    assert ran.returncode == 0, ran.stdout + ran.stderr
    imported = {line.rsplit("|", 1)[-1].strip() for line in ran.stderr.splitlines()
                if line.startswith("import time:")}
    assert "forge.cli" in imported, ran.stderr
    assert not {"importlib.metadata", "urllib.request"} & imported, ran.stderr
