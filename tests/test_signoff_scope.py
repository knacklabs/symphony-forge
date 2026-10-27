"""Canvas scope and client choices at the real sign-off command.

Test audit: protect demo-address timing, screen scope and unresolved client choices.
Regressions can treat a build request as code, omit marks, or review before refusing choices.
Existing sign-off tests do not cover these contracts. Reuse their client fixtures and replace
only the external review tool. No production test seam is needed.
"""
from __future__ import annotations

import pytest

from test_open_decisions import _question
from test_proto_signoff import _adopted_client, _client, _decision, _request_build
from test_signoff_design import _calls

STORY = "FORGE-SIGNOFF-1"
pytestmark = pytest.mark.platform


def _commit(repo, fix):
    repo.git("add", "docs/design/prototype/SCREENS.md", cwd=fix)
    repo.git("commit", "-qm", "Set screen scope", cwd=fix)


def _preview(fix, answers):
    page = _decision(fix, answers)
    page.write_text(page.read_text("utf-8").replace("approved_via: email\n", "").replace(
        "approved_on: 2026-09-28\n", ""), encoding="utf-8")
    return page


@pytest.mark.parametrize("setup", ["canvas-demo", "working-demo", "new-client", "adopted-v1.2.2"])
def test_4_canvas_first_and_build_marks(repo, tmp_path, monkeypatch, setup):
    if setup.endswith("-demo"):
        repo.write("Dockerfile", "FROM scratch\n")
        working = setup == "working-demo"
        fix, _, _ = _client(repo, tmp_path, monkeypatch, working_build=working)
        if working:
            config = repo.path / "forge.toml"
            config.write_text(config.read_text("utf-8") + '\nstage = "prototype"\n', encoding="utf-8")
            repo.git("add", "forge.toml")
            repo.git("commit", "-qm", "Keep the working demo in prototype stage")
            repo.git("push", "-q", "origin", "main")
        shown = repo.forge("next")
        assert shown.returncode == 0, shown.stdout + shown.stderr
        reminder = "connect the repo on our deploy platform"
        assert (reminder in shown.stdout) == working, shown.stdout
        if not working:
            _request_build(repo, fix)
            repo.git("push", "-q", "origin", "HEAD:main", cwd=fix)
            requested = repo.forge("next", cwd=fix)
            assert requested.returncode == 0, requested.stdout + requested.stderr
            assert reminder not in requested.stdout
        return

    make = _adopted_client if setup == "adopted-v1.2.2" else _client
    options = {} if setup == "adopted-v1.2.2" else {"working_build": False}
    fix, answers, queue = make(repo, tmp_path, monkeypatch, **options)
    screens = fix / "docs/design/prototype/SCREENS.md"
    marked = screens.read_text("utf-8").replace("Build: now\n", "")
    screens.write_text(marked, encoding="utf-8")
    _commit(repo, fix)
    page = _preview(fix, answers)
    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "SCREENS.md: Order list needs Build: now or Build: later" in refused.stderr
    assert not _calls(queue)

    screens.write_text(marked.replace("Image:", "Build: now\nImage:"), encoding="utf-8")
    _commit(repo, fix)
    _decision(fix, answers)
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "status: accepted" in page.read_text("utf-8")
    assert "design_checked:" in page.read_text("utf-8")
    screens.write_text(marked, encoding="utf-8")
    _commit(repo, fix)
    rechecked = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert rechecked.returncode == 0, rechecked.stdout + rechecked.stderr
    assert "needs Build:" not in rechecked.stderr

    synced = repo.forge("sync", cwd=fix)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    for host in (".claude", ".codex"):
        guide = (fix / host / "skills/forge/SKILL.md").read_text("utf-8")
        for text in ("Play mode", "Build: now", "Build: later"):
            assert text in guide


@pytest.mark.parametrize("setup", ["new-client", "adopted-v1.2.2"])
def test_5_signoff_waits_for_blocking_decisions(repo, tmp_path, monkeypatch, setup):
    make = _adopted_client if setup == "adopted-v1.2.2" else _client
    options = {} if setup == "adopted-v1.2.2" else {"working_build": False}
    fix, answers, queue = make(repo, tmp_path, monkeypatch, **options)
    screens = fix / "docs/design/prototype/SCREENS.md"
    text = screens.read_text("utf-8").replace("Build: now\n", "")
    screens.write_text(text.replace("Image:", "Build: now\nImage:") +
                       "\n## Order archive\nBuild: later\nImage: order-list.svg\n"
                       "Fields:\n- order name: text, required\n", encoding="utf-8")
    _commit(repo, fix)
    _preview(fix, answers)
    source = fix / "docs/decisions/open-questions.md"
    question = "Which {order} comes first?"
    full = _question(question)
    source.write_text("# Choices\n\n" + full, encoding="utf-8")

    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "Sign-off waits for 1 open decisions on Build now screens:" in refused.stderr
    assert f"- {question} (docs/decisions/open-questions.md, line 3)" in refused.stderr
    for field in ("Why we ask: It changes the order list.", "Default: Keep the current order.",
                  "Why this default: It matches the current workflow.",
                  "If the default stands: Staff keep the current order."):
        assert field in refused.stderr
    assert 'forge decision answer --from <file> --by "<name>"' in refused.stderr
    assert '--defaults, then forge decision accept client-signoff --by "Ravi"' in refused.stderr
    assert not _calls(queue)
    if setup == "new-client":
        source.write_text("# Choices\n\n" + full.replace(
            "    Why this default: It matches the current workflow.\n", "").replace(
            "    Due: 2026-11-03\n", ""), encoding="utf-8")
        incomplete = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert incomplete.returncode == 1, incomplete.stdout + incomplete.stderr
        assert "Why this default: not written yet" in incomplete.stderr
        assert not _calls(queue)

    source.write_text(full.replace("Touches: Order list", "Touches: Order archive"), encoding="utf-8")
    later = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert later.returncode == 0, later.stdout + later.stderr
    assert "The canvas completeness check passed" in later.stdout

    source.write_text(full, encoding="utf-8")
    answer_file = tmp_path / "answers.md"
    answer_file.write_text(f"- Open question: {question}\n  Answer: Keep the current order.\n", encoding="utf-8")
    answered = repo.forge("decision", "answer", "--from", str(answer_file), "--by", "Ravi", cwd=fix)
    assert answered.returncode == 0, answered.stdout + answered.stderr
    cleared = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert cleared.returncode == 0, cleared.stdout + cleared.stderr
    assert "The canvas completeness check passed" in cleared.stdout

    if setup == "new-client":
        source.write_text(_question("Keep the old sort?", due="2020-01-01"), encoding="utf-8")
        defaults = repo.forge("decision", "answer", "--defaults", cwd=fix)
        assert defaults.returncode == 0, defaults.stdout + defaults.stderr
        cleared = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert cleared.returncode == 0, cleared.stdout + cleared.stderr
        assert "The canvas completeness check passed" in cleared.stdout
