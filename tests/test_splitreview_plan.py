"""src/forge/plan_scope.py keeps task files apart before readers or approval."""
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_setup import _fresh_client
from test_worker_brief_answers_common_questions import brief  # noqa: F401
from test_workers_leave_settings_to_coordinator import client  # noqa: F401

from test_story import DOC, claude_plan, hook, new_story, setup, worktree

STORY = "FORGE-SPLITREVIEW-1"
pytestmark = pytest.mark.platform

# Gate: command admission; missing scope validation admits shared files.
# Existing shape tests miss that rule. No test-only production seam is needed.
@pytest.mark.parametrize("first,second,after,blocked", [
    ("src/basket.py", "src/basket.py", "none", True),
    ("src/", "src/page.py", "none", True),
    ("src/*.py", "src/page.py", "none", True),
    ("**/*.py", "src/page.py", "none", True),
    ("src/basket.py", "src/", "none", True),
    ("src/basket.py", "src/basket.py", "SAVE", False),
    ("src/basket.py", "src/basket.py", "SHOP/SAVE", False),
    ("src/basket.py", "src/basket.py", "MIDDLE", False),
    ("src/basket.py", "src/basket.py", "reverse", False),
    ("src/basket.py", "src/basket_extra.py", "none", False),
])
def test_2_plan_refuses_unordered_shared_files(repo, first, second, after, blocked):
    setup(repo)
    top = new_story(repo, "SHOP")
    text = DOC.replace("`src/basket.py`", f"`{first}`").replace(
        "`src/page.py`", f"`{second}`").replace("| SAVE | yes |", f"| {after} | yes |")
    if after == "MIDDLE":
        text = text.replace("New moving parts:",
                            "| MIDDLE | Middle | Shared names | 1 | `other.py` | none | SAVE | no |\n\n"
                            "New moving parts:")
    elif after == "reverse":
        text = text.replace("| none | no |", "| SHOW | no |").replace(
            "| reverse | yes |", "| none | yes |")
    (top / "plans/SHOP.md").write_text(text, encoding="utf-8")
    read = repo.forge("read", "SHOP")
    if blocked:
        assert read.returncode == 1, read.stdout + read.stderr
        assert "SAVE and SHOW" in read.stderr
        assert "Next:" in read.stderr and "After" in read.stderr
        assert not (top / "plans/SHOP.read.md").exists()
        assert not (repo.bin / "claude-calls.jsonl").exists()
    else:
        assert read.returncode == 0, read.stdout + read.stderr
        assert "found nothing" in read.stdout


@pytest.mark.parametrize("previous", [False, True], ids=["init", "earlier-adoption"])
def test_3_in_flight_plans_are_checked_again_before_approval(
        repo, gh, tmp_path, claude_payload, previous):
    if previous:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    else:
        folder, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = folder
    repo.git("config", "core.hooksPath", str(tmp_path / "fixture-no-hooks"))
    setup(repo, kind="client")
    if previous:
        upgrade = repo.forge("fix", "start", "Upgrade the client guides", "--done",
                             "The client uses current Forge guidance", "--slug", "upgrade-guides",
                             "--kind", "mechanical")
        assert upgrade.returncode == 0, upgrade.stdout + upgrade.stderr
        upgrade_top = worktree(repo, "fix/upgrade-guides")
        synced = repo.forge("sync", cwd=upgrade_top)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        repo.git("add", "-A", cwd=upgrade_top)
        repo.git("commit", "-qm", "Upgrade the client guides", cwd=upgrade_top)
        repo.git("merge", "-q", "--ff-only", "fix/upgrade-guides")
        # Seed the third-party merge without asking a client hook to push main.
        remote = Path(repo.git("remote", "get-url", "origin"))
        repo.git("fetch", "-q", str(repo.path), "main:main", cwd=remote)
        repo.git("fetch", "-q", "origin")
    for host in (".codex", ".claude"):
        guide = (repo.path / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert "before writing each task's Scope, search the code" in " ".join(guide.split())
    top = new_story(repo, "SHOP")
    doc = top / "plans/SHOP.md"
    initial = DOC.replace("## Tasks", "## For the builders\n\n## Tasks")
    doc.write_text(initial, encoding="utf-8")
    assert repo.forge("read", "SHOP").returncode == 0
    # Builder-only edits keep a passing read, but must still check scopes.
    text = initial.replace("`src/page.py`", "`src/basket.py`").replace(
        "| SAVE | yes |", "| none | yes |")
    doc.write_text(text, encoding="utf-8")
    refused = hook(repo, claude_plan(claude_payload, text))
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "SAVE and SHOW" in refused.stderr
    assert "After" in refused.stderr and "Next:" in refused.stderr
    doc.write_text(initial, encoding="utf-8")
    accepted = hook(repo, claude_plan(claude_payload, initial))
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    # Approved stories keep their contract at read and task start after builder edits.
    doc.write_text(text, encoding="utf-8")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 1 and "so it needs no new round" in read.stderr, read.stdout + read.stderr
    repo.git("add", "plans/SHOP.md", cwd=top)
    repo.git("commit", "-qm", "Adjust the approved builder scopes", cwd=top)
    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stdout + started.stderr


@pytest.mark.parametrize("client,brief", [
    pytest.param(False, False, id="new-client-fresh"),
    pytest.param(False, True, id="new-client-resumed"),
    pytest.param(True, True, id="earlier-adoption-resumed"),
], indirect=True)
def test_4_workers_keep_other_open_tasks_files_untouched(brief):
    # Prompt delivery is the contract: a resumed session can retain the older
    # outside-Scope permission. The real work command must send the new rule.
    # Existing resume coverage checks other instructions; no new seam is needed.
    assert ("Do not change a file that another open task's Scope owns. "
            "Leave it and name it in your handback.") in " ".join(brief.split())
    assert ("This restriction excludes paths with a segment named tests, test, __tests__ or spec. "
            "These test paths can be shared.") in " ".join(brief.split())
