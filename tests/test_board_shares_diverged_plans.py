"""Machine views reconcile a shared plan once instead of once per part."""
import json

import pytest

from test_machine_views_recent_finished_items import NOW, client
from test_story import DOC

STORY = "the-pane-s-refresh-runs-forge-next-and-f"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("command", ["board", "next"])
def test_1_machine_views_share_plan_reads(repo, gh, monkeypatch, tmp_path, history, command):
    # Contract: a board-sized story does not repeat expensive Git reconciliation
    # for every child. Real Git supplies both the merge and the work measurement.
    # Earlier scaling tests use fixes or identical plans, so miss this case.
    # No production test seam is needed, and GitHub is the only fake service.
    client(repo, gh, history)
    monkeypatch.setenv("FORGE_NOW", NOW)
    repo.git("switch", "-qc", "story/SHARED")
    rows = "\n".join(
        f"| PART-{n} | Part {n} | Save work | 1 | `src/part-{n}.py` | "
        f"`tests/test_part_{n}.py` | none | no |" for n in range(12))
    doc = DOC.replace("New moving parts: none", rows + "\n\nNew moving parts: none")
    repo.write("plans/SHARED.md", doc)
    repo.write(".factory/stories/SHARED/story.json", json.dumps({
        "status": "approved", "title": "Shared plan", "branch": "story/SHARED"}))
    for name in ["SAVE", "SHOW", *(f"PART-{n}" for n in range(12))]:
        repo.write(f".factory/stories/SHARED/tasks/{name}.json", json.dumps({
            "status": "started", "branch": f"task/SHARED-{name}"}))
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Record the shared plan")
    repo.git("push", "-q", "origin", "story/SHARED")
    # Published and local edits affect different lines and need a real merge.
    repo.write("plans/SHARED.md", doc.replace("## Why", "## Why\n\nPublished reason."))
    repo.git("commit", "-qam", "Add the published reason")
    repo.git("push", "-q", "origin", "story/SHARED")
    repo.git("switch", "-qc", "fix/view-plan", "HEAD~1")
    repo.git("branch", "-f", "story/SHARED", "HEAD")
    worktree = tmp_path / "shared-plan"
    repo.git("worktree", "add", str(worktree), "story/SHARED")
    (worktree / "plans/SHARED.md").write_text(doc + "\nLocal note.\n", encoding="utf-8")
    trace = tmp_path / "git.jsonl"
    monkeypatch.setenv("GIT_TRACE2_EVENT", trace.as_posix())
    result = repo.forge(command, "--json")
    assert result.returncode == 0, result.stderr
    view = json.loads(result.stdout)
    shared = next(row for row in view["items"] if row["id"] == "SHARED")
    assert len(shared["children"]) == 14
    assert shared["title"] == "Shared plan"
    calls = [json.loads(line) for line in trace.read_text("utf-8").splitlines()]
    merges = [row["argv"] for row in calls if row.get("event") == "start"
              and "merge-file" in row.get("argv", [])]
    assert len(merges) <= 2, f"Shared plan reconciled {len(merges)} times"
    # A new invocation must see edits; the optimization cannot cache across reads.
    (worktree / "plans/SHARED.md").write_text(
        doc.replace("| Part 11 |", "| Revised part |") + "\nLocal note.\n", encoding="utf-8")
    refreshed = repo.forge(command, "--json")
    assert refreshed.returncode == 0, refreshed.stderr
    shared = next(row for row in json.loads(refreshed.stdout)["items"] if row["id"] == "SHARED")
    assert next(child for child in shared["children"] if child["id"] == "SHARED/PART-11")["title"] == "Revised part"
