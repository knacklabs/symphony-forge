"""A base-branch repair must invalidate blocking findings even when the branch diff is unchanged."""

import json
import os
from pathlib import Path

import pytest

from test_close import env, finding, report  # noqa: F401
from test_close_holds_after_three_blocked_reviews import client_item

STORY = "review-current-head"


@pytest.mark.parametrize("previous", [False, True], ids=["init", "earlier-adoption"])
@pytest.mark.parametrize("command", ["close", "land"])
def test_1_close_and_land_review_the_repaired_head_before_reusing_blocking_findings(
        env, tmp_path, monkeypatch, previous, command):
    item, where = client_item(env, tmp_path, previous)
    path = "docs/product/BRIEF.md"
    env.repo.git("checkout", "-q", "-b", "fix/default-greeting")
    env.commit(env.repo.path, ".factory/fixes/default-greeting.json", json.dumps({
        "kind": "fix", "status": "working", "branch": "fix/default-greeting",
        "why": "Repair the greeting", "done_when": "The greeting welcomes readers"}))
    env.commit(env.repo.path, "docs/decisions/0001-client-signoff.md",
               '---\nstatus: accepted\nconfirmed_by: "A Client"\n---\n\n# Client sign-off\n')
    remote = Path(env.repo.git("remote", "get-url", "origin"))
    env.commit(env.repo.path, path, "Broken greeting\n")
    env.repo.git("push", "-q", "origin", "HEAD:refs/heads/fix/default-greeting")
    env.repo.git("update-ref", "refs/heads/main", env.repo.git("rev-parse", "HEAD"), cwd=remote)
    # Fake only Autoreview: its answer depends on the file in Forge's real review checkout.
    helper = Path(os.environ["AUTOREVIEW"])
    log = tmp_path / "reviewed-heads.jsonl"
    helper.write_text(
        "import json, subprocess, sys\n"
        "from pathlib import Path\n"
        f"text = Path({json.dumps(path)}).read_text('utf-8')\n"
        "head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()\n"
        f"with Path({json.dumps(log.as_posix())}).open('a', encoding='utf-8') as out:\n"
        "    out.write(json.dumps({'head': head, 'text': text}) + '\\n')\n"
        f"broken = {json.dumps(report(finding('P1', 'Repair the greeting', path)))}\n"
        f"clean = {json.dumps(report())}\n"
        "answer = clean if text == 'Hello readers\\n' else broken\n"
        "args = sys.argv[1:]\n"
        "Path(args[args.index('--json-output') + 1]).write_text(json.dumps(answer), 'utf-8')\n"
        "sys.exit(0 if answer is clean else 1)\n", encoding="utf-8")
    first = env.repo.forge("close", item, cwd=where)
    assert first.returncode == 1, first.stdout + first.stderr
    assert "The review left serious findings open:" in first.stderr, first.stdout + first.stderr

    env.commit(env.repo.path, path, "Hello readers\n")
    # GitHub lands the separate repair; the client hooks stay enabled throughout.
    env.repo.git("push", "-q", "origin", "HEAD:refs/heads/fix/default-greeting")
    env.repo.git("update-ref", "refs/heads/main", env.repo.git("rev-parse", "HEAD"), cwd=remote)
    # Exercise land at its last round: reusing the old finding would stop it immediately.
    monkeypatch.setenv("FORGE_LAND_ROUNDS", "3")
    env.gh.respond("pr", "view", stdout=json.dumps({"url": "https://github.com/acme/shop/pull/7"}))
    repaired = env.repo.forge(command, item, cwd=where)
    assert repaired.returncode == 0, repaired.stdout + repaired.stderr
    assert "Ready:" in repaired.stdout
    reviewed = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    assert len(reviewed) == 2
    assert reviewed[0]["head"] != reviewed[1]["head"]
    assert reviewed[1]["text"] == "Hello readers\n"
