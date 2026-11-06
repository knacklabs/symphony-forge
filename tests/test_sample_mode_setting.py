"""Sample mode requires the current setting, never a historical sign-off.

Test audit: protect real close and test commands from silently skipping tests.
The credible regression is the old sign-off fallback clearing the test command.
Existing sample setup coverage has no stale sign-off with an absent setting.
Reuse client fixtures and fake only GitHub and review; no production seam is needed.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from test_app_constitution import _fixture_git
from test_close import CLEAN, GREEN, env  # noqa: F401
from test_sample_setup import _prepared_client

STORY = "FIX-SAMPLE-DATA-ONLY-FROM-SETTING"


@pytest.mark.parametrize("case,enabled", [
    ("new client", False), ("earlier adopted", False), ("new client", True),
], ids=["new-client-absent", "earlier-adopted-absent", "explicit-true"])
def test_1_only_the_setting_can_skip_client_tests(env, tmp_path, case, enabled):
    repo = env.repo
    marker = tmp_path / "test-ran"
    top, config = _prepared_client(repo, env.gh, tmp_path, case, marker)
    if not enabled:
        config.write_text(re.sub(r"(?m)^sample_data = true\n", "",
                                 config.read_text("utf-8")), encoding="utf-8")
    repo.write("docs/decisions/0001-client-signoff.md",
               "---\nstatus: accepted\nsample_data: true\n---\n# Client sign-off\n")
    repo.write("docs/product/BRIEF.md",
               "# Product brief\n\n## Answers\n- Personal data: none (client, 2026-11-06)\n")
    repo.git("add", "-A", cwd=top)
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Keep the earlier sign-off", cwd=top)
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main", cwd=top)
    started = repo.forge("fix", "start", "Tidy app", "--done", "The app is tidy",
                         "--kind", "mechanical", cwd=top)
    assert started.returncode == 0, started.stdout + started.stderr
    where = Path(re.search(r" in (.+)\n", started.stdout)[1])
    env.commit(where, "app.py", "print('working app')\n", "Keep the app working")
    env.reviews(CLEAN)
    env.open_pr("")
    env.checks(GREEN)
    closed = env.close("tidy-app")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert marker.exists() is not enabled, closed.stdout + closed.stderr
    assert ("no tests or CI in sample-data mode" in closed.stdout) is enabled
    marker.unlink(missing_ok=True)
    tested = repo.forge("test", "--change", cwd=where)
    assert tested.returncode == 0, tested.stdout + tested.stderr
    assert marker.exists() is not enabled, tested.stdout + tested.stderr
