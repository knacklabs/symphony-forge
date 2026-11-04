"""Git's generated-file marks exclude contents from size limits, not other checks."""
import tomllib

import pytest

from test_close import GREEN, STORY_DOC, env  # noqa: F401
from test_setup import _fresh_client
from test_upgrade_command import (NAME, RELEASE, _repo_adopted_on_the_previous_release,
                                 unsynced_up)  # noqa: F401

STORY = "size-count-skips-generated"


@pytest.mark.parametrize("adoption", ["new init", "previous release"])
@pytest.mark.parametrize("boundary", ["part close", "fix commit", "fix pull request"])
def test_1_generated_files_do_not_count_towards_size(unsynced_up, adoption, boundary):
    # Audit: real close/hook commands must ignore generated files in size counts.
    # Existing size tests have no Git attributes; omitting this filter regresses this rule.
    # PR checks run on main, so head-only attributes must work there too. No new seam.
    up = unsynced_up
    settings = up.toml()
    version = tomllib.loads(settings)["version"]
    if adoption == "new init":
        client, made = _fresh_client(up.repo, up.env.gh, up.tmp)
        assert made.returncode == 0, made.stdout + made.stderr
        up.repo.path = client
    else:
        _repo_adopted_on_the_previous_release(up)
        up.repo.git("merge", "-q", "--ff-only", f"fix/{NAME}")
        settings = settings.replace(version, RELEASE)
    # Source repos retain the five-file limit; prototype client fixes have an allowance.
    settings = settings.replace('repo = "client"', 'repo = "forge-source"')
    up.on_main("forge.toml", settings, "Configure test worker")
    up.repo.git("config", "core.hooksPath", (up.tmp / "no-hooks").as_posix())
    up.on_main(".gitattributes", ".gitattributes linguist-generated\n")
    up.env.checks(GREEN)
    changes = {
        ".gitattributes": '.gitattributes linguist-generated\n"api/open api.json" linguist-generated=true\n',
        "api/open api.json": "{}\n" * 1001,
    }
    if boundary == "part close":
        changes["app.py"] = "value = 1\n" * 300
        item, where = up.env.start_approved_task(STORY_DOC, changes=changes)
        done = up.env.close(item)
        assert done.returncode == 0, done.stdout + done.stderr
        assert "Warning: This part changes" not in done.stdout + done.stderr
    else:
        changes.update({f"part{n}.py": "value = 1\n" for n in range(5)})
        item, where = up.env.start_fix(changes)
        if boundary == "fix commit":
            done = up.repo.forge("hook", "pre-commit", cwd=where)
        else:
            closed = up.env.close(item)
            assert closed.returncode == 0, closed.stdout + closed.stderr
            done = up.repo.forge("hook", "pr-check", "--base", up.repo.git("rev-parse", "HEAD"),
                                 "--head", up.repo.git("rev-parse", "HEAD", cwd=where),
                                 "--branch", "fix/tidy-readme")
        assert done.returncode == 0, done.stdout + done.stderr
    for host in (".codex", ".claude"):
        guide = " ".join((up.repo.path / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "They count towards neither a part's size warning nor a fix's code-file limit." in guide
