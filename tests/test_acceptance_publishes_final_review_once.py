"""Accepting review findings publishes the final records in one branch update."""
import json
import stat
from pathlib import Path

import pytest

from conftest import _install
from test_close import blocked, body, env, finding  # noqa: F401
from test_two_round_limit import client
from test_reviewchoice_skip import _default_moves_during_checks

STORY = "review-findings-split-from-close-pushes"


@pytest.mark.platform
@pytest.mark.parametrize("previous,moved", [(False, False), (True, False), (False, True)],
                         ids=["new", "earlier-adopted", "default-moves"])
def test_1_acceptance_publishes_once_after_final_review_records(env, previous, moved, tmp_path, monkeypatch):
    client(env, previous)
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    config = "\n".join(line for line in config.splitlines()
                       if not line.startswith(("merge =", "test_place =")))
    env.commit(env.repo.path, "forge.toml", 'merge = "agent"\ntest_place = "ci"\n' + config + "\n")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    defect = finding("P1", "Greeting needs more detail")
    defect["body"] = "Gain 4, Work 1, Harm 2\nCase: normal use - Readers miss the detail."
    env.reviews(blocked(defect))
    stopped = env.close(item)
    assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    assert "reached the round limit" in stopped.stderr
    env.open_pr(body(env.gh_calls("pr", "create")[-1]), draft=True)

    # Observe real remote branch updates only during acceptance, after the stopped review.
    updates = env.tmp / "accepted-heads"
    hook = Path(env.repo.git("remote", "get-url", "origin")) / "hooks" / "post-receive"
    hook.write_text(f'#!/bin/sh\ncat >> "{updates.as_posix()}"\n', encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC)
    reason = "Keep this greeting for now"
    if moved:
        _default_moves_during_checks(env, tmp_path, where, False, monkeypatch)
    else:
        # The CI review check must run the real command on the published head,
        # rather than report a canned success before close writes its ready record.
        gh = (env.repo.bin / "gh").read_text("utf-8")
        needle = 'responses = here / "gh-responses.json"\n'
        inject = (
            "if args[:4] == ['api', '--paginate', '--jq', '.check_runs[]']:\n"
            "    head = args[-1].split('/commits/')[1].split('/')[0]\n"
            f"    checked = subprocess.run([sys.executable, str(here / 'forge'), 'hook', 'pr-check', "
            f"'--base', 'origin/main', '--head', head, '--branch', {json.dumps('fix/' + item)}], "
            f"cwd={json.dumps(where.as_posix())}, capture_output=True, text=True, encoding='utf-8', timeout=60)\n"
            "    append_json(here / 'acceptance-pr-checks.jsonl', "
            "{'head': head, 'exit': checked.returncode, 'output': checked.stdout + checked.stderr})\n"
            "    sys.stdout.write(json.dumps({'name': 'tests', 'status': 'completed', 'conclusion': 'success'}) + '\\n')\n"
            "    sys.stdout.write(json.dumps({'name': 'forge-pr-check', 'status': 'completed', "
            "'conclusion': 'failure' if checked.returncode else 'success'}) + '\\n')\n"
            "    sys.exit(0)\n"
        )
        assert needle in gh
        _install(env.repo.bin, "gh", gh.replace(needle, inject + needle, 1))

    accepted = env.close(item, "--resolve", "accept", "--reason", reason)

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert f"Ready: {item}" in accepted.stdout, accepted.stdout + accepted.stderr
    common = Path(env.repo.git("rev-parse", "--git-common-dir", cwd=where))
    if not common.is_absolute():
        common = where / common
    ready = common / "forge" / "ready" / f"{item}.json"
    assert json.loads(ready.read_text("utf-8"))["commit"] == env.repo.git("rev-parse", "HEAD", cwd=where)
    heads = [line.split()[1] for line in updates.read_text("utf-8").splitlines()
             if line.split()[2] == f"refs/heads/fix/{item}"]
    assert len(heads) == (2 if moved else 1), heads
    assert heads[-1] == env.repo.git("rev-parse", "HEAD", cwd=where)
    if not moved:
        checked = [json.loads(line) for line in
                   (env.repo.bin / "acceptance-pr-checks.jsonl").read_text("utf-8").splitlines()]
        assert checked and all(row["head"] == heads[-1] and row["exit"] == 0 for row in checked), checked
    published = body(env.gh_calls("pr", "edit")[-1])
    assert "Review: clean, 1 dismissed" in published
    assert f"Human accepted the remaining finding: {reason}" in published
    for field in (".check_runs[]", ".statuses[]"):
        calls = env.gh_calls("api", "--paginate", "--jq", field)
        assert calls and all(any(f"/commits/{head}/" in call[-1] for head in heads) for call in calls)
        assert f"/commits/{heads[-1]}/" in calls[-1][-1]
