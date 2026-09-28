"""Forge delivers the two-skill UI contract to workers and reviewers."""

from test_close import env  # noqa: F401 (pytest fixture)
from test_worker import calls, install_claude

STORY = "FIX-BOTH-UI-SKILLS"


def flat(text):
    return " ".join(text.split())


def test_1_sync_delivers_both_ui_skills_and_motion_resolutions(env):
    repo = env.repo
    repo.git("checkout", "-q", "-b", "fix/ui-skill-guidance")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    for host in (".claude", ".codex"):
        standard = flat((repo.path / host / "skills/forge/standards.md").read_text("utf-8"))
        assert "impeccable and emil-design-eng are required for every UI" in standard
        assert "prototypes included" in standard
        assert "one batched inspection" in standard
        assert "under 300 ms" in standard
        assert "@starting-style" in standard
        assert "cubic-bezier(0.23, 1, 0.32, 1)" in standard


def test_2_worker_and_review_get_both_ui_skills_and_blocking_checks(env):
    repo = env.repo
    config = repo.path / "forge.toml"
    config.write_text(config.read_text("utf-8") +
                      'models.lite = { model = "sonnet", effort = "medium" }\n', "utf-8")
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin worker model")
    repo.git("push", "-q", "origin", "main")
    log = install_claude(repo)
    item, _ = env.start_fix()
    worked = repo.forge("work", item)
    assert worked.returncode == 0, worked.stderr
    brief = flat(calls(log)[-1]["brief"])
    assert "impeccable and emil-design-eng are required for every UI" in brief
    assert "prototypes included" in brief
    assert "one batched inspection" in brief
    assert "Invoke emil-design-eng with a specific task" in brief

    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    review = flat(env.prompt())
    assert "impeccable and emil-design-eng are required for every UI" in review
    assert "prototypes included" in review
    assert "one batched inspection" in review
    assert "P1 `Not done`" in review
    assert "failed emil-design-eng checklist item" in review
    assert "not a `Simpler:` finding" in review
