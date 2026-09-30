"""The client sign-off review is pinned to GPT-6.1 Sol at high effort; GPT-6 Sol no longer counts."""
import json

from test_close import env  # noqa: F401 (pytest fixture)
from test_proto_signoff import _client, _decision

STORY = "FIX-THE-OWNER-CHOSE-GPT-6-1-SOL-AT-HIGH-EFFO"


def test_1_signoff_refuses_a_review_that_ran_on_gpt_6_sol(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    page = _decision(fix, answers)
    queue.write_text(json.dumps([{"say": "model: gpt-6-sol\nthinking: high\nautoreview done",
                                  "report": {"review_status": "scoped-clean", "findings": []}}]))
    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert refused.returncode == 1
    assert "did not confirm GPT-6.1 Sol at high effort" in refused.stderr
    assert "status: proposed" in page.read_text()


def test_2_the_skill_names_the_review_models(env):
    # The coordinator learns the sign-off pin and the review defaults from the skill forge sync writes.
    env.repo.git("checkout", "-q", "-b", "fix/review-models")
    synced = env.repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    skill = " ".join((env.repo.path / ".claude/skills/forge/SKILL.md").read_text("utf-8").split())
    assert ("That review always runs on `gpt-6.1-sol` at high effort, whatever `forge.toml` says"
            in skill)
    assert "which `forge init` sets to `gpt-6.1-sol` at high effort" in skill
    assert "light review on `gpt-6.1-sol` at medium effort" in skill
