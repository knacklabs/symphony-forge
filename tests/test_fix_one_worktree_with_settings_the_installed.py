"""`forge next` keeps listing fixes when one worktree has unsupported settings."""

import json

from test_story import DOC, setup

STORY = "one-worktree-with-settings-the-installed"


def test_1_next_lists_other_items_and_names_unreadable_worktrees(repo, gh, monkeypatch):
    setup(repo)
    monkeypatch.setenv("FORGE_NOW", "2026-11-16T09:00:00+00:00")
    repo.write("plans/SHOP.md", DOC)
    repo.write(".factory/stories/SHOP/story.json", json.dumps({"status": "approved", "title":
                                                               "Shoppers can save a basket"}))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Approve basket story")
    repo.git("push", "-q", "origin", "main")
    broken = repo.path.parent / "repo fix broken settings"
    broken_task = repo.path.parent / "repo task SHOP SAVE"
    healthy = repo.path.parent / "repo fix healthy"
    for branch, path, rel, status in (
        ("fix/broken-settings", broken, ".factory/fixes/broken-settings.json", "waiting for checks"),
        ("task/SHOP-SAVE", broken_task, ".factory/stories/SHOP/tasks/SAVE.json", "waiting for checks"),
        ("fix/healthy", healthy, ".factory/fixes/healthy.json", "started"),
    ):
        repo.git("worktree", "add", "-q", "-b", branch, str(path), "main")
        state = path / rel
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps({"branch": branch, "status": status}),
                         encoding="utf-8")
    for path in (broken, broken_task):
        (path / "forge.toml").write_text(
            (path / "forge.toml").read_text(encoding="utf-8")
            + '\n[models.unknown]\nmodel = "anything"\neffort = "high"\n', encoding="utf-8")
    gh.respond("pr", "list", "--state", "open", stdout=json.dumps([
        {"headRefName": "fix/broken-settings", "url": "https://example.test/pr/1"},
        {"headRefName": "task/SHOP-SAVE", "url": "https://example.test/pr/2"}]))

    for path in (broken, broken_task):
        result = repo.forge("next", cwd=path)
        assert result.returncode == 0, result.stderr
        for unreadable in (broken, broken_task):
            assert (f"{unreadable}: forge.toml's [models] table is not usable: "
                    "unknown is not a kind of work" in result.stdout)
        assert "The fix healthy is started" in result.stdout
        assert "SHOP/SAVE is waiting for its checks" in result.stdout
        assert "How the factory is doing:" in result.stdout
