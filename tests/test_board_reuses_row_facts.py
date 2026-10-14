"""Board refreshes share Git facts instead of launching Git for each row."""
import json

import pytest

from test_machine_views_recent_finished_items import client, traced, NOW

STORY = "board-json-under-5s"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_1_board_refresh_shares_facts_between_rows(repo, gh, monkeypatch, tmp_path, history):
    # Trace native Git, not a fake whose answer decides the performance assertion.
    # Previous coverage bounds old, omitted rows; these rows remain on the board.
    client(repo, gh, history)
    repo.git("switch", "-qc", "fix/measure-refresh")
    monkeypatch.setenv("FORGE_NOW", NOW)
    monkeypatch.setenv("GIT_AUTHOR_DATE", NOW)
    monkeypatch.setenv("GIT_COMMITTER_DATE", NOW)
    counts = []
    for size in (4, 40):
        for number in range(size):
            name = f"active-{number}"
            repo.write(f".factory/fixes/{name}.json", json.dumps({
                "kind": "fix", "branch": f"fix/{name}", "status": "working",
                "why": f"Active work {number}", "done_when": "The work is finished.",
                "steps": [{"step": "start", "at": NOW}]}))
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Record active work")
        for number in range(size):
            repo.git("branch", "-f", f"fix/active-{number}", "HEAD")
        view, count = traced(repo, monkeypatch, "board", tmp_path / f"git-{size}.jsonl")
        rows = {row["id"]: row for row in view["items"]}
        for number in range(size):
            row = rows[f"active-{number}"]
            assert row["title"] == f"Active work {number}"
            assert row["stage"] == "working"
            assert row["total_seconds"] == 0
        counts.append(count)
    assert counts[1] - counts[0] <= 40 - 4, counts
    # The batch must retain working-file precedence over committed state.
    changed = repo.path / ".factory/fixes/active-0.json"
    data = json.loads(changed.read_text("utf-8"))
    changed.write_text(json.dumps({**data, "why": "Uncommitted work"}), encoding="utf-8")
    repo.write(".factory/fixes/untracked-work.json", json.dumps({
        **data, "branch": "fix/untracked-work", "why": "Untracked work"}))
    (repo.path / ".factory/fixes/active-1.json").unlink()
    result = repo.forge("board", "--json")
    assert result.returncode == 0, result.stderr
    rows = {row["id"]: row for row in json.loads(result.stdout)["items"]}
    assert rows["active-0"]["title"] == "Uncommitted work"
    assert rows["untracked-work"]["title"] == "Untracked work"
    assert "active-1" not in rows
