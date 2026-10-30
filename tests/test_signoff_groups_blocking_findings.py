"""Test audit: Protect one runnable repair step for all sign-off blockers.

The old next step names no fix and encourages separate repair loops. Existing
sign-off tests check refusal, not the suggested repair command. Exercise the
real commands, fake only external reviews, and add no production seam.
Prototype clients require an explicit worker kind. A live-stage fixture cannot
catch an unusable repair command in that main sign-off flow.
"""

import json
import shlex

import pytest

from test_proto_signoff import _adopted_client, _client, _decision, _request_build

STORY = "signoff-one-fix-for-all"


@pytest.mark.platform
@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-release"])
def test_1_blocked_signoff_names_one_fix_for_every_blocker(repo, tmp_path, monkeypatch, adopted):
    if adopted:
        fix, answers, queue = _adopted_client(repo, tmp_path, monkeypatch)
    else:
        fix, answers, queue = _client(repo, tmp_path, monkeypatch, working_build=False)
    _request_build(repo, fix)
    _decision(fix, answers)
    titles = ["Customer's order cannot save", 'Missing "Cancel" action']
    queue.write_text(json.dumps([
        {"report": {"review_status": "scoped-clean", "findings": []}},
        {"report": {"review_status": "findings", "findings": [
            {"priority": "P1", "title": title,
             "body": "Gain 5, Work 2, Harm 1\nThe demo cannot finish.",
             "code_location": {"file_path": "app.py", "line": 1}}
            for title in titles]}},
    ]), encoding="utf-8")

    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert refused.stderr.count("forge fix start ") == 1, refused.stderr
    command = refused.stderr.split("forge fix start ", 1)[1].splitlines()[0]
    args = shlex.split("fix start " + command)
    for title in titles:
        assert f"{title} (app.py:1)" in args[2]
        assert f"{title} (app.py:1)" in args[args.index("--done") + 1]
    assert 'forge decision accept client-signoff --by "<name>"' in refused.stderr.splitlines()[-1]
    started = repo.forge(*args, cwd=fix)
    assert started.returncode == 0, started.stdout + started.stderr
    assert "Started fix" in started.stdout
