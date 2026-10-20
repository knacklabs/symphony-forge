"""Sign-off compares answer content and identifies the first different line."""
import shutil

import pytest

from conftest import ROOT
from test_proto_signoff import _client, _decision

STORY = "FIX-SIGNOFF-WHITESPACE"


def _signoff(repo, gh, tmp_path, monkeypatch, history):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    if history == "adopted":
        current_config = (fix / "forge.toml").read_text("utf-8")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", fix,
                        dirs_exist_ok=True)
        assert 'version = "v1.2.2"' in (fix / "forge.toml").read_text("utf-8")
        (fix / "forge.toml").write_text(current_config, "utf-8")
        (fix / "docs/product/BRIEF.md").write_text("# Brief\n\n" + answers, "utf-8")
    synced = repo.forge("sync", cwd=fix)
    assert synced.returncode == 0, synced.stderr
    return repo, fix, answers, queue


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
            ("# Brief\r\n\r\n" + answers.replace("\n", " \t\r\n") + "\r\n\r\n").encode())
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


@pytest.mark.parametrize("history, change, line", [
    ("new", "changed", 3), ("new", "removed", 8), ("new", "added", 9),
    ("new", "indent", 3), ("new", "internal blank", 3),
    ("adopted", "changed", 3),
])
def test_2_signoff_refusal_names_the_first_different_answer_line(
        repo, gh, tmp_path, monkeypatch, history, change, line):
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
    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert refused.returncode == 1
    assert f"first differ at line {line} of the Answers section" in refused.stderr
    assert "docs/product/BRIEF.md" in refused.stderr
    assert "copy its Answers section" in refused.stderr
    assert "status: proposed" in page.read_text("utf-8")
    assert not queue.with_suffix(".calls.jsonl").exists()
