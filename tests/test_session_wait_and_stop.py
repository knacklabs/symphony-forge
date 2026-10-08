"""Native boundary proof for session queue suffixes and stop outcomes.

Test-audit: static session paths and discarded successful stdout are credible
regressions. Existing MACHINE tests miss directory changes and the post-list
stop race. No production testing seam is added.
"""
import pytest

from test_mod_native import run_native_plugin_checks
from test_mod_sync import (_previously_adopted_repo_gets_the_mod,
                           _sync_keeps_the_mod_current_at_user_scope)

STORY = 'spinner-place'


def test_1_native_session_wait_and_stop_outcomes(tmp_path):
    run_native_plugin_checks(tmp_path)


@pytest.mark.parametrize('adoption', ['new', 'earlier'])
def test_2_sync_delivers_session_wait_and_stop_mod(repo, monkeypatch, adoption):
    if adoption == 'new':
        _sync_keeps_the_mod_current_at_user_scope(repo, monkeypatch, False, '')
    else:
        _previously_adopted_repo_gets_the_mod(repo)
