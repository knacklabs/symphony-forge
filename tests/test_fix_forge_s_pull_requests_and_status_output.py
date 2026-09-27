"""Owner-facing output from Forge's pull requests, board, and next command."""
import json
from test_close import CLEAN, blocked, body, env, finding  # noqa: F401 - command-level fixture
from test_story import setup

STORY = "forge-s-pull-requests-and-status-output"

def test_1_pr_title_and_labeled_body(env):
    item, _ = env.start_task()
    env.reviews(CLEAN)
    assert env.close(item).returncode == 0
    create = env.gh_calls("pr", "create")[-1]
    assert create[create.index("--title") + 1] == "Shoppers can save a basket: Save a basket"
    assert body(create).startswith("Why: Shoppers lose their basket when they leave.\n"
                                   "Done when: Shoppers can save their basket with one click\n")


def test_2_fix_title_uses_first_clause_and_seventy_characters(env):
    why = "A very long owner-facing explanation of the problem, with more details that continue"
    item, _ = env.start_fix(why=why)
    env.reviews(CLEAN)
    assert env.close(item).returncode == 0
    create = env.gh_calls("pr", "create")[-1]
    assert create[create.index("--title") + 1] == why.split(",", 1)[0][:70]


def test_3_review_block_opens_with_plain_verdict(env):
    item, _ = env.start_fix()
    env.reviews(CLEAN)
    assert env.close(item).returncode == 0
    review = body(env.gh_calls("pr", "create")[-1]).split("<!-- forge:begin -->\n", 1)[1]
    assert review.startswith("The review found no serious problems.\n")
    assert "Forge review of " not in review


def test_4_promoted_spec_task_is_named_spec(repo):
    setup(repo)
    fix = repo.path.parent / "repo-fix-write-spec"
    repo.git("worktree", "add", "-q", "-b", "fix/write-spec", str(fix), "main")
    state = fix / ".factory/fixes/write-spec.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"why": "Write the product spec", "done_when": "The spec is ready"}))
    repo.git("add", "-A", cwd=fix)
    repo.git("commit", "-q", "-m", "Write spec", cwd=fix)
    result = repo.forge("story", "new", "PRODUCT", "--from-fix", "write-spec")
    assert result.returncode == 0, result.stderr
    assert "| SPEC |" in repo.git("show", "story/PRODUCT:plans/PRODUCT.md")
    assert repo.git("branch", "--list", "task/PRODUCT-SPEC")


def test_5_board_links_items_to_pull_requests(repo, gh, tmp_path):
    setup(repo)
    fix = repo.path.parent / "repo-fix-tidy-up"
    repo.git("worktree", "add", "-q", "-b", "fix/tidy-up", str(fix), "main")
    state = fix / ".factory/fixes/tidy-up.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"branch": "fix/tidy-up", "why": "Tidy up", "status": "ready"}))
    gh.respond("pr", "list", stdout=json.dumps([{"headRefName": "fix/tidy-up", "state": "OPEN",
        "title": "Tidy up", "url": "https://github.com/acme/shop/pull/7"}]))
    out = tmp_path / "board.html"
    result = repo.forge("board", "--out", str(out))
    assert result.returncode == 0, result.stderr
    assert '<a href="https://github.com/acme/shop/pull/7">Tidy up</a>' in out.read_text()
    calls = [call for call in gh.calls() if call[:2] == ["pr", "list"]]
    assert "--limit" in calls[-1] and int(calls[-1][calls[-1].index("--limit") + 1]) <= 25


