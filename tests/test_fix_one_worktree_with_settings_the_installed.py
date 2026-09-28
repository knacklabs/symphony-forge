"""`forge next` keeps listing fixes when one worktree has unsupported settings."""

import json

from test_story import setup

STORY = "one-worktree-with-settings-the-installed"


def test_1_next_lists_other_items_and_names_the_unreadable_worktree(repo, gh):
    setup(repo)
    broken = repo.path.parent / "repo fix broken settings"
    healthy = repo.path.parent / "repo fix healthy"
    for name, path, status in (("broken-settings", broken, "waiting for checks"),
                               ("healthy", healthy, "started")):
        repo.git("worktree", "add", "-q", "-b", f"fix/{name}", str(path), "main")
        state = path / ".factory" / "fixes" / f"{name}.json"
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps({"branch": f"fix/{name}", "status": status}),
                         encoding="utf-8")
    (broken / "forge.toml").write_text(
        (broken / "forge.toml").read_text(encoding="utf-8")
        + '\n[models.unknown]\nmodel = "anything"\neffort = "high"\n', encoding="utf-8")
    gh.respond("pr", "list", "--state", "open", stdout=json.dumps([
        {"headRefName": "fix/broken-settings", "url": "https://example.test/pr/1"}]))

    result = repo.forge("next")

    assert result.returncode == 0, result.stderr
    assert (f"{broken}: forge.toml's [models] table is not usable: unknown is not a kind of work"
            in result.stdout)
    assert "The fix healthy is started" in result.stdout
