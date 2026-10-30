"""A part's design copies and documentation do not consume its code limit."""
import tomllib

import pytest

from test_close import GREEN, STORY_DOC, env  # noqa: F401
from test_setup import _fresh_client
from test_upgrade_command import (NAME, RELEASE, _repo_adopted_on_the_previous_release,
                                 unsynced_up)  # noqa: F401

STORY = "part-size-code-only"


@pytest.mark.parametrize("adoption", ["new init", "previous release upgrade"])
def test_1_close_counts_code_without_design_copies_or_markdown(unsynced_up, adoption):
    # Audit: the real close must accept 300 code lines under a 400-line limit even with
    # 600 design lines. The old size test covers tests/plans, but not docs or Markdown.
    # Only external tools are faked; no seam supplies the size decision.
    up = unsynced_up
    env = up.env
    settings = up.toml()
    up.version = tomllib.loads(settings)["version"]
    if adoption == "new init":
        client, made = _fresh_client(up.repo, env.gh, up.tmp)
        assert made.returncode == 0, made.stdout + made.stderr
        up.repo.path = client
    else:
        _repo_adopted_on_the_previous_release(up)
        up.repo.git("merge", "-q", "--ff-only", f"fix/{NAME}")
        settings = settings.replace(up.version, RELEASE)
    # Give both client paths the close harness's worker and check configuration.
    up.on_main("forge.toml", settings, "Configure test worker")
    # The approval harness simulates the human's commits and merges on main.
    up.repo.git("config", "core.hooksPath", (up.tmp / "no-hooks").as_posix())
    env.checks(GREEN)
    changes = {
        "app.py": "value = 1\n" * 300,
        "docs/board-design/screen.dc.html": "<div>Design</div>\n" * 600,
        "README.md": "Documentation\n" * 600,
        "notes/DESIGN.MD": "Design notes\n" * 600,
        "plans/notes.txt": "Builder notes\n" * 600,
        ".factory/design.html": "Design copy\n" * 600,
        "tests/test_app.py": "assert True\n" * 600,
    }
    item, _ = env.start_approved_task(STORY_DOC, changes=changes)
    reviews = len(env.review_calls())
    publications = len(env.gh_calls("pr", "create"))

    done = env.close(item)

    assert done.returncode == 0, done.stdout + done.stderr
    assert len(env.review_calls()) == reviews + 1
    assert len(env.gh_calls("pr", "create")) == publications + 1
    for host in (".codex", ".claude"):
        guide = " ".join((up.repo.path / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "outside tests, Markdown files, docs/, plans/ and .factory/." in guide
