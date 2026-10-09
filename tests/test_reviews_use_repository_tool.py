"""Autoreview chooses models; Forge selects the repository tool for every review kind."""
import json

import pytest

from test_close import env  # noqa: F401
from test_proto_signoff import _client, _decision

STORY = "FIX-CLAUDE-SONNET-DEFAULT"


@pytest.mark.parametrize("family", ["claude", "codex"])
@pytest.mark.parametrize("light", [False, True], ids=["normal", "light"])
def test_6_close_uses_repository_tool_without_model_or_effort_overrides(env, family, light):
    toml = env.repo.path / "forge.toml"
    text = toml.read_text("utf-8").replace('workers = "claude"', f'workers = "{family}"')
    # Legacy configured pins must not become overrides of the external program's defaults.
    text += ('\n[models.review.codex]\nmodel = "gpt-6-astra"\neffort = "xhigh"\n'
             '\n[models.review.claude]\nmodel = "custom-claude"\neffort = "low"\n')
    if light:
        text = 'repo = "client"\nstage = "prototype"\n' + text
    env.commit(env.repo.path, "forge.toml", text)
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix(**({"allow_large": "Prototype before sign-off"} if light else {}))
    result = env.close(item)
    assert result.returncode == 0, result.stdout + result.stderr
    [call] = env.review_calls()
    options = dict(zip(call["args"][::2], call["args"][1::2]))
    assert options["--engine"] == family
    assert options["--max-priority"] == ("P0" if light else "P3")
    assert "--model" not in options and "--thinking" not in options


@pytest.mark.parametrize("family", ["claude", "codex"])
def test_7_signoff_uses_repository_tool_and_accepts_autoreview_default_selection(
        repo, tmp_path, monkeypatch, family):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    toml = fix / "forge.toml"
    toml.write_text(toml.read_text("utf-8") + f'workers = "{family}"\n', "utf-8")
    repo.git("commit", "-qam", "Choose the repository tool", cwd=fix)
    page = _decision(fix, answers)
    # Complete clean review, without a model header: Autoreview owns the selection.
    result = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: accepted" in page.read_text("utf-8")
    [call] = [json.loads(line) for line in queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()]
    options = dict(zip(call["args"][::2], call["args"][1::2]))
    assert options["--engine"] == family
    assert "--model" not in options and "--thinking" not in options
