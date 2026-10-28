"""Close applies a repo's added-work minimum and must-not-miss kinds."""
from __future__ import annotations

import pytest

from test_close import blocked, body, env  # noqa: F401
from test_score_notes import _client_repo, _scored


STORY = "FORGE-BAR-1"
CLIENTS = ["new-client", "adopted-v1.2.2"]


def _set_main_setting(env, key: str, value: str | None, message: str) -> None:
    repo = env.repo
    config = (repo.path / "forge.toml").read_text("utf-8")
    lines = [line for line in config.splitlines() if not line.startswith(f"{key} =")]
    if value is not None:
        lines.append(f"{key} = {value}")
    env.commit(repo.path, "forge.toml", "\n".join(lines) + "\n", message)
    repo.git("push", "-q", "origin", "main")


def _prepare_client(env, tmp_path, case: str) -> None:
    _client_repo(env, tmp_path, case == "adopted-v1.2.2")
    # A teammate's clone represents settings that already landed on the default branch.
    writer = tmp_path / "settings-writer"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(writer))
    env.repo.path = writer


@pytest.mark.parametrize("case", CLIENTS, ids=CLIENTS)
def test_1_added_work_below_the_minimum_gain_is_a_follow_up(env, tmp_path, case):
    _prepare_client(env, tmp_path, case)
    _set_main_setting(env, "added_work_min_gain", "5", "Set the added-work minimum")
    item, _ = env.start_fix()
    retry = _scored("P1", "Retry the upload",
                    "Gain 4, Work 2, Harm 1\nAdds work: retry after a temporary upload failure")
    unnamed = _scored("P1", "Upload drops the file name", "Gain 4, Work 2, Harm 1")
    security = _scored("P1", "Check the upload token",
                       "Gain 3, Work 2, Harm 1\nAdds work: check the token before saving\nRaise: Security")
    database = _scored("P1", "Database: Upload.size",
                       "Gain 2, Work 3, Harm 1\nAdds work: constrain the uploaded size")
    env.reviews(blocked(retry, unnamed, security, database))

    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Upload drops the file name" in closed.stdout
    assert "Check the upload token" in closed.stdout
    assert "Database: Upload.size" in closed.stdout
    published = body(env.gh_calls("pr", "edit")[-1])
    for title in (unnamed["title"], security["title"], database["title"]):
        assert f"{title} (app.py:1): blocks the merge" in published
    assert ("Retry the upload (app.py:1)\nDoes not block: Adds work below this repo's minimum Gain 5.\n"
            "Gain 4, Work 2, Harm 1") in closed.stdout
    prompt = env.prompt()
    assert "## Added work" in prompt and "5" in prompt

    # Settings come from the current default branch. Reclassify the same work without a worker commit.
    _set_main_setting(env, "added_work_min_gain", None, "Restore the default review bar")
    repeated = env.close(item)
    assert repeated.returncode == 1, repeated.stdout + repeated.stderr
    assert "Retry the upload" in repeated.stdout
    assert "Retry the upload (app.py:1): blocks the merge" in body(env.gh_calls("pr", "edit")[-1])
    assert "Does not block: Adds work below this repo's minimum Gain 5." not in repeated.stdout


@pytest.mark.parametrize("case", CLIENTS, ids=CLIENTS)
def test_2_a_listed_kind_blocks_at_any_score(env, tmp_path, case):
    _prepare_client(env, tmp_path, case)
    _set_main_setting(env, "always_block", '["legal"]', "Require legal findings")
    item, where = env.start_fix()
    legal = _scored("P1", "Must: Legal: the cookie notice is missing",
                    "Gain 1, Work 1, Harm 1\nCase: rare - one country")
    tone = _scored("P1", "Must: tone: a softer error", "Gain 1, Work 1, Harm 1")
    env.reviews(blocked(legal, tone))

    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Must: Legal: the cookie notice is missing" in closed.stdout
    assert f"{legal['title']} (app.py:1): blocks the merge" in body(env.gh_calls("pr", "edit")[-1])
    assert ("Must: tone: a softer error (app.py:1)\nDoes not block: Below the review bar.\n"
            "Gain 1, Work 1, Harm 1") in closed.stdout
    prompt = env.prompt()
    assert "## Kinds a change must not miss" in prompt and "legal" in prompt

    env.open_pr(body(env.gh_calls("pr", "edit")[-1]), draft=True)
    chosen = env.close(item, "--resolve", "more", "--reason", "Repair the missing legal notice")
    assert chosen.returncode == 0, chosen.stdout + chosen.stderr
    env.commit(where, "app.py", "print('still here')\n",
               "Declined: Must: Legal: the cookie notice is missing (app.py): not worth the code - small")
    repeated = env.close(item)
    assert repeated.returncode == 1, repeated.stdout + repeated.stderr
    assert "Must: Legal: the cookie notice is missing" in repeated.stdout
    assert f"{legal['title']} (app.py:1): blocks the merge" in body(env.gh_calls("pr", "edit")[-1])


@pytest.mark.parametrize("case", CLIENTS, ids=CLIENTS)
def test_4_no_setting_keeps_todays_bar(env, tmp_path, case):
    _prepare_client(env, tmp_path, case)
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    assert "added_work_min_gain =" not in config
    assert "always_block =" not in config
    skill = (env.repo.path / ".codex/skills/forge/SKILL.md").read_text("utf-8")
    closing = skill.split("## Closing", 1)[1]
    assert "added_work_min_gain" in closing and "always_block" in closing
    assert "Only the owner can accept" in closing

    item, _ = env.start_fix()
    added = _scored("P1", "Retry the save",
                    "Gain 3, Work 2, Harm 3\nAdds work: retry after a temporary save failure")
    legal = _scored("P1", "Must: legal: the cookie notice is missing", "Gain 1, Work 1, Harm 1")
    env.reviews(blocked(added, legal))
    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Retry the save" in closed.stdout
    assert ("Must: legal: the cookie notice is missing (app.py:1)\nDoes not block: Below the review bar.\n"
            "Gain 1, Work 1, Harm 1") in closed.stdout
    prompt = env.prompt()
    assert "## Added work" not in prompt
    assert "## Kinds a change must not miss" not in prompt

    _set_main_setting(env, "added_work_min_gain", "2", "Set an invalid added-work minimum")
    invalid = env.repo.forge("next")
    assert invalid.returncode == 1
    assert "forge.toml is not usable: added_work_min_gain must be 3, 4 or 5." in invalid.stderr
