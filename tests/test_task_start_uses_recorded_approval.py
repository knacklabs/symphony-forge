"""Task start accepts the same plan text as Plan Mode approval."""
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client
from test_story import DOC, claude_plan, hook, ready, setup

STORY = "FIX-TASK-START-AND-WORKER-ROUNDS-REFUSE-AN-A"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_1_approved_story_starts_its_part(repo, gh, tmp_path, claude_payload, adopted):
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier release")
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
    repo.git("config", "core.hooksPath", str(tmp_path / "fixture-hooks"))
    repo.write("docs/decisions/0001-client-signoff.md", "---\nstatus: accepted\n---\n")
    setup(repo, kind="client")
    # Like a real plan that quotes text for builders, this repeats an approved
    # heading below the owner-facing section and includes an indented numbered list.
    doc = DOC + """
The task review quotes these instructions:

```
## What changes for you
The owner approved these items:
  1. Save the basket.
  2. Show the saved time.
```
"""
    ready(repo, "SHOP", doc)
    recorded = hook(repo, claude_plan(claude_payload, doc))
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    assert "Recorded the approval of" in recorded.stdout

    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stdout + started.stderr
    assert "Started SHOP/SAVE on task/SHOP-SAVE" in started.stdout
