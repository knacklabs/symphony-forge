"""An answer releases the worker's question without an extra worker round."""
import json
import os
from pathlib import Path

import pytest

from test_close import GREEN, env  # noqa: F401
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401

STORY = "clear-answered-worker-question"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("answer", ["note", "allowance", "unrelated allowance", "mixed allowance",
                                    "amend", "prebuild allowance", "shared note", "shared allowance"])
def test_1_answered_question_no_longer_blocks_close_or_next(env, monkeypatch, sdk_data, answer):
    repo = env.repo
    _, calls = _codex_repo(repo, monkeypatch, sdk_data, start_task=False)
    settings = (repo.path / "forge.toml").read_text("utf-8")
    repo.write("forge.toml", 'test = "echo passed"\nchecks = ["tests", "forge-pr-check"]\n' + settings)
    repo.git("add", "forge.toml")
    repo.git("commit", "-qm", "Configure client checks")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Answer the parser question", "--done", "The parser works")
    assert started.returncode == 0, started.stderr
    folder = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    item = "answer-the-parser-question"
    if answer != "prebuild allowance":
        env.commit(folder, "parser.py", "value = 1\n")
    shared = answer.startswith("shared ")
    if shared:
        published = repo.forge("close", item)
        assert published.returncode == 0, published.stdout + published.stderr
        _publish_snapshot(env, folder, item)
    parser_question = "Question: May I use the existing parser?"
    question = ("Question: Allow this fix to change six code files? The coordinator can record "
                'the choice with forge fix allow-large "<reason>".' if "allowance" in answer
                and answer != "unrelated allowance" else
                f'Question: Record the narrower scope with forge fix amend {item} --done "The parser works" '
                '--because "The owner agreed".' if answer == "amend" else parser_question)
    if answer == "mixed allowance":
        question += "\n\n" + parser_question
    monkeypatch.setenv("STUB_SAY", "\n\n" + question)
    asked = repo.forge("work", item)
    assert asked.returncode == 0, asked.stderr
    assert question in repo.forge("close", item).stderr
    monkeypatch.delenv("STUB_SAY")
    answering_folder = folder
    if shared:
        _publish_snapshot(env, folder, item)
        answering_folder = env.tmp / "second-machine"
        repo.git("clone", "--no-local", "-q", "-b", f"fix/{item}",
                 repo.git("remote", "get-url", "origin"), str(answering_folder))
        repo.git("config", "user.name", "Teammate", cwd=answering_folder)
        repo.git("config", "user.email", "teammate@example.test", cwd=answering_folder)
        trust = Path(os.environ["CODEX_HOME"]) / "config.toml"
        trust.write_text(trust.read_text("utf-8") +
                         f'\n[projects.{json.dumps(str(answering_folder.resolve()))}]\ntrust_level = "trusted"\n',
                         encoding="utf-8")
    if answer.endswith("note"):
        answered = repo.forge("work", item, "--note", "Yes, use it.", cwd=answering_folder)
    elif answer == "amend":
        answered = repo.forge("fix", "amend", item, "--done", "The parser works within the narrower scope",
                              "--because", "The owner agreed", cwd=answering_folder)
    else:
        answered = repo.forge("fix", "allow-large", "The owner agreed", cwd=answering_folder)
    assert answered.returncode == 0, answered.stderr
    if shared:
        _publish_snapshot(env, folder, item)
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stderr
    if answer in ("unrelated allowance", "mixed allowance"):
        assert parser_question in shown.stdout
        closed = repo.forge("close", item)
        assert parser_question in closed.stderr
        if answer == "mixed allowance":
            assert "forge fix allow-large" not in shown.stdout + closed.stderr
        return
    assert question not in shown.stdout
    if answer == "prebuild allowance":
        assert f"Next: forge work {item}" in shown.stdout, shown.stdout
        assert f"forge work {item}" in answered.stdout
        resumed = repo.forge("work", item)
        assert resumed.returncode == 0, resumed.stderr
        assert "forge task allow-large" not in _sent(calls, "turn/start")[-1]["input"][0]["text"]
        return
    env.checks(GREEN)
    closed = repo.forge("close", item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "The worker is waiting for an answer" not in closed.stderr


def _publish_snapshot(env, folder, item):
    """GitHub returns the exact body Forge sent, including its real wait events."""
    bodies = env.repo.bin / "gh-bodies.jsonl"
    body = json.loads(bodies.read_text("utf-8").splitlines()[-1])
    pr = {"number": 7, "state": "OPEN", "body": body, "isDraft": False,
          "title": "Answer the parser question", "headRefName": f"fix/{item}",
          "headRefOid": env.repo.git("rev-parse", "HEAD", cwd=folder), "baseRefName": "main",
          "url": "https://github.com/acme/shop/pull/7"}
    env.gh.respond("pr", "list", stdout=json.dumps([pr]))
    env.gh.respond("pr", "list", "--state", "merged", stdout="[]")
    env.gh.respond("api", "graphql", stdout=json.dumps(
        {"data": {"repository": {"pullRequests": {"nodes": [pr]}}}}))
