"""Close groups Ready fixes. Next-only coverage cannot detect this output bug.

Test audit: Real close creates readiness. Report-only selection loses Ready
items behind optional failures and includes owner-only fixes. Command traces
also expose the full historical-story scan. Existing next tests do not cover
close advice or its cost. Only external services use fakes. No seam is needed.
"""
import json

import pytest

from test_close import env  # noqa: F401
from test_machine_views import github, pull

STORY = "close-suggests-land"


@pytest.mark.parametrize("checks", ["green", "optional-red"])
def test_1_close_names_this_fix_and_other_ready_fixes(env, checks, monkeypatch):
    repo = env.repo
    config = repo.path / "forge.toml"
    local = 'test_place = "local"\ntest = "git --version"\n' if checks == "optional-red" else ""
    env.commit(repo.path, "forge.toml", config.read_text("utf-8") + 'merge = "agent"\n' + local)
    repo.git("push", "-q", "origin", "main")
    first, folder = env.start_fix()
    closed = env.close(first)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert f"Next: forge merge {first}" in closed.stdout.splitlines()
    pr = pull(7, f"fix/{first}")
    pr["headRefOid"] = repo.git("rev-parse", "HEAD", cwd=folder)
    pr["commits"]["nodes"][0]["commit"]["oid"] = pr["headRefOid"]
    if checks == "optional-red":
        pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"].append(
            {"__typename": "CheckRun", "name": "optional", "status": "COMPLETED", "conclusion": "FAILURE"})
    github(env.gh, [pr])
    env.gh.respond("pr", "list", "--state", "open", stdout=json.dumps([pr]))
    second, _ = env.start("footer", "fix/footer", ".factory/fixes/footer.json",
                          {"kind": "fix", "why": "Repair the footer", "done_when": "The footer works"},
                          {"footer.py": "print('footer')\n"})
    env.start("unfinished", "fix/unfinished", ".factory/fixes/unfinished.json",
              {"kind": "fix", "why": "Repair the heading", "done_when": "The heading works"},
              {"heading.py": "print('heading')\n"})
    trace = env.tmp / "git-trace.jsonl"
    monkeypatch.setenv("GIT_TRACE2_EVENT", trace.as_posix())
    closed = env.close(second)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert f"Next: forge land {second} {first}" in closed.stdout.splitlines(), closed.stdout
    assert not env.gh_calls("pr", "merge")
    # Close advice must not scan all historical stories. Git's trace measures the
    # command boundary, independent of the Python helper layout.
    calls = [row["argv"] for line in trace.read_text("utf-8").splitlines()
             if (row := json.loads(line)).get("event") == "start"]
    assert not any("ls-tree" in call and ".factory/stories/" in call for call in calls), calls


def test_2_close_leaves_the_merge_enable_fix_to_the_owner(env, monkeypatch):
    from test_merge_enable import enable, prototype, FIX, BRANCH, URL

    prototype(env)
    monkeypatch.delenv("CODEX_THREAD_ID")
    enabled = enable(env)
    assert enabled.returncode == 0, enabled.stdout + enabled.stderr
    pr = pull(7, BRANCH)
    pr["headRefOid"] = env.repo.git("rev-parse", BRANCH)
    pr["url"] = URL
    github(env.gh, [pr])
    env.gh.respond("pr", "list", "--state", "open", stdout=json.dumps([pr]))
    item, _ = env.start_fix()
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert f"Next: forge merge {item}" in closed.stdout.splitlines(), closed.stdout
    assert not any(FIX in line for line in closed.stdout.splitlines() if line.startswith("Next:")), closed.stdout
