"""Sign-off saves the current Answers section and ignores quote formatting.

Test audit:
1. Protect the sign-off record's Answers quote against stale substantive content.
2. A changed, removed, added, indented or blank answer could remain in the saved record.
3. The sample-data brief test covers a generic stale quote; this strict-path command test covers
   substantive content differences and the earlier-adopted path. Test 1 owns whitespace only.
4. The test runs Forge's decision command and uses no production seam.
"""
import shutil

import pytest

from conftest import ROOT
from test_proto_signoff import _client, _decision

STORY = "FIX-SIGNOFF-WHITESPACE"


def _signoff(repo, gh, tmp_path, monkeypatch, history):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    if history == "adopted":
        current_config = (fix / "forge.toml").read_text("utf-8")
        current_brief = (fix / "docs/product/BRIEF.md").read_text("utf-8")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", fix,
                        dirs_exist_ok=True)
        assert 'version = "v1.2.2"' in (fix / "forge.toml").read_text("utf-8")
        (fix / "forge.toml").write_text(current_config, "utf-8")
        (fix / "docs/product/BRIEF.md").write_text(current_brief, "utf-8")
    synced = repo.forge("sync", cwd=fix)
    assert synced.returncode == 0, synced.stderr
    repo.git("add", "-A", cwd=fix)
    if repo.git("diff", "--cached", "--name-only", cwd=fix):
        repo.git("commit", "-qm", "Commit the sign-off records and synced files", cwd=fix)
    return repo, fix, answers, queue


@pytest.mark.platform
@pytest.mark.parametrize("history, style", [
    ("new", "blank line"), ("new", "mixed whitespace"),
    ("new", "brief whitespace"), ("new", "no final newline"),
    ("adopted", "mixed whitespace"),
])
def test_1_signoff_ignores_trailing_whitespace_and_line_endings(
        repo, gh, tmp_path, monkeypatch, history, style):
    repo, fix, answers, queue = _signoff(repo, gh, tmp_path, monkeypatch, history)
    # Previously the quote had to match bytes, including its final blank line.
    quote = answers
    if style == "blank line":
        quote += "\n"
    elif style == "mixed whitespace":
        quote = "\r\n".join(line + " \t" for line in answers.splitlines()) + "\r\n \t\r\n\r\n"
    elif style == "brief whitespace":
        (fix / "docs/product/BRIEF.md").write_bytes(
            ((fix / "docs/product/BRIEF.md").read_text("utf-8").split("## Answers", 1)[0] +
             answers.replace("\n", " \t\r\n") + "\r\n\r\n").encode())
        repo.git("add", "docs/product/BRIEF.md", cwd=fix)
        repo.git("commit", "-qm", "Format the source answers", cwd=fix)
    else:
        quote = answers.rstrip("\n")
    page = _decision(fix, answers)
    prefix = page.read_text("utf-8").split("## Answers", 1)[0]
    page.write_bytes((prefix + quote).encode())
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stderr
    assert "status: accepted" in page.read_text("utf-8")
    assert len(queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()) == 1


@pytest.mark.parametrize("history, change", [
    ("new", "changed"), ("new", "removed"), ("new", "added"),
    ("new", "indent"), ("new", "internal blank"),
    ("adopted", "changed"),
])
def test_2_signoff_replaces_stale_answers_with_the_brief(
        repo, gh, tmp_path, monkeypatch, history, change):
    repo, fix, answers, queue = _signoff(repo, gh, tmp_path, monkeypatch, history)
    lines = answers.splitlines()
    if change == "changed":
        lines[2] = lines[2].replace("agreed", "different")
        lines[3] = lines[3].replace("agreed", "also different")
    elif change == "removed":
        lines.pop()
    elif change == "added":
        lines.append("- Extra topic: agreed (client, 2026-09-28)")
    elif change == "indent":
        lines[2] = " " + lines[2]
    else:
        lines.insert(2, "")
    page = _decision(fix, answers, quote="\n".join(lines) + "\n\n")
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    saved = page.read_text("utf-8")
    assert "status: accepted" in saved
    saved_answers = saved.split("## Answers\n", 1)[1].rstrip()
    brief_answers = answers.split("## Answers\n", 1)[1].rstrip()
    assert saved_answers == brief_answers
    assert len(queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()) == 1
