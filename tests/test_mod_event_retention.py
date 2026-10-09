"""Native regressions and delivery through new and previously adopted clients."""
import pytest

from test_mod_native import run_native_plugin_checks
from test_mod_plugin import packaged_mod, strict_typescript_against_claude_declarations
from test_mod_sync import (_sync_keeps_the_mod_current_at_user_scope,
                           _previously_adopted_repo_gets_the_mod)

STORY = "skipped-mod"


def test_1_native_mod_events_and_machine(tmp_path, packaged_mod):
    strict_typescript_against_claude_declarations(packaged_mod)
    run_native_plugin_checks(tmp_path)


@pytest.mark.parametrize('adopted', [False, True])
def test_2_sync_delivers_the_mod_to_new_and_existing_repos(repo, monkeypatch, adopted):
    if adopted:
        _previously_adopted_repo_gets_the_mod(repo)
    else:
        _sync_keeps_the_mod_current_at_user_scope(repo, monkeypatch, False, '')
