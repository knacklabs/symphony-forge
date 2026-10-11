"""Autoreview chooses review defaults; Forge's former model and effort pins are gone."""
import json
import tomllib

from test_proto_signoff import _client, _decision
from test_setup import _fresh_client

STORY = "FIX-REVIEWS-RUN-ON-GPT-6-SOL-AT-XHIGH-EFFORT"


def test_1_forge_init_leaves_review_defaults_to_autoreview(repo, gh, tmp_path):
    client, result = _fresh_client(repo, gh, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    config = tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))
    assert "review" not in config["models"]


def test_2_signoff_review_uses_autoreviews_defaults(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    page = _decision(fix, answers)
    queue.write_text(json.dumps([{"say": "model: gpt-6.1-sol\nthinking: high\nautoreview done",
                                  "report": {"review_status": "scoped-clean", "findings": []}}]))
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stderr
    assert "status: accepted" in page.read_text()
    call = json.loads(queue.with_suffix(".calls.jsonl").read_text().splitlines()[-1])
    options = dict(zip(call["args"][::2], call["args"][1::2]))
    assert options["--engine"] == "codex"
    assert "--model" not in options and "--thinking" not in options
