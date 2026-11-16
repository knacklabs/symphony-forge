"""A background refresh keeps the screen: the shipped app-baseline skill says so.

Test audit: init and sync output are the public contract. A lost sentence in the template,
or a sync that leaves an older copy in place, recreates the bug; the package hash only pins
bytes and deletes the copies first. No production seam is needed.
"""

import shutil

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401 (env is a fixture)
from test_setup import _fresh_client

STORY = "FIX-BACKGROUND-REFRESH"
REFRESH = ("A background refresh keeps the screen. Show the loading state only when there is "
           "no data yet. On a refetch, keep the shown data, scroll position, open sections, "
           "selection, focus and typed text, and change only what changed. A browser test "
           "scrolls, opens a section, lets two refetches pass and checks both.")
URL = "Page, sort, filters, search and the open tab of a detail page live in the URL."
STALE = "# App baseline\n\n## 4. Lists\n\n- Page, sort, filters and search live in the URL.\n"


def _assert_both_hosts(top):
    for host in (".codex", ".claude"):
        text = " ".join((top / host / "skills/app-baseline/SKILL.md").read_text("utf-8").split())
        assert REFRESH in text, host
        assert URL in text, host


@pytest.mark.platform
def test_1_new_repo_gets_the_refresh_rule_from_init(env, tmp_path):
    client, made = _fresh_client(env.repo, env.gh, tmp_path)
    assert made.returncode == 0, made.stdout + made.stderr
    _assert_both_hosts(client)
