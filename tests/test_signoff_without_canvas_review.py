"""Command regression: extra canvas calls and reopening accepted old records.

Audit: existing tests demand the obsolete check. These cases protect its removal
at the command boundary, faking only external tools and adding no production seam.
"""
import pytest
from test_proto_signoff import _adopted_client, _client, _decision
from test_signoff_design import _calls

STORY = "the-canvas-completeness-check-is-a-separ"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("working", [False, True])
def test_1_signoff_uses_only_product_review(repo, tmp_path, monkeypatch, working):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch, working_build=working)
    page = _decision(fix, answers)
    result = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: accepted" in page.read_text("utf-8")
    assert len(_calls(queue)) == int(working)


def test_2_old_accepted_signoff_ignores_canvas_results(repo, tmp_path, monkeypatch):
    fix, _, queue = _adopted_client(repo, tmp_path, monkeypatch, old_signoff=True)
    page = fix / "docs/decisions/0001-client-signoff.md"
    old = page.read_text("utf-8").replace("status: accepted", "status: accepted\ndesign_checked: old")
    page.write_text(old, encoding="utf-8")
    (fix / ".factory/client-signoff.json").write_text('{"canvas": {"stop": true}}', encoding="utf-8")
    result = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "already accepted" in result.stdout
    assert page.read_text("utf-8") == old
    assert not _calls(queue)
