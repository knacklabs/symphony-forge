"""Test audit: protect accept/next output and the lifetime of repair advice.

The regression counts old keys forever and puts repairs before the build.
Existing hotspot tests have no sign-off transition. Reuse real commands and
fixtures, with no production seam. Cover new and earlier-adopted clients.
"""
import json
import shlex

import pytest

from test_proto_signoff import _adopted_client, _client, _decision
from test_spotted import entry

STORY = "FIX-AFTER-SIGNOFF-NEXT-LEADS-WITH-BUILD"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("client", ["working-build", "canvas", "earlier-adopted"])
def test_1_accepted_signoff_leads_with_build_and_excludes_old_problems(
        repo, tmp_path, monkeypatch, client):
    if client == "earlier-adopted":
        fix, answers, _ = _adopted_client(repo, tmp_path, monkeypatch)
    else:
        fix, answers, _ = _client(repo, tmp_path, monkeypatch,
                                 working_build=client == "working-build")
    old = [entry("bug", "PRODUCT.md", 1, text, "worker", item="prototype")
           for text in ("Alpha", "Beta", "Gamma")]
    old += [entry("bug", "PRODUCT.md", 1, "Serious prototype problem", "blocking", item=item)
            for item in ("first-prototype", "second-prototype")]
    path = fix / "plans/spotted.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"items": old}), encoding="utf-8")
    repo.git("add", "plans/spotted.json", cwd=fix)
    repo.git("commit", "-q", "-m", "Note prototype problems", cwd=fix)
    _decision(fix, answers)
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    branch = repo.git("branch", "--show-current", cwd=fix)
    repo.git("merge", "--no-ff", "-m", "Merge sign-off", branch)
    repo.git("push", "-q", "origin", "main")
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stderr
    assert "PRODUCT.md keeps breaking" not in shown.stdout
    assert "The app constitution comes next." in accepted.stdout
    command = 'Next: forge fix start "Write the prototype plan"'
    assert next(line for line in shown.stdout.splitlines() if line.startswith("Next: ")).startswith(command)

    # Editing an old record does not renew its age. New keys on the same file
    # count from zero. Both legacy and per-change records participate.
    old[0]["line"] = 8
    fresh = [entry("bug", "PRODUCT.md", 1, text, "worker", item="production")
             for text in ("Delta", "Epsilon", "Zeta")]
    repo.write("plans/spotted.json", json.dumps({"items": old}))
    for count in (2, 3):
        repo.write("plans/spotted/production.json", json.dumps({"items": fresh[:count]}))
        repo.git("add", "plans")
        repo.git("commit", "-q", "-m", "Note production problems")
        repo.git("push", "-q", "origin", "main")
        shown = repo.forge("next")
        assert shown.returncode == 0, shown.stderr
        assert ("PRODUCT.md keeps breaking: 3 noted problems are open there." in shown.stdout) == (count == 3)
        assert next(line for line in shown.stdout.splitlines() if line.startswith("Next: ")).startswith(command)

    if client == "working-build":
        # Own the continuation at the same command boundary: priority must not
        # create another constitution fix after the first one starts. Existing
        # constitution tests have no competing post-sign-off repair advice.
        step = next(line.removeprefix("Next: ") for line in shown.stdout.splitlines()
                    if line.startswith("Next: "))
        started = repo.forge(*shlex.split(step)[1:])
        assert started.returncode == 0, started.stdout + started.stderr
        work = next(line.removeprefix("Next: ") for line in started.stdout.splitlines()
                    if line.startswith("Next: "))
        continued = repo.forge("next")
        assert continued.returncode == 0, continued.stderr
        assert f"Next: {work}" in continued.stdout.splitlines()
