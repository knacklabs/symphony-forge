"""Sign-off accepts the model Autoreview chooses, instead of enforcing Forge's old pin."""
import json

from test_close import env  # noqa: F401 (pytest fixture)
from test_proto_signoff import _client, _decision

STORY = "FIX-THE-OWNER-CHOSE-GPT-6-1-SOL-AT-HIGH-EFFO"


def test_1_signoff_accepts_the_model_autoreview_reports(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    page = _decision(fix, answers)
    queue.write_text(json.dumps([{"say": "model: gpt-6-sol\nthinking: high\nautoreview done",
                                  "report": {"review_status": "scoped-clean", "findings": []}}]))
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stderr
    assert "status: accepted" in page.read_text()
    events = [json.loads(line) for line in (repo.path / ".git/forge/events.jsonl").read_text().splitlines()]
    review = next(event for event in reversed(events)
                  if event["event"] == "run end" and event["item"] == "client-signoff")
    assert (review["model"], review["effort"]) == ("gpt-6-sol", "high")


def test_2_the_skill_explains_autoreviews_defaults(env):
    # The coordinator learns that Autoreview owns review defaults from the synced skill.
    env.repo.git("checkout", "-q", "-b", "fix/review-models")
    synced = env.repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    skill = " ".join((env.repo.path / ".claude/skills/forge/SKILL.md").read_text("utf-8").split())
    assert "Every normal, light and sign-off review" in skill
    assert 'Claude when `tools = "claude"`, Codex when `tools = "codex"`' in skill
    assert "Forge pins no review model or effort" in skill
    assert "light review that blocks only on P0 findings" in skill
