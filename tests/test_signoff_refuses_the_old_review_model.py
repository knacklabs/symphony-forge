"""Autoreview owns model selection; a completed sign-off review is not rejected for its model."""
import json

from test_close import env  # noqa: F401 (pytest fixture)
from test_proto_signoff import _client, _decision

STORY = "FIX-THE-OWNER-CHOSE-GPT-6-1-SOL-AT-HIGH-EFFO"


def test_1_signoff_accepts_autoreview_selection_without_a_forge_model_pin(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    page = _decision(fix, answers)
    queue.write_text(json.dumps([{"say": "model: gpt-6-sol\nthinking: high\nautoreview done",
                                  "report": {"review_status": "scoped-clean", "findings": []}}]))
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "status: accepted" in page.read_text()


def test_2_the_skill_leaves_review_models_to_autoreview(env):
    # The coordinator learns tool routing and external defaults from the real synced guide.
    env.repo.git("checkout", "-q", "-b", "fix/review-models")
    synced = env.repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    skill = " ".join((env.repo.path / ".claude/skills/forge/SKILL.md").read_text("utf-8").split())
    assert "Every normal, light and sign-off review" in skill
    assert 'Claude when `workers = "claude"`, Codex when `workers = "codex"`' in skill
    assert "Forge pins no review model or effort" in skill
    assert "light review that blocks only on P0 findings" in skill
