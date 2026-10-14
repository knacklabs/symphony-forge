"""Published history survives another checkout without its original local diagnostics.

Audit: existing history proofs retain the original logs. This uses real closes,
a remote clone and a real squash; only GitHub and the reviewer are external fakes.
"""
import re

import pytest

from test_close import CLEAN, body, env, finding, report  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_last_task_records_story_outcome import github_merge
from test_worker import install_claude

STORY = "FIX-WHERE-TIME-WENT"


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
@pytest.mark.parametrize("command", ["close", "merge"])
@pytest.mark.parametrize("checkpoint", [True, False], ids=["recorded-checkpoint", "earlier-published-format"])
def test_28_fresh_clone_preserves_published_rounds_findings_and_durations(env, previous, command, checkpoint):
    client(env, previous)
    version = env.repo.forge("--version").stdout.split()[-1]
    env.commit(env.repo.path, "forge.toml", f'version = "{version}"\nstage = "live"\n'
               'workers = "claude"\nmerge = "agent"\ntest = "echo passed"\n'
               'checks = ["tests", "forge-pr-check"]\n'
               'models.build = { model = "opus", effort = "high" }\n')
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    install_claude(env.repo)
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    env.reviews({"exit": 0, "report": report(finding("P2", "Keep the basket label clear"))})
    first = env.close(item)
    assert first.returncode == 0, first.stdout + first.stderr
    first_body = body(env.gh_calls("pr", "edit")[-1])
    env.open_pr(first_body)
    env.commit(where, "app.py", "print('clear basket label')\n")
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    env.reviews(CLEAN)
    second = env.close(item)
    assert second.returncode == 0, second.stdout + second.stderr
    published = body(env.gh_calls("pr", "edit")[-1])
    [earlier_round] = re.findall(r"^Round 1:.*$", published, re.M)
    [earlier_times] = re.findall(r"^building:.*$", published, re.M)
    assert "Keep the basket label clear" in earlier_round
    assert "review" in earlier_round.lower()
    assert "Round 2:" in published
    if not checkpoint:
        # Already published histories from before provenance was recorded remain evidence.
        published = re.sub(r"\n<!-- forge:(?:history|time-record) \{.*\} -->", "", published)
    before = "## How it went\n\nThe owner checked the basket with Ana.\n\n"
    after = "\n\n## Owner notes\n\nCheck again next Tuesday.\n"
    published = before + published + after

    remote = env.repo.git("remote", "get-url", "origin")
    clone = env.tmp / "resumed-clone"
    env.repo.git("clone", "-q", remote, str(clone))
    env.repo.path = clone
    resumed = env.tmp / "resumed-fix"
    env.repo.git("worktree", "add", "-q", "-b", f"fix/{item}", str(resumed),
                 f"origin/fix/{item}")
    assert not (clone / ".git/forge/events.jsonl").exists()
    assert not (clone / ".git/forge/timings.jsonl").exists()
    env.open_pr(published)
    reviewed = len(env.review_calls())
    continued = env.close(item)
    assert continued.returncode == 0, continued.stdout + continued.stderr
    assert len(env.review_calls()) == reviewed, "A resumed close must reuse the saved clean review"
    refreshed = body(env.gh_calls("pr", "edit")[-1])
    env.open_pr(refreshed)
    again = env.close(item)
    assert again.returncode == 0, again.stdout + again.stderr
    assert len(env.review_calls()) == reviewed
    refreshed = body(env.gh_calls("pr", "edit")[-1])
    if command == "merge":
        # Supply the fetched body independently to guard merge's own refresh path.
        # The resumed close above produced the real ready receipt in the fresh clone.
        github_merge(env, f"fix/{item}")
        gh = env.repo.bin / "gh"
        source = gh.read_text("utf-8")
        gh.write_text(source.replace('"isDraft": False',
                                    f'"isDraft": False, "body": {published!r}'), "utf-8")
        merged = env.repo.forge("merge", item)
        assert merged.returncode == 0, merged.stdout + merged.stderr
        refreshed = body(env.gh_calls("pr", "edit")[-1])
        committed = env.repo.git("log", "-1", "--format=%B", "origin/main")
        assert earlier_round in committed
        assert before in committed and after.strip() in committed
    assert refreshed.startswith(before) and refreshed.endswith(after)
    managed = refreshed.split("<!-- forge:begin -->", 1)[1].split("<!-- forge:end -->", 1)[0]
    # Count the rendered history, excluding the shared machine record carried beside it.
    managed = re.sub(r"<!--.*?-->", "", managed, flags=re.S)
    assert earlier_round in managed
    assert managed.count("Round 1:") == managed.count("Round 2:") == 1
    assert managed.count("## How it went") == 1
    assert "Keep the basket label clear" in managed
    if checkpoint:
        # Shared intervals retain earlier work; later CI and idle time update the single total.
        for category in ("building", "own tests", "reviewing", "fixing findings"):
            fragment = re.search(rf"(?:^|; )({category}: [^;]+)", earlier_times)[1]
            assert fragment in managed
    else:
        # Without interval evidence, legacy snapshots remain separate and unchanged.
        assert earlier_times in managed
