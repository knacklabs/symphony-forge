"""Doctor shows Codex speed only when the repo uses Codex."""
import re
import shutil

import pytest

from conftest import ROOT, patient
from test_setup import _fresh_client

STORY = "FIX-DOCTOR-CODEX-SPEED"


@pytest.mark.parametrize("history, workers", [
    ("new", "claude"), ("new", "codex"), ("new", "split"),
    ("adopted-v1.2.2", "claude"),
])
def test_1_doctor_shows_codex_fast_only_when_repo_uses_codex(repo, gh, tmp_path,
                                                          history, workers):
    if history == "new":
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    else:
        client = repo.path
        patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client",
                                       client, dirs_exist_ok=True))
    settings = client / "forge.toml"
    text = settings.read_text("utf-8")
    text = re.sub(r'^workers = ".*"$', f'workers = "{workers}"', text, flags=re.M)
    settings.write_text('codex_fast = "needed"\n' + text, encoding="utf-8")

    checked = repo.forge("doctor", cwd=client)

    # Other setup warnings must not prevent doctor from reaching its machine report.
    assert "Test processes in use:" in checked.stdout, checked.stdout + checked.stderr
    lines = [line for line in checked.stdout.splitlines() if line.startswith("- Codex Fast:")]
    assert len(lines) == (0 if workers == "claude" else 1), checked.stdout + checked.stderr