def test_6_next_names_ready_pr_and_close_findings(repo, gh):
    setup(repo)
    fix = repo.path.parent / "repo-fix-tidy-up"
    repo.git("worktree", "add", "-q", "-b", "fix/tidy-up", str(fix), "main")
    state = fix / ".factory/fixes/tidy-up.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"branch": "fix/tidy-up", "why": "Tidy up", "status": "ready"}))
    gh.respond("pr", "list", "--state", "merged", stdout="[]")
    gh.respond("pr", "list", "--state", "open", stdout=json.dumps([{
        "headRefName": "fix/tidy-up", "url": "https://github.com/acme/shop/pull/7"}]))
    result = repo.forge("next")
    assert result.returncode == 0, result.stderr
    assert "ready to merge: https://github.com/acme/shop/pull/7" in result.stdout
    state.write_text(json.dumps({"branch": "fix/tidy-up", "why": "Tidy up", "status": "fixing",
                                 "review": {"findings": [{"priority": "P1", "title": "Missing greeting"}],
                                            "dismissals": []}}))
    result = repo.forge("next")
    assert "Missing greeting" in result.stdout


def test_7_next_names_pr_after_successful_close(env):
    item, _ = env.start_fix()
    env.reviews(CLEAN)
    assert env.close(item).returncode == 0
    env.gh.respond("pr", "list", "--state", "open", stdout=json.dumps([{
        "headRefName": "fix/tidy-readme", "url": "https://github.com/acme/shop/pull/7",
        "isDraft": False, "statusCheckRollup": [
            {"name": name, "conclusion": "SUCCESS", "completedAt": "2026-09-27T10:00:00Z"}
            for name in ("tests", "forge-pr-check")]}]))
    result = env.repo.forge("next")
    assert result.returncode == 0, result.stderr
    assert "ready to merge: https://github.com/acme/shop/pull/7" in result.stdout


def test_8_next_names_finding_after_close_stops(env):
    item, _ = env.start_fix()
    env.reviews(blocked(finding("P1", "A greeting is missing")))
    assert env.close(item).returncode == 1
    result = env.repo.forge("next")
    assert result.returncode == 0, result.stderr
    assert "Close stopped on The fix tidy-readme: A greeting is missing." in result.stdout


def test_9_board_puts_active_work_first_and_folds_finished_fixes(repo, gh, tmp_path):
    setup(repo, keys=("OLD", "LIVE"))
    repo.write("plans/roadmap.json", json.dumps({"items": [
        {"key": "OLD", "title": "An earlier story"},
        {"key": "LIVE", "title": "A current story"}]}))
    repo.write(".factory/stories/OLD/story.json", json.dumps({
        "title": "An earlier story", "status": "done", "finished": "2026-09-26T10:00:00Z"}))
    repo.write(".factory/stories/LIVE/story.json", json.dumps({
        "title": "A current story", "status": "planning"}))
    repo.write(".factory/fixes/finished-fix.json", json.dumps({
        "branch": "fix/finished-fix", "why": "A finished fix", "status": "ready"}))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Track current work")
    repo.git("push", "-q", "origin", "main")
    active = repo.path.parent / "repo-fix-active-fix"
    repo.git("worktree", "add", "-q", "-b", "fix/active-fix", str(active), "main")
    state = active / ".factory/fixes/active-fix.json"
    state.write_text(json.dumps({"branch": "fix/active-fix", "why": "An active fix",
                                 "status": "working"}))
    gh.respond("pr", "list", stdout=json.dumps([{
        "headRefName": "fix/finished-fix", "state": "MERGED", "title": "A finished fix",
        "url": "https://github.com/acme/shop/pull/8",
        "mergedAt": "2026-09-26T10:00:00Z"}]))
    out = tmp_path / "board.html"
    result = repo.forge("board", "--out", str(out))
    assert result.returncode == 0, result.stderr
    page = out.read_text()
    assert page.index("A current story") < page.index("An earlier story")
    assert "<summary>1 finished fix</summary>" in page
    assert page.index("An active fix") < page.index("<summary>1 finished fix</summary>")
    assert '<a href="https://github.com/acme/shop/pull/8">A finished fix</a>' in page
    assert "An active fix</b>: <span class=\"status\">In progress." in page
