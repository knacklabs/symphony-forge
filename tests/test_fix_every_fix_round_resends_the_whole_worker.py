"""A fix round sends only new instructions and changes since the previous turn ended."""
import json

from test_codex_resume import _resuming, _text
from test_codex_worker import _sent, sdk_data  # noqa: F401

STORY = "FIX-EVERY-FIX-ROUND-RESENDS-THE-WHOLE-WORKER"


def test_1_continued_fix_round_is_short_and_fresh_conversation_has_full_brief(
        repo, monkeypatch, sdk_data, gh, claude_session):
    _, calls, _ = _resuming(repo, monkeypatch, sdk_data)
    started = repo.forge("fix", "start", "Show a greeting", "--done", "The page greets visitors")
    assert started.returncode == 0, started.stderr
    fix = repo.path.parent / "repo-fix-show-a-greeting"

    monkeypatch.setenv("STUB_CODEX_COMMIT", "built.py")
    first = repo.forge("work", "show-a-greeting")
    assert first.returncode == 0, first.stdout + first.stderr
    assert "## The fix" in _text(calls) and "## Tests first" in _text(calls)
    monkeypatch.delenv("STUB_CODEX_COMMIT")

    (fix / "coordinator.txt").write_text("Coordinator change\n", encoding="utf-8")
    state_file = fix / ".factory/fixes/show-a-greeting.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["review"] = {"status": "blocked", "findings": [
        {"priority": "P1", "title": "Greeting missing", "body": "Show it on the page.",
         "file": "built.py", "line": 1}]}
    state_file.write_text(json.dumps(state), encoding="utf-8")
    # Committed: a round that ends with changes uncommitted gets a second, commit-nudge turn.
    repo.git("add", "-A", cwd=fix)
    repo.git("commit", "-qm", "Coordinator change", cwd=fix)
    gh.respond("pr", "checks", state["branch"], stdout=json.dumps([
        {"name": "tests", "bucket": "fail", "link": "https://example.test/job/123"}]))
    gh.respond("run", "view", "--job", "123", stdout="FAILED greeting check\n")
    record = repo.path / ".git/forge/threads/fix/show-a-greeting.json"
    saved = json.loads(record.read_text(encoding="utf-8"))
    record.write_text(json.dumps({**saved, "question": "Question: Which greeting?"}), encoding="utf-8")

    continued = repo.forge("work", "show-a-greeting", "--note", "Use the short greeting")
    assert continued.returncode == 0, continued.stdout + continued.stderr
    prompt = _text(calls)
    assert "Fix round 2 on Show a greeting." in prompt
    assert "Use the short greeting" in prompt
    assert "Question: Which greeting?" in prompt
    assert "The coordinator answered: Use the short greeting" in prompt
    assert "P1 Greeting missing (built.py:1): Show it on the page." in prompt
    assert "FAILED greeting check" in prompt
    assert "earlier brief" in prompt
    assert "## The fix" not in prompt and "## Tests first" not in prompt
    assert "Build the page" not in prompt and "+BUILT = True" not in prompt
    assert "+Coordinator change" in prompt
    assert _sent(calls, "thread/resume")

    record.unlink()
    fresh = repo.forge("work", "show-a-greeting")
    assert fresh.returncode == 0, fresh.stdout + fresh.stderr
    assert "## The fix" in _text(calls) and "## Tests first" in _text(calls)
