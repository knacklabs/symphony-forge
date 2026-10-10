"""Due success checks precede planning for new and earlier-adopted clients."""
import json
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_discovery import _client, _ok
from test_measure import DUE, SPEC, _confirm, _fix
from test_setup import _version

STORY = "discovery-due-check-test"


@pytest.mark.parametrize("adoption", ["new", "previous release"])
def test_1_due_success_check_precedes_planning_when_every_roadmap_story_is_done(
        repo, gh, tmp_path, monkeypatch, adoption):
    # Empty means no unfinished stories; keep their roadmap links for check-back.
    monkeypatch.setenv("FORGE_NOW", "2026-10-01T09:00:00+00:00")
    if adoption == "new":
        repo.path = _client(repo, gh, tmp_path)
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        config = (repo.path / "forge.toml").read_text(encoding="utf-8")
        repo.write("forge.toml", config.replace('version = "v1.2.2"',
                                               f'version = "{_version(repo)}"'))
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Upgrade the earlier adoption")
        repo.git("push", "-q", "origin", "main")

    plan = _fix(repo, "Plan invoices by email")
    if adoption == "previous release":
        _ok(repo.forge("sync", cwd=plan))
    (plan / "docs/specs/invoices.md").write_text(SPEC, encoding="utf-8")
    _confirm(repo, plan, "invoices")
    (plan / "plans").mkdir(exist_ok=True)
    (plan / "plans/roadmap.json").write_text(json.dumps({"items": [
        {"key": key, "spec": "docs/specs/invoices.md"} for key in ("INV-1", "INV-2")
    ]}) + "\n", encoding="utf-8")
    for key in ("INV-1", "INV-2"):
        state = plan / f".factory/stories/{key}/story.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"title": key, "status": "done"}) + "\n",
                         encoding="utf-8")
    repo.git("add", "-A", cwd=plan)
    repo.git("commit", "-q", "-m", "Finish the invoice stories", cwd=plan)
    repo.git("merge", "-q", "--ff-only", "fix/plan-invoices-by-email")
    # The remote receives the landed fixture, as GitHub would after merging its PR.
    remote = Path(repo.git("remote", "get-url", "origin"))
    repo.git("fetch", "-q", str(repo.path), "main:main", cwd=remote)
    repo.git("fetch", "-q", "origin")
    repo.git("worktree", "remove", str(plan))

    # Completed entries retain their links: next offers planning rather than discovery.
    # The crossing contract is that the due check precedes those next-step instructions.
    assert _ok(repo.forge("next")).splitlines()[:6] == DUE + [
        "No story or fix is in progress.",
        'Next: forge story new <KEY> "<title>"',
        'Next: forge fix start "<why>" --done "<done when>"']
