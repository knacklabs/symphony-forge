"""Sign-off reuses full-run proof only for Forge output and records.

Test audit: protect command admission after a main repair and on the reviewed
branch. Rejecting all stale results or ignoring default-branch app changes breaks these cases.
Existing sign-off tests supply green proof only on latest main, so cannot catch
this gap. Reuse their client fixtures and fake only GitHub and Autoreview, with
no production seam. Earlier clients start from the text adoption fixture.
"""
import json
from pathlib import Path

import pytest

from conftest import StubGh
from test_proto_signoff import _adopted_client, _client, _decision, _request_build

STORY = "FIX-EACH-MERGED-REPAIR-MAKES-THE-LAST-GREEN"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-release"])
@pytest.mark.parametrize("change", ["record", "sync", "app-main", "app-branch", "failed"])
def test_1_signoff_reuses_green_only_for_forge_changes(repo, tmp_path, monkeypatch, adopted, change):
    make = _adopted_client if adopted else _client
    fix, answers, queue = make(repo, tmp_path, monkeypatch)
    green = repo.git("rev-parse", "origin/main")
    if adopted:
        _request_build(repo, fix)
    if change == "sync":
        synced = repo.forge("sync", cwd=fix)
        assert synced.returncode == 0, synced.stderr
    else:
        repo.write("plans/repair.md", "# Repair record\n")
    if change == "app-main":
        repo.write("app.py", "print('changed app')\n")
    work = fix if change == "sync" else repo.path
    repo.git("add", "-A", cwd=work)
    repo.git("commit", "-q", "-m", "Record repair", cwd=work)
    if change == "sync":
        branch = repo.git("branch", "--show-current", cwd=fix)
        repo.git("merge", "--ff-only", branch)
    # A GitHub merge updates the bare remote without the client's push hook.
    remote = Path(repo.git("remote", "get-url", "origin"))
    repo.git("fetch", "-q", str(repo.path), "main:main", cwd=remote)
    latest = repo.git("rev-parse", "HEAD")
    for sha in repo.git("rev-list", f"{green}..HEAD").splitlines():
        StubGh(repo.bin).respond(
            "api", f"repos/{{owner}}/{{repo}}/commits/{sha}/statuses",
            stdout=json.dumps([{"context": "forge-full-suite",
                                "state": "failure" if change == "failed" else "success"}]
                              if change in {"failed", "app-branch"} and sha == latest else []))
    repo.git("merge", "--no-edit", "main", cwd=fix)
    if change == "app-branch":
        (fix / "app.py").write_text("print('unverified app')\n", encoding="utf-8")
        repo.git("add", "app.py", cwd=fix)
        repo.git("commit", "-q", "-m", "Change app", cwd=fix)
    page = _decision(fix, answers)

    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    # The amended contract checks main's changes, so an unmerged app repair
    # must reach review. Main app changes and a failed latest run still refuse.
    if change in {"record", "sync", "app-branch"}:
        assert accepted.returncode == 0, accepted.stdout + accepted.stderr
        assert "status: accepted" in page.read_text("utf-8")
    else:
        assert accepted.returncode == 1, accepted.stdout + accepted.stderr
        assert "full test run" in accepted.stderr
        assert "status: proposed" in page.read_text("utf-8")
        assert not queue.with_suffix(".calls.jsonl").exists()
