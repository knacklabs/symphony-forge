"""A background refresh keeps the screen: the shipped app-baseline skill says so.

Test audit: init and sync output are the public contract. A lost sentence in the template,
or a sync that leaves an older copy in place, recreates the bug; the package hash only pins
bytes and deletes the copies first. No production seam is needed.
"""

import pytest

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


@pytest.mark.platform
def test_2_sync_replaces_stale_copies_in_a_new_repo(env, tmp_path):
    client, made = _fresh_client(env.repo, env.gh, tmp_path)
    assert made.returncode == 0, made.stdout + made.stderr
    repo = env.repo
    for host in (".codex", ".claude"):
        (client / host / "skills/app-baseline/SKILL.md").write_text(STALE, "utf-8")
    (client / "app.py").write_text("print('mine')\n", "utf-8")
    repo.git("switch", "-qc", "fix/refresh-baseline", cwd=client)
    repo.git("add", "-A", cwd=client)
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-qm", "Keep stale copies",
             cwd=client)
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    _assert_both_hosts(client)
    changed = repo.git("status", "--porcelain", "--untracked-files=all", cwd=client).split("\n")
    paths = [line[3:] for line in changed if line]
    assert (client / "app.py").read_text("utf-8") == "print('mine')\n"
    assert not [p for p in paths if p == "app.py" or p.startswith(("src/", "tests/"))], paths
