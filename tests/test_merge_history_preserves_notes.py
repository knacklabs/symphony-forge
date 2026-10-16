"""Refreshing merge history preserves the owner's sections in the published squash."""
import json

from test_close import body, env, finding, report  # noqa: F401
from test_last_task_records_story_outcome import github_merge

STORY = "FIX-WHERE-TIME-WENT"


def test_18_merge_refreshes_only_managed_history_and_keeps_handwritten_sections(env):
    # A handwritten heading identical to Forge's must survive both the PR edit and squash.
    # Existing squash coverage has no owner text surrounding the managed block.
    config = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", config.read_text("utf-8") + 'merge = "agent"\n')
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix(round=1)
    env.reviews({"exit": 0, "report": report(finding("P2", "Use clearer basket copy"))})
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    generated = body(env.gh_calls("pr", "edit")[-1])
    before = "## How it went\n\nThe owner tested the basket with Ana.\n\n"
    after = "\n\n## How it went\n\nThe owner will check back next Tuesday.\n"
    published = before + generated + after
    github_merge(env, f"fix/{item}")
    gh = env.repo.bin / "gh"
    source = gh.read_text("utf-8")
    gh.write_text(source.replace('"isDraft": False',
                                f'"isDraft": False, "body": {published!r}'), "utf-8")
    merged = env.repo.forge("merge", item)
    assert merged.returncode == 0, merged.stderr
    refreshed = body(env.gh_calls("pr", "edit")[-1])
    committed = env.repo.git("log", "-1", "--format=%B", "origin/main")
    assert refreshed.startswith(before)
    assert refreshed.endswith(after)
    assert before in committed and after.strip() in committed
    assert refreshed.count("<!-- forge:begin -->") == 1
    assert refreshed.count("<!-- forge:end -->") == 1
    managed = refreshed.split("<!-- forge:begin -->", 1)[1].split("<!-- forge:end -->", 1)[0]
    assert "Review: clean" in managed
    assert "Use clearer basket copy" in managed
    assert "CI passed, then passed" in managed
    assert "CI passed, then passed" in committed


def test_19_merge_adds_history_to_an_already_ready_pre_upgrade_pull_request(env):
    # Audit: old close published this managed block and two-field ready receipt. No modern
    # close runs here; existing squash proofs first publish a modern How it went section.
    # Only GitHub is faked; Forge must insert the section and preserve the real squash body.
    config = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", config.read_text("utf-8") + 'merge = "agent"\n')
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix(status="waiting for checks")
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    env.repo.git("push", "-q", "origin", f"fix/{item}", cwd=where)
    ready = env.repo.path / ".git" / "forge" / "ready" / f"{item}.json"
    ready.parent.mkdir(parents=True, exist_ok=True)
    ready.write_text(json.dumps({"commit": head, "review": "clean"}) + "\n", "utf-8")
    before = "## How it went\n\nThe owner tested the basket with Ana.\n\n"
    managed = "<!-- forge:begin -->\nReview: clean, 0 dismissed, 0 advice.\n<!-- forge:end -->"
    after = "\n\n## Owner notes\n\nCheck back next Tuesday.\n"
    published = before + managed + after
    github_merge(env, f"fix/{item}")
    gh = env.repo.bin / "gh"
    source = gh.read_text("utf-8")
    gh.write_text(source.replace('"isDraft": False',
                                f'"isDraft": False, "body": {published!r}'), "utf-8")

    merged = env.repo.forge("merge", item)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    edits = env.gh_calls("pr", "edit")
    assert len(edits) == 1, "Merge must publish history on the already-ready legacy pull request"
    refreshed = body(edits[0])
    assert refreshed.startswith(before) and refreshed.endswith(after)
    generated = refreshed.split("<!-- forge:begin -->", 1)[1].split("<!-- forge:end -->", 1)[0]
    assert "Review: clean, 0 dismissed, 0 advice." in generated
    assert generated.count("## How it went") == 1
    assert "waiting for CI:" in generated and "CI passed" in generated
    committed = env.repo.git("log", "-1", "--format=%B", "origin/main")
    assert refreshed.rstrip() in committed
    assert not env.gh_calls("pr", "create")
