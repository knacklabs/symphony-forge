"""An answer releases the worker's question without an extra worker round."""
from pathlib import Path

import pytest

from test_close import GREEN, env  # noqa: F401
from test_codex_worker import _codex_repo, sdk_data  # noqa: F401

STORY = "clear-answered-worker-question"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("answer", ["note", "allowance", "unrelated allowance"])
def test_1_answered_question_no_longer_blocks_close_or_next(env, monkeypatch, sdk_data, answer):
    repo = env.repo
    _codex_repo(repo, monkeypatch, sdk_data, start_task=False)
    settings = (repo.path / "forge.toml").read_text("utf-8")
    repo.write("forge.toml", 'test = "echo passed"\nchecks = ["tests", "forge-pr-check"]\n' + settings)
    repo.git("add", "forge.toml")
    repo.git("commit", "-qm", "Configure client checks")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Answer the parser question", "--done", "The parser works")
    assert started.returncode == 0, started.stderr
    folder = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    item = "answer-the-parser-question"
    env.commit(folder, "parser.py", "value = 1\n")
    question = ("Question: Allow this fix to change six code files? The coordinator can record "
                'the choice with forge fix allow-large "<reason>".' if answer == "allowance" else
                "Question: May I use the existing parser?")
    monkeypatch.setenv("STUB_SAY", "\n\n" + question)
    asked = repo.forge("work", item)
    assert asked.returncode == 0, asked.stderr
    assert question in repo.forge("close", item).stderr
    monkeypatch.delenv("STUB_SAY")
    if answer == "note":
        answered = repo.forge("work", item, "--note", "Yes, use it.")
    else:
        answered = repo.forge("fix", "allow-large", "The owner agreed", cwd=folder)
    assert answered.returncode == 0, answered.stderr
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stderr
    if answer == "unrelated allowance":
        assert question in shown.stdout
        assert question in repo.forge("close", item).stderr
        return
    assert question not in shown.stdout
    env.checks(GREEN)
    closed = repo.forge("close", item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "The worker is waiting for an answer" not in closed.stderr
