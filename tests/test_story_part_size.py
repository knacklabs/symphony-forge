"""Large parts warn without a stop, and both client hosts receive the rule."""
import json
import tomllib
from pathlib import Path

import pytest

from test_close import GREEN, STORY_DOC, approve_story, env  # noqa: F401
from test_setup import _fresh_client
from test_upgrade_command import (NAME, RELEASE, _repo_adopted_on_the_previous_release,
                                 unsynced_up)  # noqa: F401

STORY = "part-size-limit"


@pytest.mark.parametrize("case", ["400 lines", "401 lines", "deleted lines", "tests and docs excluded"])
def test_1_close_warns_about_a_large_part_and_goes_on(env, case):
    # Close owns counting and continuation; the former contract stopped before review.
    if case == "deleted lines":
        env.commit(env.repo.path, "app.py", "old = 1\n" * 401)
        env.repo.git("push", "-q", "origin", "main")
    count = 400 if case == "400 lines" else 401
    changes = {"app.py": "new = 1\n" * (0 if case == "deleted lines" else count)}
    if case == "tests and docs excluded":
        changes = {"app.py": "new = 1\n" * 300}
        changes.update({path: "assert True\n" * 600 for path in (
            "tests/test_app.py", "web/app.test.ts", "web/app.spec.ts",
            "server/test_api.py", "server/api_test.py", "server/testing/helper.py")})
        changes.update({"docs/design.html": "Design\n" * 600,
                        "plans/notes.txt": "Notes\n" * 600})
    item, where = env.start_approved_task(STORY_DOC, changes=changes)
    done = env.close(item)
    assert done.returncode == 0, done.stdout + done.stderr
    warnings = [line for line in (done.stdout + done.stderr).splitlines()
                if line.startswith("Warning: This part changes")]
    assert warnings == (["Warning: This part changes 401 lines outside tests and docs; aim for about 400."]
                        if case in {"401 lines", "deleted lines"} else [])
    assert len(env.review_calls()) == 1
    assert len(env.gh_calls("pr", "create")) == 1
    assert "stop" not in json.loads((where / ".factory/stories/SHOP/tasks/T1.json").read_text())


def test_2_a_part_start_prints_the_size_rule(env):
    # Start output owns the reminder; fixes must not receive a part rule.
    approve_story(env.repo, STORY_DOC)
    started = env.repo.forge("task", "start", "SHOP/T1")
    assert started.returncode == 0, started.stdout + started.stderr
    lines = started.stdout.splitlines()
    assert lines[0].startswith("Started ")
    assert lines[1] == "Keep this part to about 400 changed lines outside tests and docs; close only warns when it is larger."
    assert lines[2].startswith("Next:")
    fixed = env.repo.forge("fix", "start", "Repair a typo", "--done", "The typo is fixed")
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    assert "400 changed lines" not in fixed.stdout


@pytest.mark.parametrize("adoption", ["new init", "previous release upgrade and sync"])
def test_3_the_guide_says_close_only_warns(unsynced_up, adoption):
    # The guide is a shipped prompt contract: inspect both actual command-generated guides,
    # not the source template. uv and GitHub are faked only at their external boundaries.
    up = unsynced_up
    if adoption == "new init":
        client, made = _fresh_client(up.repo, up.env.gh, up.tmp)
        assert made.returncode == 0, made.stdout + made.stderr
    else:
        _repo_adopted_on_the_previous_release(up)
        client = up.folder
    for host in (".codex", ".claude"):
        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "Keep each part's builder notes to its goal, files and one test per rule." in guide
        assert "about 400 changed lines" in guide
        assert "close warns when a part is larger" in guide
        assert "Close stops a part over 400 lines" not in guide
        assert "Stories approved before this limit keep working" not in guide


def _old_size_stop(up, adoption):
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
    up.on_main("forge.toml", settings, "Configure test worker")
    up.repo.git("config", "core.hooksPath", (up.tmp / "no-hooks").as_posix())
    up.env.checks(GREEN)
    approve_story(up.repo, STORY_DOC)
    trees = up.repo.git("worktree", "list", "--porcelain").split("\n\n")
    story_path = Path(next(entry.splitlines()[0].removeprefix("worktree ") for entry in trees
                           if "branch refs/heads/story/SHOP" in entry))
    rel = ".factory/stories/SHOP/story.json"
    state = json.loads((story_path / rel).read_text("utf-8"))
    state["approval"]["part_line_limit"] = 400
    up.env.commit(story_path, rel, json.dumps(state), "Old approval limit")
    up.repo.git("merge", "-q", "--ff-only", "story/SHOP")
    up.repo.git("push", "-q", "origin", "main")
    started = up.repo.forge("task", "start", "SHOP/T1")
    assert started.returncode == 0, started.stdout + started.stderr
    where = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    up.env.commit(where, "app.py", "value = 1\n" * 401)
    rel = ".factory/stories/SHOP/tasks/T1.json"
    state = json.loads((where / rel).read_text("utf-8"))
    state.update(part_line_limit=400, status="hotspot",
                 stop={"question": "OLD SIZE QUESTION", "size": True})
    up.env.commit(where, rel, json.dumps(state), "Saved old size question")
    return where


@pytest.mark.parametrize("adoption", ["new init", "previous release"])
def test_4_an_approval_with_a_saved_limit_or_size_stop_still_closes(unsynced_up, adoption):
    # Real next and close must ignore an old local stop; no migration or allowance is needed.
    up = unsynced_up
    _old_size_stop(up, adoption)
    next_step = up.repo.forge("next")
    assert next_step.returncode == 0, next_step.stdout + next_step.stderr
    assert "OLD SIZE QUESTION" not in next_step.stdout
    assert "--resolve" not in next_step.stdout
    done = up.env.close("SHOP/T1")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Warning: This part changes 401 lines" in done.stdout + done.stderr


@pytest.mark.parametrize("adoption", ["new init", "previous release"])
def test_5_a_saved_size_stop_shows_no_question_from_published_state(unsynced_up, adoption):
    # Published state bypasses read_state, so both views must filter the old question too.
    up = unsynced_up
    where = _old_size_stop(up, adoption)
    up.repo.git("push", "-q", "origin", "task/SHOP-T1", cwd=where)
    up.repo.git("worktree", "remove", str(where))
    up.repo.git("branch", "-D", "task/SHOP-T1")
    for command in (("next",), ("board", "--json")):
        shown = up.repo.forge(*command)
        assert shown.returncode == 0, shown.stdout + shown.stderr
        assert "OLD SIZE QUESTION" not in shown.stdout
        assert "--resolve" not in shown.stdout
